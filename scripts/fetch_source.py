#!/usr/bin/env python3
"""Download one registry source from its committed manifest and write provenance.json.

Gate 2, G2-3 (docs/gates/gate-2.md section 3, D1-D8).
Stdlib only, so the workflow needs no project install.

Manifest: data/manifests/<source_id>.csv with columns
  source_id, vintage, file, url, sha256, bytes, auth_env, enabled, note
- sha256 = 64-hex pinned hash, or "unpinned" (only fetched with --pin-mode record).
- auth_env = name of an environment variable holding a key; the url may contain
  "{NAME}" which is replaced by the key. The key is never printed or written.
- enabled = false rows are declared but not fetched (exit 0 with a message).

Exit codes: 0 ok or clean skip; 1 hash/size mismatch or download error; 2 bad input.
On any failure nothing is left in the output directory, so nothing is uploaded.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import re
import shutil
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HEX64 = re.compile(r"^[0-9a-f]{64}$")
COLUMNS = ["source_id", "vintage", "file", "url", "sha256", "bytes", "auth_env", "enabled", "note"]


def load_rows(manifest_dir: Path, source_id: str, vintage: str | None) -> list[dict]:
    if not re.fullmatch(r"[a-z0-9_]+", source_id):
        raise SystemExit(_err(2, f"invalid source_id {source_id!r}"))
    path = manifest_dir / f"{source_id}.csv"
    if not path.is_file():
        raise SystemExit(_err(2, f"unknown source_id {source_id!r}: no manifest {path}"))
    with path.open(newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames != COLUMNS:
            raise SystemExit(_err(2, f"{path}: columns {reader.fieldnames} != {COLUMNS}"))
        rows = [r for r in reader if r["source_id"] == source_id]
    if vintage:
        rows = [r for r in rows if r["vintage"] == vintage]
    if not rows:
        raise SystemExit(_err(2, f"{source_id}: no manifest rows for vintage {vintage!r}"))
    vintages = {r["vintage"] for r in rows}
    if len(vintages) > 1:
        raise SystemExit(_err(2, f"{source_id}: several vintages {sorted(vintages)}; pass --vintage"))
    return rows


def _err(code: int, msg: str) -> int:
    print(f"ERROR: {msg}", file=sys.stderr)
    return code


def _url_with_key(row: dict) -> tuple[str, str] | None:
    """Return (real_url, redacted_url), or None when the needed key is absent."""
    url, env = row["url"], row["auth_env"].strip()
    if not env:
        return url, url
    key = os.environ.get(env, "")
    if not key:
        return None
    return url.replace("{" + env + "}", key), url.replace("{" + env + "}", "***")


def sha256_file(path: Path) -> tuple[str, int]:
    h, n = hashlib.sha256(), 0
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
            n += len(chunk)
    return h.hexdigest(), n


def fetch(args: argparse.Namespace) -> int:
    rows = load_rows(Path(args.manifest_dir), args.source_id, args.vintage)
    disabled = [r["file"] for r in rows if r["enabled"].strip().lower() != "true"]
    if disabled:
        print(f"SKIP: {args.source_id} rows {disabled} are declared but disabled (enabled=false in the manifest).")
        return 0
    urls = {}
    for r in rows:
        u = _url_with_key(r)
        if u is None:
            print(f"SKIP: {args.source_id}/{r['file']} needs secret {r['auth_env']}, which is not set. "
                  f"Add it as a repository secret to enable this source.")
            return 0
        urls[r["file"]] = u
    unpinned = [r["file"] for r in rows if not HEX64.match(r["sha256"])]
    if unpinned and args.pin_mode != "record":
        return _err(1, f"{args.source_id}: {unpinned} have no pinned sha256; dispatch with pin_mode=record "
                       f"to obtain hashes, then commit them to the manifest")

    out = Path(args.out_dir)
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    files, ok = [], True
    try:
        for r in rows:
            real, shown = urls[r["file"]]
            dest = out / r["file"]
            print(f"GET {shown} -> {dest.name}")
            req = urllib.request.Request(real, headers={"User-Agent": "capex-model-data-download"})
            with urllib.request.urlopen(req, timeout=args.timeout) as resp, dest.open("wb") as fh:
                shutil.copyfileobj(resp, fh)
            digest, size = sha256_file(dest)
            pinned = HEX64.match(r["sha256"]) is not None
            match = (digest == r["sha256"]) if pinned else None
            if pinned and not match:
                ok = False
                print(f"HASH MISMATCH {r['file']}: got {digest}, manifest {r['sha256']}", file=sys.stderr)
            if r["bytes"].strip() and int(r["bytes"]) != size:
                ok = False
                print(f"SIZE MISMATCH {r['file']}: got {size}, manifest {r['bytes']}", file=sys.stderr)
            files.append({"file": r["file"], "url": shown, "sha256": digest, "bytes": size,
                          "pinned": pinned, "verified": bool(match)})
    except Exception as exc:  # network, HTTP, disk
        shutil.rmtree(out, ignore_errors=True)
        msg = f"download failed: {type(exc).__name__}: {exc}"
        for env in {r["auth_env"].strip() for r in rows} - {""}:
            if os.environ.get(env):
                msg = msg.replace(os.environ[env], "***")
        return _err(1, msg)
    if not ok:
        shutil.rmtree(out, ignore_errors=True)
        return _err(1, "hash/size check failed; output removed, nothing will be uploaded")

    prov = {
        "source_id": args.source_id,
        "vintage": rows[0]["vintage"],
        "manifest": f"data/manifests/{args.source_id}.csv",
        "pin_mode": args.pin_mode,
        "retrieved_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "workflow_run_id": os.environ.get("GITHUB_RUN_ID", "local"),
        "workflow_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT", ""),
        "git_commit": os.environ.get("GITHUB_SHA", "local"),
        "files": files,
    }
    (out / "provenance.json").write_text(json.dumps(prov, indent=2) + "\n")
    print(f"OK: {len(files)} file(s) in {out}; all_verified={all(f['verified'] for f in files)}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a") as fh:
            fh.write("fetched=true\n")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("source_id")
    p.add_argument("--vintage", default=None)
    p.add_argument("--pin-mode", choices=["verify", "record"], default="verify")
    p.add_argument("--manifest-dir", default="data/manifests")
    p.add_argument("--out-dir", default="download")
    p.add_argument("--timeout", type=float, default=120.0)
    return fetch(p.parse_args(argv))


if __name__ == "__main__":
    sys.exit(main())
