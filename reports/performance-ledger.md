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
| pjm5bus | pjm5-dcpf | 1,224 | 1,517 | 3,672 | 0.0103 | 7 | 117 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc_px | R4-F | 1,370,304 | 1,405,593 | 3,857,838 | 251.7 | 1 | 2313 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |
| rts_gmlc | R4-F | 1,405,440 | 1,440,732 | 3,975,461 | 225.8 | 1 | 2709 | simplex | on | 1.16.0 | Linux x86_64 2 cpu | 8722664a4e0331a86257e2b6d8d8d869ead71f8b |  |  |

Not in the table (the writer drops free text on rewrite; values in `reports/gate-4-evidence.md` section 9): R4-F on GitHub Actions (run 46095301368): rts_gmlc wall 169 s, solve 148.4 s, 2,725 MB; rts_gmlc_px wall 174 s, solve 151 s, 2,292 MB. R4-NF (rts_gmlc_nodal, dcpf): did not finish within the 30-min job limit (run 46095301368); owner question open. Window and R4-F rows above are the local 2-cpu sandbox; previous-gate columns empty (no RTS run before Gate 4); pjm5 dcpf angle 10.3 ms vs Gate 3 11.5 ms.
