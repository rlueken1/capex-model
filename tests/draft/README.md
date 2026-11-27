# tests/draft - drafts awaiting a gate

Currently empty. The Gate 3 draft (`test_pjm5bus.py`, prep item P6) was promoted to `tests/test_pjm5bus.py` in G3-2 and
its SPEC-GAP notes resolved to the names fixed by formulation 7.4a.11 (F-0.3).
Convention for future drafts: written from the draft criteria and spec only (never from `src/capex`), skips (not xfails)
citing `Gate <n>`; promote by moving the file to `tests/` once the gate is approved and the spec names are fixed.
Never loosen a tolerance to make a test pass.
