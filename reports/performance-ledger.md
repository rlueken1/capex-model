# Performance ledger

Written by `python -m capex ledger` (`capex/ledger.py`). One row per case x run; solve time is the median of `n` solves of the same LP; previous gate = the Gate 3 reference (reports/gate-3-evidence.md section 8) where one exists.

| case | run | rows | cols | nnz | solve s (median) | n | peak RSS MB | method | crossover | HiGHS | runner | git commit | previous gate s | ratio |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| rts_gmlc_px | R4-Z | 56,160 | 57,753 | 159,615 | 1.063 | 3 | 212 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_px_cp | R4-C | 55,440 | 55,593 | 156,015 | 1.208 | 3 | 211 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_nodal_px | R4-N | 124,920 | 151,353 | 399,015 | 27.97 | 3 | 406 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_nodal_px | R4-NP | 98,640 | 125,073 | 9,487,935 | 9.823 | 3 | 1313 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_nodal_px | R4-NX | 124,920 | 150,993 | 398,295 | 27.11 | 3 | 423 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_nodal | R4-NS | 126,360 | 152,796 | 403,862 | 30.1 | 3 | 456 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| pjm5bus | pjm5-dcpf | 1,224 | 1,517 | 3,672 | 0.01152 | 7 | 118 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e | 0.0115 | 1.00 |
| rts_gmlc_px | R4-F | 1,370,304 | 1,405,593 | 3,857,838 | 251.7 | 1 | 2313 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc | R4-F | 1,405,440 | 1,440,732 | 3,975,461 | 225.8 | 1 | 2709 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| T1 | T1 | 216 | 218 | 504 | 0.0005947 | 7 | 115 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T2a | T2a | 432 | 436 | 1,296 | 0.002798 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T2b | T2b | 434 | 436 | 1,300 | 0.002026 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T2c | T2c | 434 | 436 | 1,300 | 0.00193 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T3a | T3a | 216 | 218 | 504 | 0.0003727 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T3b | T3b | 216 | 218 | 504 | 0.0003868 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| T4 | T4 | 288 | 362 | 720 | 0.0007485 | 7 | 116 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e |  |  |
| pjm5bus | pjm5-transport | 720 | 1,157 | 2,304 | 0.003691 | 7 | 117 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e | 0.0032 | 1.15 |
| pjm5bus | pjm5-ptdf | 864 | 1,157 | 4,896 | 0.003981 | 7 | 119 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 36e791a186c6d5abed41d46a5b305e4624840f5e | 0.0044 | 0.90 |

Not in the table (the writer drops free text on rewrite; values in `reports/gate-4-evidence.md` section 9): R4-F on GitHub Actions (run 46095301368): rts_gmlc wall 169 s, solve 148.4 s, 2,725 MB; rts_gmlc_px wall 174 s, solve 151 s, 2,292 MB. R4-NF (rts_gmlc_nodal, dcpf): did not finish within the 30-min job limit (run 46095301368); owner question open. Window and R4-F rows above are the local 2-cpu sandbox; previous-gate columns empty (no RTS run before Gate 4).

T1–T4 and pjm5 rows (G4-7-fix3, F4-4; median of 7 solves, each row in its own process, local 2-cpu sandbox, 2026-11-28): T1, T2a, T2b, T2c, T3a, T3b, T4 previous gate s = n/a (not measured at Gate 3); size identity holds against the golden LP shapes (`tests/golden/gate2/<case>/conditioning.json` rows/cols/nnz, all 7 equal). pjm5 previous gate s from gate-3-evidence section 8: transport 3.2 ms (720 x 1,157, nnz 2,304), dcpf angle 11.5 ms (1,224 x 1,517, nnz 3,672), dcpf ptdf 4.4 ms (864 x 1,157, nnz 4,896); all three sizes identical to Gate 3 (angle/ptdf also equal `tests/golden/gate3/pjm5bus/{angle,ptdf}/conditioning.json`), time ratios 1.15 / 1.00 / 0.90, all within the README rule (size identical, time <= 2x). Run labels: pjm5-transport = `tx.model: transport`; pjm5-dcpf = case default (angle); pjm5-ptdf = `tx.dcpf_form: ptdf`, `tx.ref_bus: A`. Sub-millisecond times are noise-dominated. Checked by `tests/test_g4_ledger_rows.py`.
