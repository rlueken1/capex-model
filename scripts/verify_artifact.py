#!/usr/bin/env python3
"""Verify a downloaded data artifact against its provenance.json and the committed manifest.

Gate 2, G2-3 (gate-2.md D8). Run before any case loader reads the files:
    python scripts/verify_artifact.py <artifact_dir> [--against <vendored_dir>] [--summary]
Checks: every file listed in provenance.json exists with that sha256 and size; no extra
files; and for manifest rows with a pinned sha256, provenance agrees with the manifest
(so an artifact from an older manifest is caught). --against also requires each file's sha256 to equal
the same-named file in a vendored directory. --summary prints a markdown provenance table (for
$GITHUB_STEP_SUMMARY) and nothing else. Exit 0 ok, 1 mismatch, 2 bad input.
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


def verify_against(art: Path, vendored: Path) -> list[str]:
    """Each data file in the artifact must equal the same-named file in `vendored` (sha256)."""
    prov = json.loads((art / "provenance.json").read_text())
    problems = []
    for f in prov["files"]:
        other = vendored / f["file"]
        if not other.is_file():
            problems.append(f"{f['file']}: no vendored copy in {vendored}")
        elif sha256_file(other)[0] != f["sha256"]:
            problems.append(f"{f['file']}: sha256 differs from vendored copy {other}")
    return problems


def summary_markdown(art: Path) -> str:
    """provenance.json and a file/hash table as markdown."""
    text = (art / "provenance.json").read_text()
    prov = json.loads(text)
    rows = "\n".join(f"| `{f['file']}` | {f['bytes']} | `{f['sha256']}` | {f['verified']} |" for f in prov["files"])
    return (f"### data-download {prov['source_id']} ({prov['vintage']})\n\n"
            f"| file | bytes | sha256 | pinned and verified |\n|---|---|---|---|\n{rows}\n\n"
            f"<details><summary>provenance.json</summary>\n\n```json\n{text}```\n\n</details>\n")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("artifact_dir")
    p.add_argument("--manifest-dir", default="data/manifests")
    p.add_argument("--against", default=None, help="vendored directory whose same-named files must hash equal")
    p.add_argument("--summary", action="store_true", help="print a markdown provenance table and exit")
    a = p.parse_args(argv)
    art = Path(a.artifact_dir)
    if not (art / "provenance.json").is_file():
        print(f"ERROR: {art} is not a directory with provenance.json", file=sys.stderr)
        return 2
    if a.summary:
        print(summary_markdown(art))
        return 0
    problems = verify(art, Path(a.manifest_dir))
    if a.against:
        problems += verify_against(art, Path(a.against))
    for msg in problems:
        print(f"FAIL: {msg}", file=sys.stderr)
    if not problems:
        print(f"OK: {art} matches provenance.json and manifest")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
