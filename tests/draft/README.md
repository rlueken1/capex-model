# tests/draft - Gate 3 draft tests (prep item P6)

`test_pjm5bus.py` is written from the DRAFT `docs/gates/gate-3.md` and formulation 7.4a only (never from `src/capex`).
- Part 1 (runs now): independent DC-OPF reference route (scipy/HiGHS, angle + PTDF form) and self-checks of the
  draft's published numbers. Never imports `capex`.
- Part 2 (skipped until Gate 3): model-facing tests P5a-P5f, health checks, mutations M7-M10. Each place where the
  interface is not yet specified carries a `# SPEC-GAP:` comment; grep for it to build the W-spec checklist.
Un-skip by deleting the module-level `pytestmark` once gate-3.md is approved and `tx.model=dcpf` exists; move the file
to `tests/` and resolve the SPEC-GAPs. Never loosen a tolerance to make a test pass.
