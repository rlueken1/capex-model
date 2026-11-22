"""Case loading and validation (docs/data-schema.md sections 1-3, 6) into dense arrays."""
from __future__ import annotations

import calendar
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from . import FORMULATION_VERSION, SCHEMA_VERSION, econ
from .config import Tolerances

T = 72
AVAIL_ZERO_BELOW = 1e-3
XMAX_SENTINEL = 1e6
PROV = ["source_id", "vintage", "retrieved", "method", "basis", "confidence"]
METHODS = {"observed", "derived", "estimated", "assumed"}
CONFIDENCE = {"high", "medium", "low"}
RESOURCE_COSTS = ["vom_usd_mwh", "mc_override_usd_mwh", "fom_usd_mw_yr", "fom_usd_mwh_yr", "capex_usd_mw",
                  "capex_usd_mwh", "cfix_override_usd_mw_yr", "cfix_e_override_usd_mwh_yr"]
# table -> (required columns, optional columns, key columns)
SCHEMA: dict[str, tuple[list[str], list[str], list[str]]] = {
    "periods": (["period_id", "weight_blocks", "rep_kind", "days_represented"],
                ["source_start_date", "forced_reason", "cluster_size_blocks"], ["period_id"]),
    "load": (["zone", "period_id", "t", "demand_mw"], [], ["zone", "period_id", "t"]),
    "load_meta": (["zone", "net_of_btm", "year"] + PROV, ["est_level"], ["zone"]),
    "zones": (["zone_id", "name", "rto"], ["state_shares_ref", "reserve_area"] + PROV + ["est_level"], ["zone_id"]),
    "links": (["link_id", "zone_from", "zone_to", "ntc_fwd_mw", "ntc_rev_mw"] + PROV,
              ["dollar_year", "est_level"], ["link_id"]),
    "resources": (["resource_id", "zone", "type", "tech", "status"] + PROV,
                  ["fuel", "k0_mw", "e0_mwh", "xmax_mw", "xmax_mwh", "heat_rate_mmbtu_mwh", "life_yr",
                   "finance_class", "construction_profile_id", "eta_c_frac", "eta_d_frac", "selfdis_frac_h",
                   "dur_min_h", "dur_max_h", "long_duration", "dollar_year", "est_level"] + RESOURCE_COSTS,
                  ["resource_id"]),
    "finance": (["finance_class", "mode"] + PROV,
                ["wacc_real_frac", "wacc_nominal_frac", "inflation_frac", "pff", "debt_frac", "debt_rate_nominal",
                 "equity_rate_nominal", "tax_rate", "macrs_class_yr", "est_level"], ["finance_class"]),
    "construction_profiles": (["profile_id", "k", "share_phi"], [], ["profile_id", "k"]),
    "availability": (["resource_id", "period_id", "t", "availability_frac"], [], ["resource_id", "period_id", "t"]),
    "availability_meta": (["resource_id"] + PROV, ["profile_year", "weather_year", "est_level"], ["resource_id"]),
    "fuel_prices": (["fuel_hub", "period_id", "t", "price_usd_mmbtu"], [], ["fuel_hub", "period_id", "t"]),
    "fuel_prices_meta": (["fuel_hub", "dollar_year", "price_basis", "license_class"] + PROV, ["est_level"],
                         ["fuel_hub"]),
    "fuel_map": (["fuel", "fuel_hub"], ["zone"], ["fuel"]),
    "deflator": (["year", "gdp_deflator_index", "is_projection"] + PROV, ["est_level"], ["year"]),
    "sources": (["source_id", "description"], [], ["source_id"]),
}
REQUIRED_TABLES = ["periods", "load", "load_meta", "zones", "resources", "finance", "deflator", "sources"]
PROVENANCE_TABLES = ["load_meta", "links", "resources", "finance", "availability_meta", "fuel_prices_meta", "deflator"]


class DataError(ValueError):
    """Raised by the loader for any validation failure (no LP is built)."""


@dataclass(frozen=True)
class Gen:
    """Thermal and VRE resources (index g)."""
    ids: tuple[str, ...]
    zone: np.ndarray
    kind: np.ndarray       # "TH" | "VRE"
    tech: np.ndarray
    fuel: np.ndarray
    status: np.ndarray
    k0: np.ndarray         # MW
    xmax: np.ndarray       # MW (may be inf)
    cfix: np.ndarray       # $/MW-yr of new capacity (0 for existing)
    fom0: np.ndarray       # $/yr: FOM_r K0_r (part of Z0)
    mc: np.ndarray         # (G,P,T) $/MWh
    avail: np.ndarray      # (G,P,T)


@dataclass(frozen=True)
class Storage:
    """Storage resources (index s)."""
    ids: tuple[str, ...]
    zone: np.ndarray
    tech: np.ndarray
    status: np.ndarray
    p0: np.ndarray
    e0: np.ndarray
    xp_max: np.ndarray
    xe_max: np.ndarray
    eta_c: np.ndarray
    eta_d: np.ndarray
    sigma: np.ndarray
    dur_lo: np.ndarray     # NaN = no bound
    dur_hi: np.ndarray
    vom: np.ndarray
    cp: np.ndarray
    ce: np.ndarray
    fom0: np.ndarray       # $/yr: FOM^P P0 + FOM^E E0


@dataclass(frozen=True)
class Links:
    ids: tuple[str, ...]
    origin: np.ndarray
    end: np.ndarray
    f_plus: np.ndarray
    f_minus: np.ndarray


@dataclass(frozen=True)
class Case:
    case_id: str
    formulation_version: str
    base_dollar_year: int
    model_year: int
    zones: tuple[str, ...]
    periods: tuple[str, ...]
    w: np.ndarray                  # (P,) blocks
    demand: np.ndarray             # (Z,P,T) MW
    voll: float
    gen: Gen
    storage: Storage
    links: Links
    tolerances: Tolerances
    switches: dict
    solver_config: dict
    seed: int
    config: dict                   # parsed manifest (fingerprint input)
    tables: dict[str, pd.DataFrame]          # tables exactly as read (fingerprint input)
    annualization: pd.DataFrame
    conversions: pd.DataFrame      # dollar-year conversions applied
    n_avail_zeroed: int


def days_in_year(year: int) -> int:
    return 366 if calendar.isleap(year) else 365


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_manifest(case_dir: Path) -> dict:
    manifest = yaml.safe_load((case_dir / "case.yaml").read_text())
    required = ["case_id", "schema_version", "formulation_version", "base_dollar_year", "model_year", "dt_h",
                "tables", "voll_usd_mwh", "voll_dollar_year"]
    missing = [k for k in required if k not in manifest]
    if missing:
        raise DataError(f"case.yaml missing keys {missing}")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise DataError(f"schema_version {manifest['schema_version']} != {SCHEMA_VERSION}")
    if manifest["formulation_version"] != FORMULATION_VERSION:
        raise DataError(f"formulation_version {manifest['formulation_version']} != {FORMULATION_VERSION}")
    if float(manifest["dt_h"]) != 1.0:
        raise DataError("dt_h must be 1.0 (formulation 1.1)")
    return manifest


def read_tables(case_dir: Path, manifest: dict) -> dict[str, pd.DataFrame]:
    """Read every listed table, verifying sha256 when the manifest gives one."""
    tables: dict[str, pd.DataFrame] = {}
    for name, entry in manifest["tables"].items():
        if name not in SCHEMA:
            raise DataError(f"unknown table '{name}'")
        path = case_dir / entry["file"]
        if "sha256" in entry and _sha256(path) != entry["sha256"]:
            raise DataError(f"sha256 mismatch for {entry['file']}")
        tables[name] = pd.read_csv(path)
    missing = [n for n in REQUIRED_TABLES if n not in tables]
    if missing:
        raise DataError(f"missing tables {missing}")
    return tables


def check_schema(tables: dict[str, pd.DataFrame]) -> None:
    """Required columns present, no unknown columns (except x_ prefix), keys unique, no nulls in required."""
    for name, df in tables.items():
        required, optional, keys = SCHEMA[name]
        absent = [c for c in required if c not in df.columns]
        unknown = [c for c in df.columns if c not in required + optional and not c.startswith("x_")]
        if absent or unknown:
            raise DataError(f"{name}: missing columns {absent}, unknown columns {unknown}")
        if df[required].isna().any().any():
            raise DataError(f"{name}: null in required columns")
        if df.duplicated(keys).any():
            raise DataError(f"{name}: duplicate keys {keys}")


def check_provenance(tables: dict[str, pd.DataFrame]) -> None:
    """Provenance fields P on every row of value-bearing tables (data-schema section 6.7)."""
    sources = set(tables["sources"]["source_id"])
    today = date.today()
    for name in PROVENANCE_TABLES:
        if name not in tables:
            continue
        df = tables[name]
        bad = ~df["method"].isin(METHODS) | ~df["confidence"].isin(CONFIDENCE)
        bad |= (df["method"] == "assumed") & (df["confidence"] == "high")
        bad |= ~df["source_id"].isin(sources)
        level = df["est_level"] if "est_level" in df.columns else pd.Series(np.nan, index=df.index)
        bad |= df["method"].isin(["estimated", "derived"]) & (~level.isin([1, 2, 3, 4]) | df["basis"].isna())
        if bad.any() or pd.to_datetime(df["retrieved"]).dt.date.gt(today).any():
            raise DataError(f"{name}: invalid provenance on rows {list(df.index[bad])}")


def read_deflator(tables: dict[str, pd.DataFrame], base_year: int) -> econ.Deflator:
    df = tables["deflator"]
    return econ.Deflator(index=dict(zip(df["year"], df["gdp_deflator_index"])),
                         is_projection=dict(zip(df["year"], df["is_projection"])), base_year=base_year)


def check_periods(tables: dict[str, pd.DataFrame], model_year: int) -> np.ndarray:
    """Weight identity, floor and days cross-check (formulation 1.2). Returns w (P,)."""
    df = tables["periods"]
    w = df["weight_blocks"].to_numpy(float)
    if abs(w.sum() - days_in_year(model_year) / 3.0) > 1e-9:
        raise DataError(f"sum of weights {w.sum()!r} != D_y/3 = {days_in_year(model_year) / 3.0!r}")
    if (w < 1.0).any():
        raise DataError("weight floor violated: w_p >= 1 required")
    if (np.abs(df["days_represented"].to_numpy(float) - 3 * w) > 1e-9).any():
        raise DataError("days_represented != 3 w_p")
    return w


def _full_grid(df: pd.DataFrame, key: str, periods: list[str], name: str) -> None:
    """Every (key, period, t=1..72) present exactly once."""
    expected = len(df[key].unique()) * len(periods) * T
    ok = len(df) == expected and set(df["period_id"]) <= set(periods) and df["t"].between(1, T).all()
    if not ok:
        raise DataError(f"{name}: must cover every {key} x period x t=1..{T} exactly once")


def _grid(df: pd.DataFrame, key: str, ids: list[str], periods: list[str], value: str) -> np.ndarray:
    """Pivot a long (key, period_id, t) table into a dense (len(ids), P, T) array."""
    out = np.full((len(ids), len(periods), T), np.nan)
    ix = {k: i for i, k in enumerate(ids)}
    pix = {p: i for i, p in enumerate(periods)}
    out[df[key].map(ix).to_numpy(), df["period_id"].map(pix).to_numpy(), df["t"].to_numpy(int) - 1] = df[value]
    return out


def _factors(df: pd.DataFrame, deflator: econ.Deflator, cost_cols: list[str], name: str) -> np.ndarray:
    """Per-row deflator factor; rows with any cost value need a dollar_year (data-schema 6.6)."""
    has_cost = df[[c for c in cost_cols if c in df.columns]].notna().any(axis=1)
    if "dollar_year" not in df.columns:
        if has_cost.any():
            raise DataError(f"{name}: cost values without dollar_year")
        return np.ones(len(df))
    if (has_cost & df["dollar_year"].isna()).any():
        raise DataError(f"{name}: cost without dollar_year on rows {list(df.index[has_cost & df['dollar_year'].isna()])}")
    years = df["dollar_year"].fillna(deflator.base_year).astype(int)
    return np.asarray(econ.deflator_factor(years.to_numpy(), deflator))


def _num(df: pd.DataFrame, col: str, default: float = np.nan) -> np.ndarray:
    return df[col].to_numpy(float) if col in df.columns else np.full(len(df), default)


def _num0(df: pd.DataFrame, col: str) -> np.ndarray:
    """Numeric column with nulls as 0 (infinity preserved)."""
    return np.nan_to_num(_num(df, col), nan=0.0, posinf=np.inf, neginf=-np.inf)


def check_resources(res: pd.DataFrame, zones: set[str], finance: set[str], fuel_map: set[str]) -> None:
    """Gate-1 data rule and referential integrity for resources (data-schema 6.4-6.5)."""
    if not res["zone"].isin(zones).all() or not res["type"].isin(["TH", "VRE", "ST"]).all() \
            or not res["status"].isin(["existing", "candidate"]).all():
        raise DataError("resources: unknown zone, type or status")
    xmax = np.nan_to_num(np.concatenate([_num(res, "xmax_mw", 0), _num(res, "xmax_mwh", 0)]), posinf=0)
    if (xmax >= XMAX_SENTINEL).any():
        raise DataError("resources: finite xmax >= 1e6 looks like a big-M sentinel; use inf")
    for _, r in res.iterrows():
        _check_resource_row(r, finance, fuel_map)


def _check_resource_row(r: pd.Series, finance: set[str], fuel_map: set[str]) -> None:
    rid, kind, existing = r["resource_id"], r["type"], r["status"] == "existing"
    g = lambda c: r.get(c, np.nan)  # noqa: E731
    cap_mw, cap_mwh = np.nan_to_num(g("k0_mw")), np.nan_to_num(g("e0_mwh"))
    xmax_mw, xmax_mwh = np.nan_to_num(g("xmax_mw")), np.nan_to_num(g("xmax_mwh"))
    if existing and not (cap_mw > 0 and xmax_mw == 0 and xmax_mwh == 0):
        raise DataError(f"{rid}: existing needs k0>0 and xmax=0")
    if not existing and not (cap_mw == 0 and cap_mwh == 0 and xmax_mw > 0 and (kind != "ST" or xmax_mwh > 0)):
        raise DataError(f"{rid}: candidate needs k0=0 and xmax>0")
    if kind == "TH" and pd.isna(g("mc_override_usd_mwh")) and (
            pd.isna(g("heat_rate_mmbtu_mwh")) or g("heat_rate_mmbtu_mwh") <= 0 or g("fuel") not in fuel_map):
        raise DataError(f"{rid}: thermal needs mc_override or heat rate with a mapped fuel")
    if kind == "ST":
        etas = [g("eta_c_frac"), g("eta_d_frac")]
        if any(pd.isna(e) or not 0 < e <= 1 for e in etas) or (existing and cap_mwh <= 0):
            raise DataError(f"{rid}: storage needs eta in (0,1] and e0>0 when existing")
        if not pd.isna(g("selfdis_frac_h")) and not 0 <= g("selfdis_frac_h") < 1:
            raise DataError(f"{rid}: selfdis_frac_h outside [0,1)")
        if not pd.isna(g("dur_min_h")) and not pd.isna(g("dur_max_h")) and g("dur_min_h") > g("dur_max_h"):
            raise DataError(f"{rid}: dur_min_h > dur_max_h")
    if not existing:
        _check_candidate_cost(r, kind, finance)


def _check_candidate_cost(r: pd.Series, kind: str, finance: set[str]) -> None:
    g = lambda c: r.get(c, np.nan)  # noqa: E731
    parts = [("capex_usd_mw", "cfix_override_usd_mw_yr")] + ([("capex_usd_mwh", "cfix_e_override_usd_mwh_yr")]
                                                             if kind == "ST" else [])
    for capex, override in parts:
        if pd.isna(g(override)) and (pd.isna(g(capex)) or pd.isna(g("life_yr")) or g("finance_class") not in finance):
            raise DataError(f"{r['resource_id']}: candidate needs ({capex}, life_yr, finance_class) or {override}")


def finance_params(row: pd.Series) -> tuple[float, float]:
    """Real WACC r and PFF for a finance class (formulation 5.2)."""
    g = lambda c: row.get(c, np.nan)  # noqa: E731
    inflation = 0.0 if pd.isna(g("inflation_frac")) else g("inflation_frac")
    derive = [g(c) for c in ("debt_frac", "debt_rate_nominal", "equity_rate_nominal", "tax_rate")]
    if pd.notna(g("wacc_real_frac")):
        r = float(g("wacc_real_frac"))
    elif pd.notna(g("wacc_nominal_frac")):
        r = econ.fisher_real_rate(g("wacc_nominal_frac"), inflation)
    elif not any(pd.isna(d) for d in derive):
        r = econ.fisher_real_rate(econ.nominal_wacc(*derive), inflation)
    else:
        raise DataError(f"finance class {row['finance_class']}: no WACC")
    if row["mode"] == "simple_crf":
        return r, 1.0
    if row["mode"] != "atb_pff":
        raise DataError(f"finance class {row['finance_class']}: unknown mode {row['mode']}")
    if pd.notna(g("pff")):
        return r, float(g("pff"))
    if any(pd.isna(d) for d in derive) or pd.isna(g("macrs_class_yr")):
        raise DataError(f"finance class {row['finance_class']}: atb_pff needs pff or tax/debt/equity/macrs inputs")
    return r, econ.atb_pff(derive[3], int(g("macrs_class_yr")), econ.nominal_wacc(*derive))


def _annualize_part(label: str, comp: str, capex: float, override: float, fom: float, r_row: pd.Series,
                    life: float, profile: list[float] | None, dollar_year: float, factor: float) -> dict:
    """One annualization-table row; cfix = ANN + FOM, or the override (bypass, flagged)."""
    base = {"resource_id": label, "component": comp, "dollar_year_in": dollar_year, "deflator_factor": factor,
            "fom": fom * factor}
    if pd.notna(override):
        return {**base, "I": np.nan, "r": np.nan, "n": np.nan, "kappa": np.nan, "pff": np.nan, "crf": np.nan,
                "ann": np.nan, "cfix": override * factor, "basis": "cfix_override"}
    r, pff = finance_params(r_row)
    ann = econ.annualize(capex * factor, r, life, profile, pff)
    return {**base, "I": capex * factor, "r": r, "n": life, "kappa": ann.kappa, "pff": ann.pff, "crf": ann.crf,
            "ann": ann.ann, "cfix": ann.ann + fom * factor, "basis": "annualize"}


def build_annualization(res: pd.DataFrame, factors: np.ndarray, tables: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Annualization table for every candidate (section 5.2 print); existing units carry no capex."""
    fin = tables["finance"].set_index("finance_class")
    prof = tables.get("construction_profiles")
    rows = []
    for (_, r), f in zip(res.iterrows(), factors):
        if r["status"] != "candidate":
            continue
        g = lambda c: r.get(c, np.nan)  # noqa: E731
        profile = None
        if pd.notna(g("construction_profile_id")):
            profile = prof[prof["profile_id"] == r["construction_profile_id"]].sort_values("k")["share_phi"].tolist()
        fin_row = fin.loc[g("finance_class")].copy() if pd.notna(g("finance_class")) else None
        if fin_row is not None:
            fin_row["finance_class"] = g("finance_class")
        common = dict(r_row=fin_row, life=g("life_yr"), profile=profile, dollar_year=g("dollar_year"), factor=f)
        rows.append(_annualize_part(r["resource_id"], "P" if r["type"] == "ST" else "cap", g("capex_usd_mw"),
                                    g("cfix_override_usd_mw_yr"), np.nan_to_num(g("fom_usd_mw_yr")), **common))
        if r["type"] == "ST":
            rows.append(_annualize_part(r["resource_id"], "E", g("capex_usd_mwh"), g("cfix_e_override_usd_mwh_yr"),
                                        np.nan_to_num(g("fom_usd_mwh_yr")), **common))
    return pd.DataFrame(rows)


def _ann_cfix(ann: pd.DataFrame, ids: list[str], comp: str) -> np.ndarray:
    sel = ann[ann["component"] == comp].set_index("resource_id")["cfix"] if len(ann) else pd.Series(dtype=float)
    return np.array([sel.get(i, 0.0) for i in ids])


def fuel_price_grid(tables: dict[str, pd.DataFrame], periods: list[str], deflator: econ.Deflator
                    ) -> dict[str, np.ndarray]:
    """phi_{f,p,t} by hub in base-year $/MMBtu (formulation 1.4)."""
    if "fuel_prices" not in tables:
        return {}
    meta = tables["fuel_prices_meta"].set_index("fuel_hub")
    out = {}
    for hub, df in tables["fuel_prices"].groupby("fuel_hub"):
        _full_grid(df, "fuel_hub", periods, f"fuel_prices[{hub}]")
        out[hub] = _grid(df, "fuel_hub", [hub], periods, "price_usd_mmbtu")[0] * econ.deflator_factor(
            int(meta.loc[hub, "dollar_year"]), deflator)
    return out


def build_availability(res: pd.DataFrame, tables: dict[str, pd.DataFrame], periods: list[str]
                       ) -> tuple[np.ndarray, int]:
    """A_{r,p,t}: default 1, explicit rows override, required for VRE; < 1e-3 zeroed and counted."""
    ids = list(res["resource_id"])
    avail = np.ones((len(ids), len(periods), T))
    if "availability" in tables:
        df = tables["availability"]
        if not df["resource_id"].isin(ids).all() or not df["availability_frac"].between(0, 1).all():
            raise DataError("availability: unknown resource or value outside [0,1]")
        for rid, sub in df.groupby("resource_id"):
            _full_grid(sub, "resource_id", periods, f"availability[{rid}]")
            avail[ids.index(rid)] = _grid(sub, "resource_id", [rid], periods, "availability_frac")[0]
    given = set(tables["availability"]["resource_id"]) if "availability" in tables else set()
    missing = [i for i, t in zip(ids, res["type"]) if t == "VRE" and i not in given]
    if missing:
        raise DataError(f"availability required for every VRE: missing {missing}")
    tiny = (avail < AVAIL_ZERO_BELOW) & (avail > 0)
    avail[avail < AVAIL_ZERO_BELOW] = 0.0
    return avail, int(tiny.sum())


def build_gen(res: pd.DataFrame, factors: np.ndarray, ann: pd.DataFrame, tables: dict[str, pd.DataFrame],
              zone_ix: dict[str, int], periods: list[str], deflator: econ.Deflator) -> tuple[Gen, int]:
    mask = (res["type"] != "ST").to_numpy()
    sub, f = res[mask].reset_index(drop=True), factors[mask]
    avail, n_zeroed = build_availability(sub, tables, periods)
    phi = fuel_price_grid(tables, periods, deflator)
    fuel_map = dict(zip(tables["fuel_map"]["fuel"], tables["fuel_map"]["fuel_hub"])) if "fuel_map" in tables else {}
    vom = np.nan_to_num(_num(sub, "vom_usd_mwh")) * f
    hr = np.nan_to_num(_num(sub, "heat_rate_mmbtu_mwh"))
    override = _num(sub, "mc_override_usd_mwh") * f
    mc = np.zeros((len(sub), len(periods), T))
    for i, row in sub.iterrows():
        if pd.notna(override[i]):
            mc[i] = override[i]
        else:
            fuel_cost = phi[fuel_map[row["fuel"]]] * hr[i] if row["fuel"] in fuel_map else 0.0
            mc[i] = fuel_cost + vom[i]
    ids = list(sub["resource_id"])
    fuel = sub["fuel"].fillna("none").to_numpy() if "fuel" in sub.columns else np.full(len(sub), "none")
    k0 = np.nan_to_num(_num(sub, "k0_mw"))
    xmax = _num0(sub, "xmax_mw")
    fom0 = np.nan_to_num(_num(sub, "fom_usd_mw_yr")) * f * k0
    gen = Gen(ids=tuple(ids), zone=sub["zone"].map(zone_ix).to_numpy(), kind=sub["type"].to_numpy(),
              tech=sub["tech"].to_numpy(), fuel=fuel, status=sub["status"].to_numpy(), k0=k0, xmax=xmax,
              cfix=_ann_cfix(ann, ids, "cap"), fom0=fom0, mc=mc, avail=avail)
    return gen, n_zeroed


def build_storage(res: pd.DataFrame, factors: np.ndarray, ann: pd.DataFrame, zone_ix: dict[str, int]) -> Storage:
    mask = (res["type"] == "ST").to_numpy()
    sub, f = res[mask].reset_index(drop=True), factors[mask]
    ids = list(sub["resource_id"])
    p0, e0 = np.nan_to_num(_num(sub, "k0_mw")), np.nan_to_num(_num(sub, "e0_mwh"))
    fom_p, fom_e = (np.nan_to_num(_num(sub, c)) * f for c in ("fom_usd_mw_yr", "fom_usd_mwh_yr"))
    return Storage(
        ids=tuple(ids), zone=sub["zone"].map(zone_ix).to_numpy(), tech=sub["tech"].to_numpy(),
        status=sub["status"].to_numpy(), p0=p0, e0=e0, xp_max=_num0(sub, "xmax_mw"),
        xe_max=_num0(sub, "xmax_mwh"), eta_c=_num(sub, "eta_c_frac"), eta_d=_num(sub, "eta_d_frac"),
        sigma=np.nan_to_num(_num(sub, "selfdis_frac_h")), dur_lo=_num(sub, "dur_min_h"), dur_hi=_num(sub, "dur_max_h"),
        vom=np.nan_to_num(_num(sub, "vom_usd_mwh")) * f, cp=_ann_cfix(ann, ids, "P"), ce=_ann_cfix(ann, ids, "E"),
        fom0=fom_p * p0 + fom_e * e0)


def build_links(tables: dict[str, pd.DataFrame], zone_ix: dict[str, int]) -> Links:
    df = tables.get("links", pd.DataFrame(columns=SCHEMA["links"][0]))
    if not (df["zone_from"].isin(zone_ix).all() and df["zone_to"].isin(zone_ix).all()):
        raise DataError("links: unknown zone")
    if (df["zone_from"] == df["zone_to"]).any() or (df[["ntc_fwd_mw", "ntc_rev_mw"]] < 0).any().any():
        raise DataError("links: endpoints must differ and NTC >= 0")
    return Links(ids=tuple(df["link_id"]), origin=df["zone_from"].map(zone_ix).to_numpy(int),
                 end=df["zone_to"].map(zone_ix).to_numpy(int), f_plus=df["ntc_fwd_mw"].to_numpy(float),
                 f_minus=df["ntc_rev_mw"].to_numpy(float))


def load_case(case_dir: str | Path) -> Case:
    """Read, validate and densify a case directory. Raises DataError on any violation."""
    case_dir = Path(case_dir)
    manifest = read_manifest(case_dir)
    tables = read_tables(case_dir, manifest)
    check_schema(tables)
    check_provenance(tables)
    base = int(manifest["base_dollar_year"])
    deflator = read_deflator(tables, base)
    w = check_periods(tables, int(manifest["model_year"]))
    periods = list(tables["periods"]["period_id"])
    zones = list(tables["zones"]["zone_id"])
    zone_ix = {z: i for i, z in enumerate(zones)}
    load = tables["load"]
    if not load["zone"].isin(zones).all() or set(load["zone"]) != set(zones):
        raise DataError("load: every zone needs load and no unknown zones")
    _full_grid(load, "zone", periods, "load")
    if (load["demand_mw"] < 0).any():
        raise DataError("load: demand_mw must be >= 0")
    res = tables["resources"]
    fuel_map = set(tables["fuel_map"]["fuel"]) if "fuel_map" in tables else set()
    check_resources(res, set(zones), set(tables["finance"]["finance_class"]), fuel_map)
    factors = _factors(res, deflator, RESOURCE_COSTS, "resources")
    ann = build_annualization(res, factors, tables)
    gen, n_zeroed = build_gen(res, factors, ann, tables, zone_ix, periods, deflator)
    voll_factor = econ.deflator_factor(int(manifest["voll_dollar_year"]), deflator)
    years = res["dollar_year"].dropna().astype(int) if "dollar_year" in res.columns else pd.Series(dtype=int)
    conv = pd.DataFrame({"dollar_year": sorted(set(years) | {int(manifest["voll_dollar_year"])})})
    conv["factor"] = econ.deflator_factor(conv["dollar_year"].to_numpy(), deflator)
    return Case(
        case_id=str(manifest["case_id"]), formulation_version=manifest["formulation_version"], base_dollar_year=base,
        model_year=int(manifest["model_year"]), zones=tuple(zones), periods=tuple(periods), w=w,
        demand=_grid(load, "zone", zones, periods, "demand_mw"), voll=float(manifest["voll_usd_mwh"]) * voll_factor,
        gen=gen, storage=build_storage(res, factors, ann, zone_ix), links=build_links(tables, zone_ix),
        tolerances=Tolerances(**manifest.get("tolerances", {})), switches=manifest.get("switches", {}),
        solver_config=manifest.get("solver", {}), seed=int(manifest.get("seed", 0)), config=manifest, tables=tables,
        annualization=ann, conversions=conv, n_avail_zeroed=n_zeroed)
