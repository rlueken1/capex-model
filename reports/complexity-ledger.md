# Complexity ledger

One row per feature switch (docs/gates/README.md "Complexity value review"). Values reported; judgment by formulation lead + consulting reviewer, owner decides.
Backcast error and memory columns start when the scoreboard exists (Gate 5); performance-ledger starts Gate 4.

| Feature / switch | Gate | Delta backcast error | Delta rows / cols / nnz (pjm5, 72 h, vs transport) | Delta solve time (pjm5) | Delta memory | Delta client answers | Judgment |
|---|---|---|---|---|---|---|---|
| `tx.model = dcpf` angle form (default form) | 3 | n/a (no scoreboard) | +504 / +360 / +1,368 (1,224 / 1,517 / 3,672 vs 720 / 1,157 / 2,304) | 11.5 ms vs 3.2 ms median (3.6x; end-to-end run 0.22 s vs 0.18 s) | not measured | LMP differs by up to 20 $/MWh at a bus and system cost -15.3% under transport; congestion price-setter class CONGESTION_LOOP; reference-bus-dependent decomposition | proposed: keep as option, default stays `transport` (DECISIONS 29); owner decides (Gate 3 item 7, RTS-GMLC use) |
| `tx.model = dcpf` PTDF form (`tx.dcpf_form: ptdf`) | 3 | n/a | +144 / 0 / +2,592 (864 / 1,157 / 4,896) | 4.4 ms (1.4x) | not measured | identical to angle (P5b) | keep as option; angle form default |
Source: `reports/gate-3-evidence.md` section 8 (7 runs each, median). Tiny case: no scaling inference to PJM size.
