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


def assumptions_book(case: Case) -> str:
    """Markdown assumptions book for one run."""
    sections = [("Provenance mix", provenance_mix(case)), ("Dollar-year conversions to base "
                f"{case.base_dollar_year}$", case.conversions), ("Annualization table (formulation 5.2)",
                case.annualization), ("Counts", counts(case))]
    parts = [f"# Assumptions book: {case.case_id}"]
    for title, table in sections:
        parts += [f"## {title}", table.to_string(index=False) if len(table) else "(none)"]
    return "\n\n".join(parts) + "\n"
