"""LP assembly (formulation section 2) with scaling (section 6.1). Every row/column block carries its spec label."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp

from . import network
from .config import Scaling
from .data import T, Case

INF = np.inf


@dataclass(frozen=True)
class Block:
    """A contiguous family of rows or columns: spec label, index sets and their ids."""
    name: str
    dims: tuple[str, ...]
    ids: tuple[tuple, ...]
    offset: int

    @property
    def shape(self) -> tuple[int, ...]:
        return tuple(len(i) for i in self.ids)

    @property
    def size(self) -> int:
        return int(np.prod(self.shape))

    def idx(self, *ix: np.ndarray) -> np.ndarray:
        """Flat positions of index tuples (integer positions per dimension)."""
        grids = np.broadcast_arrays(*(np.asarray(a, dtype=np.int64) for a in ix))
        if self.size == 0 or grids[0].size == 0:
            return np.empty(grids[0].shape, dtype=np.int64)
        return self.offset + np.ravel_multi_index(tuple(grids), self.shape)

    def view(self, vec: np.ndarray) -> np.ndarray:
        """Slice of a full-length vector reshaped to this block's shape."""
        return vec[self.offset:self.offset + self.size].reshape(self.shape)

    def frame(self) -> pd.DataFrame:
        """Labelled index table: one row per member, columns = dims."""
        grids = np.indices(self.shape).reshape(len(self.shape), -1)
        cols = {d: np.asarray(ids, dtype=object)[g] for d, ids, g in zip(self.dims, self.ids, grids)}
        return pd.DataFrame({"label": self.name, **cols})


@dataclass(frozen=True)
class LP:
    """min c'x s.t. row_lo <= A x <= row_hi, col_lo <= x <= col_hi, in scaled units."""
    a: sp.csr_matrix
    c: np.ndarray
    row_lo: np.ndarray
    row_hi: np.ndarray
    col_lo: np.ndarray
    col_hi: np.ndarray
    rows: dict[str, Block]
    cols: dict[str, Block]
    scaling: Scaling

    @property
    def col_scale(self) -> np.ndarray:
        return column_scale(self.cols, self.n_cols, self.scaling.k_p)

    @property
    def n_rows(self) -> int:
        return self.a.shape[0]

    @property
    def n_cols(self) -> int:
        return self.a.shape[1]


@dataclass(frozen=True)
class _Net:
    """DC power flow data of one build (formulation 7.4a.2): form, islands, susceptance, PTDF (ptdf form only)."""
    form: str
    isl: network.Islands
    b: np.ndarray           # (L,) MW/rad
    h: np.ndarray | None    # (L,N)


def _net(case: Case) -> _Net | None:
    if not case.dcpf:
        return None
    isl = network.islands(case)
    return _Net(case.dcpf_form, isl, network.susceptance_mw_rad(case),
                network.ptdf(case, isl) if case.dcpf_form == "ptdf" else None)


def column_scale(cols: dict[str, Block], n_cols: int, k_p: float) -> np.ndarray:
    """Per-column scale of x~ = scale x: k_P, except the unscaled angles theta (formulation 7.4a.2)."""
    scale = np.full(n_cols, k_p)
    if "theta" in cols:
        scale[cols["theta"].offset:cols["theta"].offset + cols["theta"].size] = 1.0
    return scale


class _Layout:
    """Sequential block allocator."""

    def __init__(self) -> None:
        self.blocks: dict[str, Block] = {}
        self.size = 0

    def add(self, name: str, dims: tuple[str, ...], ids: tuple[tuple, ...]) -> Block:
        block = Block(name, dims, ids, self.size)
        self.blocks[name] = block
        self.size += block.size
        return block


def _layouts(case: Case, dur_lo_ix: np.ndarray, dur_hi_ix: np.ndarray, net: _Net | None
             ) -> tuple[_Layout, _Layout]:
    gen_ids, st_ids = case.gen.ids, case.storage.ids
    pt = (tuple(case.periods), tuple(range(1, T + 1)))
    cols, rows = _Layout(), _Layout()
    for name, ids in (("x", gen_ids), ("xP", st_ids), ("xE", st_ids)):
        cols.add(name, ("resource",), (ids,))
    for name, dim, ids in (("g", "resource", gen_ids), ("ch", "resource", st_ids), ("dis", "resource", st_ids),
                           ("soc", "resource", st_ids), ("flow", "link", case.links.ids),
                           ("use", "zone", case.zones)):
        cols.add(name, (dim, "period", "t"), (ids, *pt))
    if net is None or net.form == "angle":
        rows.add("bal", ("zone", "period", "t"), (case.zones, *pt))
    rows.add("gen_max", ("resource", "period", "t"), (gen_ids, *pt))
    for name in ("st_pwr", "st_soc", "st_emax"):
        rows.add(name, ("resource", "period", "t"), (st_ids, *pt))
    st_ids_arr = np.asarray(st_ids, dtype=object)
    rows.add("st_dur_lo", ("resource",), (tuple(st_ids_arr[dur_lo_ix]),))
    rows.add("st_dur_hi", ("resource",), (tuple(st_ids_arr[dur_hi_ix]),))
    if net is not None:
        _add_network(case, cols, rows, net, pt)
    return cols, rows


def _add_network(case: Case, cols: _Layout, rows: _Layout, net: _Net, pt: tuple[tuple, tuple]) -> None:
    """dcpf blocks (7.4a.3, 7.4a.4): kvl/ref_angle rows and theta columns, or bal_sys/ptdf_flow rows."""
    if net.form == "angle":
        cols.add("theta", ("zone", "period", "t"), (case.zones, *pt))
        rows.add("kvl", ("link", "period", "t"), (case.links.ids, *pt))
        rows.add("ref_angle", ("island", "period", "t"), (net.isl.ids, *pt))
    else:
        rows.add("bal_sys", ("island", "period", "t"), (net.isl.ids, *pt))
        rows.add("ptdf_flow", ("link", "period", "t"), (case.links.ids, *pt))


def _triplets(parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]], shape: tuple[int, int]) -> sp.csr_matrix:
    rows = np.concatenate([p[0].ravel() for p in parts])
    cols = np.concatenate([p[1].ravel() for p in parts])
    vals = np.concatenate([np.broadcast_to(p[2], p[0].shape).ravel() for p in parts]).astype(float)
    mat = sp.coo_matrix((vals, (rows, cols)), shape=shape).tocsr()
    mat.eliminate_zeros()
    return mat


def _bal_parts(case: Case, cols: _Layout, rows: _Layout) -> list[tuple]:
    """bal[z,p,t]: nodal balance with transport links (formulation 2.2)."""
    gen, st, lk = case.gen, case.storage, case.links
    cb, rb = cols.blocks, rows.blocks
    gi, gp, gt = np.indices((len(gen.ids), len(case.periods), T))
    si, sp_, stt = np.indices((len(st.ids), len(case.periods), T))
    li, lp_, lt = np.indices((len(lk.ids), len(case.periods), T))
    zi, zp, zt = np.indices((len(case.zones), len(case.periods), T))
    return [
        (rb["bal"].idx(gen.zone[gi], gp, gt), cb["g"].idx(gi, gp, gt), 1.0),
        (rb["bal"].idx(st.zone[si], sp_, stt), cb["dis"].idx(si, sp_, stt), 1.0),
        (rb["bal"].idx(st.zone[si], sp_, stt), cb["ch"].idx(si, sp_, stt), -1.0),
        (rb["bal"].idx(lk.end[li], lp_, lt), cb["flow"].idx(li, lp_, lt), 1.0),
        (rb["bal"].idx(lk.origin[li], lp_, lt), cb["flow"].idx(li, lp_, lt), -1.0),
        (rb["bal"].idx(zi, zp, zt), cb["use"].idx(zi, zp, zt), 1.0)]


def _angle_parts(case: Case, cols: _Layout, rows: _Layout, net: _Net, k_p: float) -> list[tuple]:
    """kvl[l,p,t]: f - b (theta_o - theta_e) = 0 with b scaled by k_P; ref_angle[i,p,t]: theta_ref = 0."""
    lk, n_p = case.links, len(case.periods)
    cb, rb = cols.blocks, rows.blocks
    li, lp_, lt = np.indices((len(lk.ids), n_p, T))
    ii, ip, it = np.indices((len(net.isl.ids), n_p, T))
    kb = (k_p * net.b)[li]
    return [
        (rb["kvl"].idx(li, lp_, lt), cb["flow"].idx(li, lp_, lt), 1.0),
        (rb["kvl"].idx(li, lp_, lt), cb["theta"].idx(lk.origin[li], lp_, lt), -kb),
        (rb["kvl"].idx(li, lp_, lt), cb["theta"].idx(lk.end[li], lp_, lt), kb),
        (rb["ref_angle"].idx(ii, ip, it), cb["theta"].idx(net.isl.ref[ii], ip, it), 1.0)]


def _ptdf_parts(case: Case, cols: _Layout, rows: _Layout, net: _Net) -> list[tuple]:
    """bal_sys[i,p,t] and ptdf_flow[l,p,t]: every injection column enters with its sign and node (7.4a.4)."""
    gen, st, n_p = case.gen, case.storage, len(case.periods)
    cb, rb = cols.blocks, rows.blocks
    injection = [(cb["g"], gen.zone, 1.0), (cb["dis"], st.zone, 1.0), (cb["ch"], st.zone, -1.0),
                 (cb["use"], np.arange(len(case.zones)), 1.0)]
    parts = []
    for blk, node, sign in injection:
        mi, mp, mt = np.indices((len(node), n_p, T))
        parts.append((rb["bal_sys"].idx(net.isl.node[node][mi], mp, mt), blk.idx(mi, mp, mt), sign))
        li, mi, mp, mt = np.indices((len(case.links.ids), len(node), n_p, T))
        parts.append((rb["ptdf_flow"].idx(li, mp, mt), blk.idx(mi, mp, mt), -sign * net.h[li, node[mi]]))
    li, lp_, lt = np.indices((len(case.links.ids), n_p, T))
    parts.append((rb["ptdf_flow"].idx(li, lp_, lt), cb["flow"].idx(li, lp_, lt), 1.0))
    return parts


def _device_parts(case: Case, cols: _Layout, rows: _Layout, dur_lo_ix: np.ndarray, dur_hi_ix: np.ndarray
                  ) -> list[tuple]:
    gen, st = case.gen, case.storage
    cb, rb = cols.blocks, rows.blocks
    n_g, n_s, n_p = len(gen.ids), len(st.ids), len(case.periods)
    gi, gp, gt = np.indices((n_g, n_p, T))
    si, sp_, stt = np.indices((n_s, n_p, T))
    t_prev = (stt - 1) % T
    return [
        # gen_max[r,p,t]: g - A x <= A K0
        (rb["gen_max"].idx(gi, gp, gt), cb["g"].idx(gi, gp, gt), 1.0),
        (rb["gen_max"].idx(gi, gp, gt), cb["x"].idx(gi), -gen.avail),
        # st_pwr[r,p,t]: c + d - xP <= P0
        (rb["st_pwr"].idx(si, sp_, stt), cb["ch"].idx(si, sp_, stt), 1.0),
        (rb["st_pwr"].idx(si, sp_, stt), cb["dis"].idx(si, sp_, stt), 1.0),
        (rb["st_pwr"].idx(si, sp_, stt), cb["xP"].idx(si), -1.0),
        # st_soc[r,p,t]: e_t - (1-sigma) e_{t-} - eta_c c + d / eta_d = 0
        (rb["st_soc"].idx(si, sp_, stt), cb["soc"].idx(si, sp_, stt), 1.0),
        (rb["st_soc"].idx(si, sp_, stt), cb["soc"].idx(si, sp_, t_prev), -(1.0 - st.sigma[si])),
        (rb["st_soc"].idx(si, sp_, stt), cb["ch"].idx(si, sp_, stt), -st.eta_c[si]),
        (rb["st_soc"].idx(si, sp_, stt), cb["dis"].idx(si, sp_, stt), 1.0 / st.eta_d[si]),
        # st_emax[r,p,t]: e - xE <= E0
        (rb["st_emax"].idx(si, sp_, stt), cb["soc"].idx(si, sp_, stt), 1.0),
        (rb["st_emax"].idx(si, sp_, stt), cb["xE"].idx(si), -1.0),
        # st_dur_lo[r]: xE - dur_lo xP >= 0 ; st_dur_hi[r]: xE - dur_hi xP <= 0
        (rb["st_dur_lo"].idx(np.arange(len(dur_lo_ix))), cb["xE"].idx(dur_lo_ix), 1.0),
        (rb["st_dur_lo"].idx(np.arange(len(dur_lo_ix))), cb["xP"].idx(dur_lo_ix), -st.dur_lo[dur_lo_ix]),
        (rb["st_dur_hi"].idx(np.arange(len(dur_hi_ix))), cb["xE"].idx(dur_hi_ix), 1.0),
        (rb["st_dur_hi"].idx(np.arange(len(dur_hi_ix))), cb["xP"].idx(dur_hi_ix), -st.dur_hi[dur_hi_ix])]


def _matrix(case: Case, cols: _Layout, rows: _Layout, dur_lo_ix: np.ndarray, dur_hi_ix: np.ndarray,
            net: _Net | None, k_p: float) -> sp.csr_matrix:
    ptdf_form = net is not None and net.form == "ptdf"
    parts = [] if ptdf_form else _bal_parts(case, cols, rows)
    parts += _device_parts(case, cols, rows, dur_lo_ix, dur_hi_ix)
    if net is not None:
        parts += _ptdf_parts(case, cols, rows, net) if ptdf_form else _angle_parts(case, cols, rows, net, k_p)
    return _triplets(parts, (rows.size, cols.size))


def _costs(case: Case, cols: _Layout) -> np.ndarray:
    """Objective coefficients in I/O units (formulation 2.3, without Z0)."""
    gen, st, cb = case.gen, case.storage, cols.blocks
    wt = case.w[None, :, None]
    c = np.zeros(cols.size)
    cb["x"].view(c)[:] = gen.cfix
    cb["xP"].view(c)[:] = st.cp
    cb["xE"].view(c)[:] = st.ce
    cb["g"].view(c)[:] = wt * gen.mc
    cb["dis"].view(c)[:] = wt * st.vom[:, None, None]
    cb["use"].view(c)[:] = wt * case.voll
    return c


def _col_bounds(case: Case, cols: _Layout) -> tuple[np.ndarray, np.ndarray]:
    cb = cols.blocks
    lo, hi = np.zeros(cols.size), np.full(cols.size, INF)
    cb["x"].view(hi)[:] = case.gen.xmax
    cb["xP"].view(hi)[:] = case.storage.xp_max
    cb["xE"].view(hi)[:] = case.storage.xe_max
    cb["flow"].view(lo)[:] = -case.links.f_minus[:, None, None]
    cb["flow"].view(hi)[:] = case.links.f_plus[:, None, None]
    cb["use"].view(hi)[:] = case.demand
    if "theta" in cb:
        cb["theta"].view(lo)[:] = -INF
    return lo, hi


def _equalities(case: Case, net: _Net | None) -> dict[str, np.ndarray]:
    """Right-hand sides of the equality rows that carry demand (zero rows stay at their default 0)."""
    if net is None or net.form == "angle":
        return {"bal": case.demand}
    island_demand = np.zeros((len(net.isl.ids), *case.demand.shape[1:]))
    np.add.at(island_demand, net.isl.node, case.demand)
    return {"bal_sys": island_demand, "ptdf_flow": -np.einsum("ln,npt->lpt", net.h, case.demand)}


def _row_bounds(case: Case, rows: _Layout, net: _Net | None) -> tuple[np.ndarray, np.ndarray]:
    """Equalities have lo = hi = rhs; <= rows have lo = -inf; >= rows have hi = +inf."""
    rb, gen, st = rows.blocks, case.gen, case.storage
    lo, hi = np.full(rows.size, -INF), np.zeros(rows.size)
    for name, rhs in _equalities(case, net).items():
        rb[name].view(lo)[:] = rhs
        rb[name].view(hi)[:] = rhs
    for name in ("kvl", "ref_angle"):
        if name in rb:
            rb[name].view(lo)[:] = 0.0
    rb["gen_max"].view(hi)[:] = gen.avail * gen.k0[:, None, None]
    rb["st_pwr"].view(hi)[:] = st.p0[:, None, None]
    rb["st_soc"].view(lo)[:] = 0.0
    rb["st_emax"].view(hi)[:] = st.e0[:, None, None]
    rb["st_dur_lo"].view(lo)[:] = 0.0
    rb["st_dur_lo"].view(hi)[:] = INF
    return lo, hi


def build_lp(case: Case, scaling: Scaling = Scaling()) -> LP:
    """Assemble the scaled LP. Power/energy quantities scale by k_P, costs by k_C s_obj / k_P."""
    st = case.storage
    candidate = st.status == "candidate"
    dur_lo_ix = np.flatnonzero(candidate & ~np.isnan(st.dur_lo))
    dur_hi_ix = np.flatnonzero(candidate & ~np.isnan(st.dur_hi))
    net = _net(case)
    cols, rows = _layouts(case, dur_lo_ix, dur_hi_ix, net)
    row_lo, row_hi = _row_bounds(case, rows, net)
    col_lo, col_hi = _col_bounds(case, cols)
    scale = column_scale(cols.blocks, cols.size, scaling.k_p)
    return LP(a=_matrix(case, cols, rows, dur_lo_ix, dur_hi_ix, net, scaling.k_p),
              c=_costs(case, cols) * scaling.cost_factor, row_lo=row_lo * scaling.k_p, row_hi=row_hi * scaling.k_p,
              col_lo=col_lo * scale, col_hi=col_hi * scale, rows=rows.blocks, cols=cols.blocks, scaling=scaling)
