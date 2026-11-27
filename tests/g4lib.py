"""Gate 4 verifier library (G4-3). Written from docs/gates/gate-4.md and docs/formulation.md F-0.4 only.

* `make_fixture`: builds small F-0.4 fixture cases (pjm5 + DC link, two AC islands joined by one DC link, pjm5 + storage)
  by copying cases/pjm5bus into a tmp dir and editing the CSVs (nothing here imports capex).
* `net_from_case` + `solve_net`: the INDEPENDENT route. A multi-hour DC-OPF with DC links, storage and islands,
  read from the case CSVs and solved with scipy.optimize.linprog(method="highs") in angle or PTDF form; never the capex
  builders. It returns primal values, LMPs, line duals mu (signed, mu f >= 0), DC-link duals, water values.
* `interval_lp`: the verifier's own S2 / case-(c) interval LP (formulation 7.4a.7), also via linprog.
Sign conventions (7.4a.5, 7.4a.12): f_l = b_l (theta_o - theta_e) with + = zone_from -> zone_to; pi = dCost/dD;
mu_l = pi_e(l) - pi_o(l) for a DC link, mu f >= 0; pi_n = lambda_i(n) - sum_{l in AC} H_{l,n} mu_l.
"""
from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.sparse as sp
import yaml
from scipy.optimize import linprog

REPO = Path(__file__).resolve().parents[1]
PJM5 = REPO / "cases" / "pjm5bus"
T = 72
W1 = 365.0 / 3.0                                      # pjm5: model_year 2025, D_y = 365 (7.4a.11)
LETTERS = list("ABCDE")
PROV = dict(source_id="pjm5", vintage="matpower-b6c85b0", retrieved="2026-11-27", method="assumed",
            basis="Gate 4 verifier fixture (G4-3), declared F-0.4", confidence="low")


# ====================================================================================== fixture construction
def _sha(path: Path) -> str:
    import hashlib
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(tmp: Path, name: str = "fx") -> Path:
    """Copy cases/pjm5bus to tmp/cases/<name>, data -> repo data (so '../../data/...' resolves)."""
    dst = Path(tmp) / "cases" / name
    shutil.copytree(PJM5, dst)
    if not (Path(tmp) / "data").exists():
        (Path(tmp) / "data").symlink_to(REPO / "data")
    return dst


def repin(cd: Path) -> None:
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    for spec in cfg.get("tables", {}).values():
        f = spec.get("file", "")
        if "sha256" in spec and not f.startswith(".."):
            spec["sha256"] = _sha(cd / f)
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))


def dc_row(link_id, a, b, fwd, rev=None) -> dict:
    return dict(link_id=link_id, zone_from=a, zone_to=b, ntc_fwd_mw=float(fwd),
                ntc_rev_mw=float(fwd if rev is None else rev), reactance_pu=np.nan, base_mva=np.nan,
                link_type="dc", **PROV)


def storage_row(rid="batt", zone="D", p=50.0, e=200.0, eta_c=0.9, eta_d=0.9, sigma=0.0, vom=0.0) -> dict:
    return dict(resource_id=rid, zone=zone, type="ST", tech="battery", status="existing", k0_mw=p, xmax_mw=0.0,
                dollar_year=2024, e0_mwh=e, xmax_mwh=0.0, vom_usd_mwh=vom, eta_c_frac=eta_c, eta_d_frac=eta_d,
                selfdis_frac_h=sigma, **PROV)


def make_fixture(tmp: Path, *, name="fx", dc=(), drop_links=(), form="angle", ref=None, switches=None,
                 storage=(), load_factors=None, gen_edit=None, formulation="F-0.4", audit_profile=None,
                 link_type_col=None, tx="dcpf") -> Path:
    """pjm5 + optional DC links / storage / load profile; declared F-0.4. `dc` = iterable of dc_row dicts."""
    cd = stage(tmp, name)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    cfg["formulation_version"] = formulation
    if switches is not None:
        cfg["switches"] = switches
    elif tx == "dcpf":
        sw = {"tx.model": "dcpf", "tx.dcpf_form": form}
        if ref is not None:
            sw["tx.ref_bus"] = ref
        cfg["switches"] = sw
    else:
        cfg["switches"] = {"tx.model": tx}
    if audit_profile:
        cfg["audit_profile"] = audit_profile
    ln = pd.read_csv(cd / "links.csv")
    if drop_links:
        ln = ln[~ln["link_id"].isin(drop_links)]
    if link_type_col or (link_type_col is None and dc):
        ln["link_type"] = "ac"
    if dc:
        ln = pd.concat([ln, pd.DataFrame(list(dc))], ignore_index=True)
    ln.to_csv(cd / "links.csv", index=False)
    rs = pd.read_csv(cd / "resources.csv")
    if gen_edit is not None:
        rs = gen_edit(rs)
    if storage:
        rs = pd.concat([rs, pd.DataFrame(list(storage))], ignore_index=True)
    rs.to_csv(cd / "resources.csv", index=False)
    if load_factors is not None:
        ld = pd.read_csv(cd / "load.csv")
        ld["demand_mw"] = ld["demand_mw"] * np.asarray(load_factors, float)[ld["t"].to_numpy() - 1]
        ld.to_csv(cd / "load.csv", index=False)
    (cd / "case.yaml").write_text(yaml.safe_dump(cfg, sort_keys=False))
    repin(cd)
    return cd


# ====================================================================================== reading a case (independent)
@dataclass
class Net:
    zones: list
    load: np.ndarray                    # (T, N)
    gbus: np.ndarray
    gmax: np.ndarray
    gcost: np.ndarray
    gid: list
    lfrom: np.ndarray                   # AC lines
    lto: np.ndarray
    lx: np.ndarray                      # pu
    lbase: np.ndarray
    lrate: np.ndarray                   # inf = unlimited
    lid: list
    kfrom: np.ndarray                   # DC links
    kto: np.ndarray
    kfwd: np.ndarray
    krev: np.ndarray
    kid: list
    st: list = field(default_factory=list)   # dicts: id, bus, P, E, eta_c, eta_d, sigma, vom
    refs: dict = field(default_factory=dict)  # island index -> bus index
    form: str = "angle"

    @property
    def N(self):
        return len(self.zones)

    @property
    def b(self):
        return self.lbase / self.lx            # MW/rad (base_mva / x_pu, 7.4a.2)

    def islands(self) -> list[list[int]]:
        """Components of (N, AC lines), ordered by smallest zone index (7.4a.2)."""
        par = list(range(self.N))

        def find(i):
            while par[i] != i:
                par[i] = par[par[i]]
                i = par[i]
            return i
        for o, e in zip(self.lfrom, self.lto):
            par[find(int(o))] = find(int(e))
        comp: dict = {}
        for n in range(self.N):
            comp.setdefault(find(n), []).append(n)
        return sorted(comp.values(), key=lambda c: min(c))


def net_from_case(case_dir: Path, hours: int = T, form: str | None = None) -> Net:
    """Read the F-0.4 case CSVs directly (links.csv incl. link_type, resources.csv, load.csv, case.yaml)."""
    cd = Path(case_dir)
    cfg = yaml.safe_load((cd / "case.yaml").read_text())
    sw = cfg.get("switches") or {}
    zones = pd.read_csv(cd / "zones.csv")["zone_id"].tolist()
    zi = {z: i for i, z in enumerate(zones)}
    ld = pd.read_csv(cd / "load.csv")
    load = np.zeros((hours, len(zones)))
    ld = ld[ld["t"] <= hours]
    for z, g in ld.groupby("zone"):
        load[g["t"].to_numpy() - 1, zi[z]] = g["demand_mw"].to_numpy()
    rs = pd.read_csv(cd / "resources.csv")
    th = rs[rs["type"] == "TH"]
    st = []
    for _, r in rs[rs["type"] == "ST"].iterrows():
        st.append(dict(id=r["resource_id"], bus=zi[r["zone"]], P=float(r["k0_mw"]), E=float(r["e0_mwh"]),
                       eta_c=float(r["eta_c_frac"]), eta_d=float(r["eta_d_frac"]),
                       sigma=float(r.get("selfdis_frac_h") or 0.0), vom=float(r.get("vom_usd_mwh") or 0.0)))
    ln = pd.read_csv(cd / "links.csv")
    lt = ln["link_type"].fillna("ac") if "link_type" in ln.columns else pd.Series("ac", index=ln.index)
    drop_dc = sw.get("tx.dc_links") == "exclude"
    ac, dc = ln[lt == "ac"], ln[lt == "dc"]
    inf = lambda s: np.where(s.isna(), np.inf, s.to_numpy(float))
    net = Net(zones=zones, load=load, gbus=np.array([zi[z] for z in th["zone"]]), gmax=th["k0_mw"].to_numpy(float),
              gcost=th["mc_override_usd_mwh"].to_numpy(float), gid=th["resource_id"].tolist(),
              lfrom=np.array([zi[z] for z in ac["zone_from"]], int), lto=np.array([zi[z] for z in ac["zone_to"]], int),
              lx=ac["reactance_pu"].to_numpy(float), lbase=ac["base_mva"].to_numpy(float), lrate=inf(ac["ntc_fwd_mw"]),
              lid=ac["link_id"].tolist(),
              kfrom=np.array([zi[z] for z in dc["zone_from"]], int), kto=np.array([zi[z] for z in dc["zone_to"]], int),
              kfwd=inf(dc["ntc_fwd_mw"]), krev=inf(dc["ntc_rev_mw"]), kid=dc["link_id"].tolist(), st=st,
              form=form or sw.get("tx.dcpf_form", "angle"))
    if drop_dc:
        for a in ("kfrom", "kto", "kfwd", "krev"):
            setattr(net, a, getattr(net, a)[:0])
        net.kid = []
    refs = sw.get("tx.ref_bus")
    refs = [refs] if isinstance(refs, str) else list(refs or [])
    for k, isl in enumerate(net.islands()):
        named = [zi[z] for z in refs if zi[z] in isl]
        net.refs[k] = named[0] if named else min(isl)
    return net


def _ptdf_island(net: Net, isl: list[int], ref: int):
    """H (L_i, N): d f_l / d inj_n for lines of island, withdrawal at ref; zero columns outside. Returns (line idx, H)."""
    lines = [l for l in range(len(net.lx)) if net.lfrom[l] in isl]
    H = np.zeros((len(lines), net.N))
    if not lines:
        return lines, H
    A = np.zeros((len(lines), net.N))
    for r, l in enumerate(lines):
        A[r, net.lfrom[l]], A[r, net.lto[l]] = 1.0, -1.0
    b = net.b[lines]
    B = A.T @ np.diag(b) @ A
    keep = [n for n in isl if n != ref]
    X = np.zeros((net.N, net.N))
    if keep:
        X[np.ix_(keep, keep)] = np.linalg.inv(B[np.ix_(keep, keep)])
    return lines, (np.diag(b) @ A) @ X


def ptdf_full(net: Net):
    """H (L, N) over all islands, each with its reference bus."""
    H = np.zeros((len(net.lx), net.N))
    for k, isl in enumerate(net.islands()):
        lines, h = _ptdf_island(net, isl, net.refs[k])
        for r, l in enumerate(lines):
            H[l] = h[r]
    return H


# ====================================================================================== independent multi-hour LP
@dataclass
class Sol:
    net: Net
    obj_hr: float                     # sum over the T modelled hours of $/h (unweighted)
    g: np.ndarray                     # (T, G)
    f: np.ndarray                     # (T, L) AC flows
    fk: np.ndarray                    # (T, K) DC flows
    pi: np.ndarray                    # (T, N) LMP
    lam: np.ndarray                   # (T, N) lambda of the island of each bus
    mu: np.ndarray                    # (T, L)
    muk: np.ndarray                   # (T, K) from column-bound reduced cost
    inj: np.ndarray                   # (T, N) resource injection net of load (excludes DC flows)
    ch: np.ndarray = None
    dis: np.ndarray = None
    soc: np.ndarray = None
    v: np.ndarray = None              # (T, S) water value
    pwr_rho: np.ndarray = None        # (T, S) st_pwr rent (>= 0)

    @property
    def obj_annual(self):
        return self.obj_hr * W1


def solve_net(net: Net, hours: int = T, force_obj_max: float | None = None, sense_vec=None) -> Sol:
    """Independent LP. Variables per hour: g (G), theta (N) [angle form], fk (K), c,d,e (per storage); PTDF form drops theta.
    `sense_vec`/`force_obj_max` are used by uniqueness probes (min/max a linear functional at the optimal cost)."""
    G, N, L, K, S = len(net.gmax), net.N, len(net.lx), len(net.kfwd), len(net.st)
    angle = net.form == "angle"
    isl = net.islands()
    per = G + (N if angle else 0) + K + 3 * S
    og, oth = 0, G
    ok = G + (N if angle else 0)
    oc = ok + K
    nv = hours * per
    col = lambda t, o: t * per + o
    cost = np.zeros(nv)
    lb, ub = np.zeros(nv), np.full(nv, np.inf)
    for t in range(hours):
        cost[col(t, 0): col(t, 0) + G] = net.gcost
        ub[col(t, 0): col(t, 0) + G] = net.gmax
        if angle:
            lb[col(t, oth): col(t, oth) + N], ub[col(t, oth): col(t, oth) + N] = -np.inf, np.inf
            for k, i in enumerate(isl):
                lb[col(t, oth + net.refs[k])] = ub[col(t, oth + net.refs[k])] = 0.0
        for k in range(K):
            lb[col(t, ok + k)], ub[col(t, ok + k)] = -net.krev[k], net.kfwd[k]
        for s, st in enumerate(net.st):
            cost[col(t, oc + 3 * s + 1)] = st["vom"]                       # discharge VOM
            ub[col(t, oc + 3 * s + 2)] = st["E"]                           # soc <= E
    # equality rows: nodal balance (angle) or island balance (ptdf) + soc rows
    Aeq_r, Aeq_c, Aeq_v, beq = [], [], [], []
    Aub_r, Aub_c, Aub_v, bub = [], [], [], []
    n_eq = n_ub = 0
    H = None if angle else ptdf_full(net)
    for t in range(hours):
        # injection of each unit into bus n: terms (col, coef)
        terms = {n: [] for n in range(N)}
        for g in range(G):
            terms[net.gbus[g]].append((col(t, og + g), 1.0))
        for s, st in enumerate(net.st):
            terms[st["bus"]] += [(col(t, oc + 3 * s + 1), 1.0), (col(t, oc + 3 * s), -1.0)]
        dc_terms = {n: [] for n in range(N)}
        for k in range(K):
            dc_terms[net.kto[k]].append((col(t, ok + k), 1.0))
            dc_terms[net.kfrom[k]].append((col(t, ok + k), -1.0))
        if angle:
            for n in range(N):                                              # bal: inj + DC - sum_l A_ln f_l = D
                for c, v in terms[n] + dc_terms[n]:
                    Aeq_r.append(n_eq), Aeq_c.append(c), Aeq_v.append(v)
                for l in range(L):
                    sgn = 1.0 if net.lfrom[l] == n else (-1.0 if net.lto[l] == n else 0.0)
                    if sgn:
                        for nn, w in ((net.lfrom[l], net.b[l]), (net.lto[l], -net.b[l])):
                            Aeq_r.append(n_eq), Aeq_c.append(col(t, oth + nn)), Aeq_v.append(-sgn * w)
                beq.append(net.load[t, n])
                n_eq += 1
            for l in range(L):
                if np.isfinite(net.lrate[l]):
                    for sg in (1.0, -1.0):
                        for nn, w in ((net.lfrom[l], net.b[l]), (net.lto[l], -net.b[l])):
                            Aub_r.append(n_ub), Aub_c.append(col(t, oth + nn)), Aub_v.append(sg * w)
                        bub.append(net.lrate[l])
                        n_ub += 1
        else:
            for k_i, ii in enumerate(isl):                                   # bal_sys per island
                for n in ii:
                    for c, v in terms[n] + dc_terms[n]:
                        Aeq_r.append(n_eq), Aeq_c.append(c), Aeq_v.append(v)
                beq.append(float(net.load[t, ii].sum()))
                n_eq += 1
            for l in range(L):
                if not np.isfinite(net.lrate[l]):
                    continue
                for sg in (1.0, -1.0):
                    for n in range(N):
                        if H[l, n] != 0.0:
                            for c, v in terms[n] + dc_terms[n]:
                                Aub_r.append(n_ub), Aub_c.append(c), Aub_v.append(sg * H[l, n] * v)
                    bub.append(net.lrate[l] + sg * float(H[l] @ net.load[t]))
                    n_ub += 1
        for s, st in enumerate(net.st):                                      # st_soc (cyclic), st_pwr
            tm = (t - 1) % hours
            Aeq_r += [n_eq] * 4
            Aeq_c += [col(t, oc + 3 * s + 2), col(tm, oc + 3 * s + 2), col(t, oc + 3 * s), col(t, oc + 3 * s + 1)]
            Aeq_v += [1.0, -(1.0 - st["sigma"]), -st["eta_c"], 1.0 / st["eta_d"]]
            beq.append(0.0)
            n_eq += 1
            Aub_r += [n_ub, n_ub]
            Aub_c += [col(t, oc + 3 * s), col(t, oc + 3 * s + 1)]
            Aub_v += [1.0, 1.0]
            bub.append(st["P"])
            n_ub += 1
    Aeq = sp.csr_matrix((Aeq_v, (Aeq_r, Aeq_c)), shape=(n_eq, nv))
    Aub = sp.csr_matrix((Aub_v, (Aub_r, Aub_c)), shape=(n_ub, nv)) if n_ub else None
    bounds = list(zip([None if np.isneginf(x) else x for x in lb], [None if np.isinf(x) else x for x in ub]))
    res = linprog(cost, A_ub=Aub, b_ub=np.array(bub) if n_ub else None, A_eq=Aeq, b_eq=np.array(beq), bounds=bounds,
                  method="highs")
    assert res.status == 0, res.message
    return _unpack(net, res, hours, per, og, oth, ok, oc, angle, isl, H, n_eq, n_ub)


def _unpack(net, res, hours, per, og, oth, ok, oc, angle, isl, H, n_eq, n_ub) -> Sol:
    G, N, L, K, S = len(net.gmax), net.N, len(net.lx), len(net.kfwd), len(net.st)
    x = res.x.reshape(hours, per)
    g = x[:, og:og + G]
    fk = x[:, ok:ok + K]
    pi, lam, mu, f = np.zeros((hours, N)), np.zeros((hours, N)), np.zeros((hours, L)), np.zeros((hours, L))
    inj = np.zeros((hours, N))
    for t in range(hours):
        inj[t] = -net.load[t]
        for gg in range(G):
            inj[t, net.gbus[gg]] += g[t, gg]
        for s, st in enumerate(net.st):
            inj[t, st["bus"]] += x[t, oc + 3 * s + 1] - x[t, oc + 3 * s]
    ub_marg = res.ineqlin.marginals if n_ub else np.zeros(0)
    eq_marg = res.eqlin.marginals
    rows_ub_per = 0
    ratedl = [l for l in range(L) if np.isfinite(net.lrate[l])]
    for t in range(hours):
        if angle:
            th = x[t, oth:oth + N]
            Fm = np.zeros((L, N))
            for l in range(L):
                Fm[l, net.lfrom[l]], Fm[l, net.lto[l]] = net.b[l], -net.b[l]
            f[t] = Fm @ th
    # duals
    n_st = S
    eq_per = (N if angle else len(isl)) + n_st
    ub_per = (2 * len(ratedl)) + n_st
    for t in range(hours):
        e = eq_marg[t * eq_per: t * eq_per + (N if angle else len(isl))]
        u = ub_marg[t * ub_per: t * ub_per + 2 * len(ratedl)] if n_ub else np.zeros(0)
        for j, l in enumerate(ratedl):
            mu[t, l] = -u[2 * j] + u[2 * j + 1]
        if angle:
            pi[t] = e
        else:
            for k, ii in enumerate(isl):
                lam[t, ii] = e[k]
            pi[t] = lam[t] - H.T @ mu[t]
            f[t] = H @ inj[t] + _dc_inj_f(net, H, fk[t])
        if angle:
            for k, ii in enumerate(isl):
                lam[t, ii] = pi[t, net.refs[k]]
    # DC link duals from column reduced costs
    lo = res.lower.marginals.reshape(hours, per) if hasattr(res, "lower") else np.zeros((hours, per))
    up = res.upper.marginals.reshape(hours, per) if hasattr(res, "upper") else np.zeros((hours, per))
    muk = -(lo[:, ok:ok + K] + up[:, ok:ok + K])
    sol = Sol(net=net, obj_hr=float(res.fun), g=g, f=f, fk=fk, pi=pi, lam=lam, mu=mu, muk=muk, inj=inj)
    if S:
        sol.ch = np.stack([x[:, oc + 3 * s] for s in range(S)], 1)
        sol.dis = np.stack([x[:, oc + 3 * s + 1] for s in range(S)], 1)
        sol.soc = np.stack([x[:, oc + 3 * s + 2] for s in range(S)], 1)
        sol.v = np.stack([-eq_marg[t * eq_per + (N if angle else len(isl)) + s] for t in range(hours) for s in range(S)]
                         ).reshape(hours, S)
        sol.pwr_rho = np.stack([-ub_marg[t * ub_per + 2 * len(ratedl) + s] for t in range(hours) for s in range(S)]
                               ).reshape(hours, S)
    return sol


def _dc_inj_f(net, H, fk):
    out = np.zeros(H.shape[0])
    for k in range(len(fk)):
        out += (H[:, net.kto[k]] - H[:, net.kfrom[k]]) * fk[k]
    return out


# ====================================================================================== derived quantities
def decomposition(sol: Sol, t: int) -> np.ndarray:
    """pi_n = lambda_i(n) - sum_{l in AC} H_{l,n} mu_l (7.4a.5/7.4a.12)."""
    H = ptdf_full(sol.net)
    return sol.lam[t] - H.T @ sol.mu[t]


def rent_components(net: Net) -> list[list[int]]:
    """Components of (islands, all DC links) (7.4a.12)."""
    par = list(range(net.N))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for o, e in list(zip(net.lfrom, net.lto)) + list(zip(net.kfrom, net.kto)):
        par[find(int(o))] = find(int(e))
    comp: dict = {}
    for n in range(net.N):
        comp.setdefault(find(n), []).append(n)
    return sorted(comp.values(), key=min)


def rent_identity(sol: Sol, t: int):
    """Per rent component: (sum pi (-inj), sum mu f over AC + DC links in the component)."""
    net = sol.net
    out = []
    for C in rent_components(net):
        lhs = float(sol.pi[t, C] @ -sol.inj[t, C])
        rhs = sum(sol.mu[t, l] * sol.f[t, l] for l in range(len(net.lx)) if net.lfrom[l] in C)
        rhs += sum(sol.muk[t, k] * sol.fk[t, k] for k in range(len(net.kfwd)) if net.kfrom[k] in C)
        out.append((C, lhs, float(rhs)))
    return out


# ====================================================================================== hour state and price-setter analysis
@dataclass
class Hour:
    """Everything the 7.4a.7 / 7.4a.12 analysis needs for one hour, from the independent LP or from a run's output tables."""
    net: Net
    pi: np.ndarray                    # (N,)
    g: np.ndarray                     # (G,)
    f: np.ndarray                     # (L,)
    mu: np.ndarray                    # (L,)
    fk: np.ndarray                    # (K,)
    ch: np.ndarray                    # (S,)
    dis: np.ndarray                   # (S,)
    v: np.ndarray                     # (S,)


def hour_from_sol(sol: Sol, t: int) -> Hour:
    S = len(sol.net.st)
    z = np.zeros(S)
    return Hour(sol.net, sol.pi[t], sol.g[t], sol.f[t], sol.mu[t], sol.fk[t],
                sol.ch[t] if S else z, sol.dis[t] if S else z, sol.v[t] if S else z)


def tol_pi_of(pi: float) -> float:
    return max(0.01, 1e-5 * abs(pi))


def members(hr: Hour, tol_q=1e-3) -> list[dict]:
    """M_i candidates (7.4a.7): units meeting a local class at their own bus AND its price check, with setter cost.
    kind in {MARGINAL_UNIT, TIE_AT_BOUND, STORAGE_DIS, STORAGE_CH}."""
    net, out = hr.net, []
    for g in range(len(net.gmax)):
        m, pi_m = int(net.gbus[g]), hr.pi[int(net.gbus[g])]
        ok = abs(pi_m - net.gcost[g]) <= tol_pi_of(pi_m)
        tq = max(tol_q, 1e-6 * net.gmax[g])
        if tq < hr.g[g] < net.gmax[g] - tq and ok:
            out.append(dict(id=net.gid[g], bus=m, cost=float(net.gcost[g]), kind="MARGINAL_UNIT"))
        elif ok and not (tq < hr.g[g] < net.gmax[g] - tq):
            out.append(dict(id=net.gid[g], bus=m, cost=float(net.gcost[g]), kind="TIE_AT_BOUND"))
    for s, st in enumerate(net.st):
        if st["P"] <= tol_q:
            continue
        m, pi_m = st["bus"], hr.pi[st["bus"]]
        slack = hr.ch[s] + hr.dis[s] < st["P"] - tol_q
        cd_, cc_ = st["vom"] + hr.v[s] / st["eta_d"], st["eta_c"] * hr.v[s]
        if tol_q < hr.dis[s] < st["P"] - tol_q and slack and abs(pi_m - cd_) <= tol_pi_of(pi_m):
            out.append(dict(id=st["id"], bus=m, cost=float(cd_), kind="STORAGE_DIS"))
        elif tol_q < hr.ch[s] < st["P"] - tol_q and slack and abs(pi_m - cc_) <= tol_pi_of(pi_m):
            out.append(dict(id=st["id"], bus=m, cost=float(cc_), kind="STORAGE_CH"))
    return out


def price_components(hr: Hour, tol_q=1e-3) -> list[list[int]]:
    """Components of (islands, DC links strictly inside their limits) (7.4a.12)."""
    net = hr.net
    par = list(range(net.N))

    def find(i):
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    for o, e in zip(net.lfrom, net.lto):
        par[find(int(o))] = find(int(e))
    for k in range(len(net.kfwd)):
        if -net.krev[k] + tol_q < hr.fk[k] < net.kfwd[k] - tol_q:
            par[find(int(net.kfrom[k]))] = find(int(net.kto[k]))
    comp: dict = {}
    for n in range(net.N):
        comp.setdefault(find(n), []).append(n)
    return sorted(comp.values(), key=min)


def analyse(hr: Hour, comp: list[int], tol_q=1e-3, with_storage_rows=True) -> dict | None:
    """Case (a)/(b)/(c) analysis of the congested price component `comp` (7.4a.7 + 7.4a.12 A8). None if not congested.
    Returns dict(case, alpha {bus: {resource_id: weight}}, ids, buses, K (AC line indices), free (DC link indices), rank,
    rows, cols, interval(n) -> (lo, hi) using the S2 storage rows when `with_storage_rows`)."""
    net = hr.net
    H = ptdf_full(net)
    isl = [i for i in net.islands() if set(i) & set(comp)]
    iof = {n: k for k, i in enumerate(isl) for n in i}
    nI = len(isl)
    K = [l for l in range(len(net.lx)) if net.lfrom[l] in comp and abs(hr.mu[l]) > max(tol_pi_of(hr.pi[net.lfrom[l]]), tol_pi_of(hr.pi[net.lto[l]]))
         and abs(hr.f[l]) >= net.lrate[l] - 1e-3]
    if not K:
        return None
    nc = nI + len(K)

    def phi(n):
        v = np.zeros(nc)
        v[iof[n]] = 1.0
        v[nI:] = [-H[l, n] for l in K]
        return v
    mem = [m for m in members(hr, tol_q) if m["bus"] in comp]
    buses = sorted({m["bus"] for m in mem})
    c_b = {b: float(np.mean([m["cost"] for m in mem if m["bus"] == b])) for b in buses}
    free = [k for k in range(len(net.kfwd)) if net.kfrom[k] in comp and net.kto[k] in comp
            and -net.krev[k] + tol_q < hr.fk[k] < net.kfwd[k] - tol_q]
    rows = [phi(b) for b in buses] + [phi(net.kto[k]) - phi(net.kfrom[k]) for k in free]
    rhs = np.array([c_b[b] for b in buses] + [0.0] * len(free))
    Phi = np.array(rows) if rows else np.zeros((0, nc))
    rank = int(np.linalg.matrix_rank(Phi, tol=1e-9 * np.linalg.svd(Phi, compute_uv=False)[0])) if rows else 0
    case = "a" if (len(rows) == nc == rank) else ("b" if rank == nc < len(rows) else "c")
    alpha = {}
    if case in "ab":
        P = np.linalg.pinv(Phi)
        for n in comp:
            w = phi(n) @ P
            alpha[n] = {}
            for i, b in enumerate(buses):
                at_b = [m for m in mem if m["bus"] == b]
                for m in at_b:
                    alpha[n][m["id"]] = float(w[i] / len(at_b))
    out = dict(case=case, alpha=alpha, ids=[m["id"] for m in mem], buses=buses, K=K, free=free, rank=rank, rows=len(rows),
               cols=nc, members=mem)

    def interval(n):
        if case != "c":
            raise ValueError("interval only in case (c)")
        A_ub, b_ub = [], []
        in_m = {m["id"] for m in mem}

        def prow(m):
            v = np.zeros(nc)
            v[iof[m]] = 1.0
            v[nI:] = [-H[l, m] for l in K]
            return v
        for g in range(len(net.gmax)):
            m = int(net.gbus[g])
            if net.gid[g] in in_m or m not in comp:
                continue
            tq = max(tol_q, 1e-6 * net.gmax[g])
            if hr.g[g] >= net.gmax[g] - tq:
                A_ub.append(-prow(m)), b_ub.append(-net.gcost[g])
            elif hr.g[g] <= tq:
                A_ub.append(prow(m)), b_ub.append(net.gcost[g])
        if with_storage_rows:
            for s, st in enumerate(net.st):
                m = st["bus"]
                if st["id"] in in_m or m not in comp or st["P"] <= tol_q:
                    continue
                tp = tol_pi_of(hr.pi[m])
                cd_, cc_ = st["vom"] + hr.v[s] / st["eta_d"], st["eta_c"] * hr.v[s]
                if hr.ch[s] <= tol_q and hr.dis[s] <= tol_q:                  # idle: two-sided
                    A_ub.append(prow(m)), b_ub.append(cd_ + tp)
                    A_ub.append(-prow(m)), b_ub.append(-(cc_ - tp))
                elif hr.dis[s] >= st["P"] - tol_q:                            # discharging at the st_pwr limit
                    A_ub.append(-prow(m)), b_ub.append(-(cd_ - tp))
                elif hr.ch[s] >= st["P"] - tol_q:                             # charging at the limit
                    A_ub.append(prow(m)), b_ub.append(cc_ + tp)
        bounds = [(None, None)] * nI + [((0, None) if hr.f[l] > 0 else (None, 0)) for l in K]
        res = []
        for sg in (1.0, -1.0):
            r = linprog(sg * prow(n), A_eq=Phi if rows else None, b_eq=rhs if rows else None,
                        A_ub=np.array(A_ub) if A_ub else None, b_ub=np.array(b_ub) if b_ub else None, bounds=bounds,
                        method="highs")
            if r.status == 0:
                res.append(sg * r.fun)
            elif r.status == 3:
                res.append(-np.inf if sg > 0 else np.inf)
            else:
                raise AssertionError(f"verifier interval LP failed: {r.message}")
        return res[0], res[1]
    out["interval"] = interval
    return out


# ====================================================================================== run-side helpers (model-facing tests)
from types import SimpleNamespace          # noqa: E402

import pytest                              # noqa: E402


def xf(what: str):
    """strict xfail for a test that needs Gate 4 code (marker checker: reason cites `Gate 4`)."""
    return pytest.mark.xfail(strict=True, reason=f"Gate 4: needs G4-4 {what}")


@pytest.fixture(scope="session")
def g4run(tmp_path_factory):
    """g4run(key, builder) -> SimpleNamespace(t=tables, h=HealthReport, sv, fp, out, cd); builder(tmp) -> case dir. Cached by key."""
    from capex.run import output_tables, run_case          # lazily: the independent route must not need capex
    cache: dict = {}

    def get(key, builder):
        if key not in cache:
            tmp = tmp_path_factory.mktemp("g4")
            cd = builder(tmp)
            sv, health, fp = run_case(cd, tmp / "out")
            cache[key] = SimpleNamespace(t=output_tables(sv, health), h=health, sv=sv, fp=fp, cd=cd, out=tmp / "out")
        return cache[key]
    return get


def pcol(df: pd.DataFrame) -> str:
    return "period_id" if "period_id" in df.columns else "period"


def idcol(df: pd.DataFrame) -> str:
    for c in ("resource", "resource_id", "link", "link_id", "zone"):
        if c in df.columns:
            return c
    raise KeyError(f"no id column in {list(df.columns)}")


def mat(df: pd.DataFrame, col: str, ids: list[str], hours: int = T, key: str | None = None) -> np.ndarray:
    """(hours, len(ids)) matrix of df[col] by id column, single period p1, t = 1..hours."""
    d = df[df[pcol(df)] == "p1"] if pcol(df) in df.columns else df
    w = d.pivot(index="t", columns=key or idcol(df), values=col).reindex(range(1, hours + 1))
    return w[ids].to_numpy(float)


def check_row(h, cid: str) -> pd.DataFrame:
    c = h.checks
    return c[c["check_id"] == cid]


def non_pass(h) -> pd.DataFrame:
    c = h.checks
    return c[c["status"] != "pass"]


def total_obj(t: dict) -> float:
    return float(t["objective"].query("component == 'total'")["value_usd_yr"].iloc[0])
