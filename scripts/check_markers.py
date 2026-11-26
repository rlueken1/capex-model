"""Gate 2 C5: every xfail/skip/skipif marker or call in tests/ must carry a reason citing DECISIONS <n> or Gate <n>.

Markers under tests/draft/ must be skips (not xfails) citing Gate <n>.
Usage: python scripts/check_markers.py [tests_dir]   |   python scripts/check_markers.py --self-test
"""
from __future__ import annotations

import ast
import re
import sys
from pathlib import Path

MARK_KINDS = {"skip", "skipif", "xfail"}
CALL_KINDS = {"skip", "xfail"}
REF = re.compile(r"(DECISIONS|Gate) \d+")
GATE_REF = re.compile(r"Gate \d+")


def _strings(node: ast.AST | None) -> str:
    if node is None:
        return ""
    return " ".join(n.value for n in ast.walk(node) if isinstance(n, ast.Constant) and isinstance(n.value, str))


def _dotted(node: ast.AST) -> str:
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def _reason_node(kind: str, call: ast.Call | None, is_mark: bool) -> ast.AST | None:
    if call is None:
        return None
    for kw in call.keywords:
        if kw.arg in ("reason", "msg"):
            return kw.value
    if kind == "skipif" and is_mark:
        return None
    return call.args[0] if call.args else None


def scan_source(source: str, filename: str, draft: bool) -> list[str]:
    """Return one 'file:line: message' per offending marker."""
    tree = ast.parse(source, filename)
    call_funcs = {id(n.func) for n in ast.walk(tree) if isinstance(n, ast.Call)}
    calls = {id(n.func): n for n in ast.walk(tree) if isinstance(n, ast.Call)}
    problems: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        dotted = _dotted(node)
        is_mark = dotted == f"pytest.mark.{node.attr}" and node.attr in MARK_KINDS
        is_call = dotted == f"pytest.{node.attr}" and node.attr in CALL_KINDS
        if not (is_mark or is_call):
            continue
        if is_call and id(node) not in call_funcs:
            continue  # bare reference such as `pytest.skip` passed around; only calls count
        kind = node.attr
        reason = _strings(_reason_node(kind, calls.get(id(node)), is_mark))
        where = f"{filename}:{node.lineno}: {dotted}"
        if not REF.search(reason):
            problems.append(f"{where} lacks a reason containing 'DECISIONS <n>' or 'Gate <n>'")
        elif draft and (kind == "xfail" or not GATE_REF.search(reason)):
            problems.append(f"{where} under tests/draft/ must be a skip with 'Gate <n>'")
    return problems


def scan_tree(tests_dir: Path) -> list[str]:
    problems: list[str] = []
    for path in sorted(tests_dir.rglob("*.py")):
        draft = "draft" in path.relative_to(tests_dir).parts[:-1]
        problems += scan_source(path.read_text(), str(path), draft)
    return problems


_BAD_SAMPLE = '''
import pytest

@pytest.mark.xfail
def test_a(): ...

@pytest.mark.skip(reason="flaky")
def test_b(): ...

def test_c():
    pytest.skip("not now")

@pytest.mark.skipif(True, reason="DECISIONS 7 ok")
def test_d(): ...
'''


def self_test() -> int:
    problems = scan_source(_BAD_SAMPLE, "<bad-sample>", draft=False)
    problems += scan_source('import pytest\n@pytest.mark.xfail(reason="Gate 3")\ndef t(): ...\n', "<draft-xfail>", draft=True)
    print("\n".join(problems))
    if len(problems) != 4:
        print(f"self-test BROKEN: expected 4 problems, got {len(problems)}")
        return 2
    print("self-test: checker correctly rejects the bad sample (exit 1)")
    return 1


def main(argv: list[str]) -> int:
    if argv[:1] == ["--self-test"]:
        return self_test()
    problems = scan_tree(Path(argv[0] if argv else "tests"))
    if problems:
        print("\n".join(problems))
        print(f"{len(problems)} marker(s) violate the C5 reason rule")
        return 1
    print("check_markers: all xfail/skip markers carry a DECISIONS/Gate reference")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
