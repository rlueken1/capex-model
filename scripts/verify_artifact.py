#!/usr/bin/env python3
"""Verify a downloaded data artifact against its provenance.json and the committed manifest.

DRAFT (prep item P4; gate-2.md D8). Run before any case loader reads the files:
    python scripts/verify_artifact.py <artifact_dir>
Checks: every file listed in provenance.json exists with that sha256 and size; no extra
files; and for manifest rows with a pinned sha256, provenance agrees with the manifest
(so an artifact from an older manifest is caught). Exit 0 ok, 1 mismatch, 2 bad input.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from fetch_source import HEX64, sha256_file  # noqa: E402


def verify(art: Path, manifest_dir: Path) -> list[str]:
    prov_path = art / "provenance.json"
    if not prov_path.is_file():
        return [f"no provenance.json in {art}"]
    prov = json.loads(prov_path.read_text())
    problems = []
    listed = {f["file"] for f in prov["files"]}
    extra = {p.name for p in art.iterdir() if p.is_file()} - listed - {"provenance.json"}
    if extra:
        problems.append(f"files not in provenance.json: {sorted(extra)}")
    for f in prov["files"]:
        path = art / f["file"]
        if not path.is_file():
            problems.append(f"missing {f['file']}")
            continue
        digest, size = sha256_file(path)
        if digest != f["sha256"] or size != f["bytes"]:
            problems.append(f"{f['file']}: sha256/bytes {digest}/{size} != provenance {f['sha256']}/{f['bytes']}")
    manifest = manifest_dir / f"{prov['source_id']}.csv"
    if manifest.is_file():
        with manifest.open(newline="") as fh:
            pins = {r["file"]: r["sha256"] for r in csv.DictReader(fh)
                    if r["vintage"] == prov["vintage"] and HEX64.match(r["sha256"])}
        for f in prov["files"]:
            if f["file"] in pins and pins[f["file"]] != f["sha256"]:
                problems.append(f"{f['file']}: provenance sha256 differs from manifest pin")
        if not pins:
            print(f"NOTE: {manifest} has no pinned hashes for vintage {prov['vintage']}; "
                  "checked against provenance.json only (pin_mode=record artifact)")
    else:
        problems.append(f"no manifest {manifest} for source_id {prov['source_id']!r}")
    return problems


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("artifact_dir")
    p.add_argument("--manifest-dir", default="data/manifests")
    a = p.parse_args(argv)
    art = Path(a.artifact_dir)
    if not art.is_dir():
        print(f"ERROR: {art} is not a directory", file=sys.stderr)
        return 2
    problems = verify(art, Path(a.manifest_dir))
    for msg in problems:
        print(f"FAIL: {msg}", file=sys.stderr)
    if not problems:
        print(f"OK: {art} matches provenance.json and manifest")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
