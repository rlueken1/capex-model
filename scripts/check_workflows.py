"""Parse every GitHub workflow file with yaml.safe_load; exit 1 naming file and error on failure.

Usage: python scripts/check_workflows.py [workflows_dir]   (default: .github/workflows)
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def workflow_files(directory: Path) -> list[Path]:
    return sorted([*directory.glob("*.yml"), *directory.glob("*.yaml")])


def main(argv: list[str]) -> int:
    directory = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent / ".github" / "workflows"
    failed = False
    for path in workflow_files(directory):
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"FAIL {path}: {exc}", file=sys.stderr)
            failed = True
        else:
            print(f"ok {path}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
