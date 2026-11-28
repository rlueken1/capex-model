"""Hook 11: assumptions-book stub (provenance mix, dollar-year conversions, annualization table, counts)."""
from __future__ import annotations

import pandas as pd

from ..data import PROVENANCE_TABLES, Case


def provenance_mix(case: Case) -> pd.DataFrame:
    rows = [(name, m, c, n) for name in PROVENANCE_TABLES if name in case.tables
            for (m, c), n in case.tables[name].groupby(["method", "confidence"]).size().items()]
    return pd.DataFrame(rows, columns=["table", "method", "confidence", "rows"])


def counts(case: Case) -> pd.DataFrame:
    gen, st = case.gen, case.storage
    items = {
        "zones": len(case.zones), "periods": len(case.periods), "links": len(case.links.ids),
        "resources_thermal_vre": len(gen.ids), "resources_storage": len(st.ids),
        "candidates": int((gen.status == "candidate").sum() + (st.status == "candidate").sum()),
        "cfix_overrides": int((case.annualization["basis"] == "cfix_override").sum()) if len(case.annualization) else 0,
        "availability_values_zeroed": case.n_avail_zeroed, "weight_sum_blocks": float(case.w.sum())}
    return pd.DataFrame({"item": list(items), "value": list(items.values())})


TOY_BANNER = "Toy case: all inputs assumed; numbers are illustrative, not PJM estimates."


def is_toy(case: Case) -> bool:
    """True when no input cell has method observed, derived or estimated."""
    return not any(case.tables[name]["method"].isin(["observed", "derived", "estimated"]).any()
                   for name in PROVENANCE_TABLES if name in case.tables)


def dc_link_lines(case: Case) -> list[str]:
    """Header lines for controllable DC links (formulation 7.4a.12): treatment, and the lossless-link assumption."""
    if case.excluded_links:
        return [f"- tx.dc_links: exclude (dc rows dropped: {', '.join(case.excluded_links)})"]
    dc = [i for i, is_dc in zip(case.links.ids, case.links.is_dc) if is_dc]
    return [f"- tx.dc_links: controllable ({', '.join(dc)}; lossless, source resistance ignored)"] if dc else []


def run_header(case: Case, run_id: str, fingerprint: str) -> list[str]:
    """Run header (data-sources.md, assumptions book item 1), with the toy banner when applicable."""
    lines = [f"- run_id: {run_id}", f"- fingerprint: {fingerprint}", f"- case: {case.case_id}",
             f"- base dollar year: {case.base_dollar_year}", *dc_link_lines(case)]
    return lines + ([TOY_BANNER] if is_toy(case) else [])


def assumptions_book(case: Case, run_id: str, fingerprint: str) -> str:
    """Markdown assumptions book for one run."""
    sections = [("Provenance mix", provenance_mix(case)), ("Dollar-year conversions to base "
                f"{case.base_dollar_year}$", case.conversions), ("Annualization table (formulation 5.2)",
                case.annualization), ("Counts", counts(case))]
    parts = [f"# Assumptions book: {case.case_id}", "\n".join(run_header(case, run_id, fingerprint))]
    for title, table in sections:
        parts += [f"## {title}", table.to_string(index=False) if len(table) else "(none)"]
    return "\n\n".join(parts) + "\n"
