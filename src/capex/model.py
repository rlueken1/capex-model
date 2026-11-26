"""LP assembly (formulation section 2) with scaling (section 6.1). Every row/column block carries its spec label."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
import scipy.sparse as sp

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
    def n_rows(self) -> int:
        return self.a.shape[0]

    @property
    def n_cols(self) -> int:
        return self.a.shape[1]


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


def _layouts(case: Case, dur_lo_ix: np.ndarray, dur_hi_ix: np.ndarray) -> tuple[_Layout, _Layout]:
    gen_ids, st_ids = case.gen.ids, case.storage.ids
    pt = (tuple(case.periods), tuple(range(1, T + 1)))
    cols, rows = _Layout(), _Layout()
    for name, ids in (("x", gen_ids), ("xP", st_ids), ("xE", st_ids)):
        cols.add(name, ("resource",), (ids,))
    for name, dim, ids in (("g", "resource", gen_ids), ("ch", "resource", st_ids), ("dis", "resource", st_ids),
                           ("soc", "resource", st_ids), ("flow", "link", case.links.ids),
                           ("use", "zone", case.zones)):
        cols.add(name, (dim, "period", "t"), (ids, *pt))
    rows.add("bal", ("zone", "period", "t"), (case.zones, *pt))
    rows.add("gen_max", ("resource", "period", "t"), (gen_ids, *pt))
    for name in ("st_pwr", "st_soc", "st_emax"):
        rows.add(name, ("resource", "period", "t"), (st_ids, *pt))
    st_ids_arr = np.asarray(st_ids, dtype=object)
    rows.add("st_dur_lo", ("resource",), (tuple(st_ids_arr[dur_lo_ix]),))
    rows.add("st_dur_hi", ("resource",), (tuple(st_ids_arr[dur_hi_ix]),))
    return cols, rows


def _triplets(parts: list[tuple[np.ndarray, np.ndarray, np.ndarray]], shape: tuple[int, int]) -> sp.csr_matrix:
    rows = np.concatenate([p[0].ravel() for p in parts])
    cols = np.concatenate([p[1].ravel() for p in parts])
    vals = np.concatenate([np.broadcast_to(p[2], p[0].shape).ravel() for p in parts]).astype(float)
    return sp.coo_matrix((vals, (rows, cols)), shape=shape).tocsr()


def _matrix(case: Case, cols: _Layout, rows: _Layout, dur_lo_ix: np.ndarray, dur_hi_ix: np.ndarray) -> sp.csr_matrix:
    gen, st, lk = case.gen, case.storage, case.links
    cb, rb = cols.blocks, rows.blocks
    n_g, n_s, n_l, n_z, n_p = len(gen.ids), len(st.ids), len(lk.ids), len(case.zones), len(case.periods)
    gi, gp, gt = np.indices((n_g, n_p, T))
    si, sp_, stt = np.indices((n_s, n_p, T))
    li, lp_, lt = np.indices((n_l, n_p, T))
    zi, zp, zt = np.indices((n_z, n_p, T))
    t_prev = (stt - 1) % T
    parts = [
        # bal[z,p,t]
        (rb["bal"].idx(gen.zone[gi], gp, gt), cb["g"].idx(gi, gp, gt), 1.0),
        (rb["bal"].idx(st.zone[si], sp_, stt), cb["dis"].idx(si, sp_, stt), 1.0),
        (rb["bal"].idx(st.zone[si], sp_, stt), cb["ch"].idx(si, sp_, stt), -1.0),
        (rb["bal"].idx(lk.end[li], lp_, lt), cb["flow"].idx(li, lp_, lt), 1.0),
        (rb["bal"].idx(lk.origin[li], lp_, lt), cb["flow"].idx(li, lp_, lt), -1.0),
        (rb["bal"].idx(zi, zp, zt), cb["use"].idx(zi, zp, zt), 1.0),
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
        (rb["st_dur_hi"].idx(np.arange(len(dur_hi_ix))), cb["xP"].idx(dur_hi_ix), -st.dur_hi[dur_hi_ix]),
    ]
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
    return lo, hi


def _row_bounds(case: Case, rows: _Layout) -> tuple[np.ndarray, np.ndarray]:
    """Equalities have lo = hi = rhs; <= rows have lo = -inf; >= rows have hi = +inf."""
    rb, gen, st = rows.blocks, case.gen, case.storage
    lo, hi = np.full(rows.size, -INF), np.zeros(rows.size)
    rb["bal"].view(lo)[:] = case.demand
    rb["bal"].view(hi)[:] = case.demand
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
    cols, rows = _layouts(case, dur_lo_ix, dur_hi_ix)
    row_lo, row_hi = _row_bounds(case, rows)
    col_lo, col_hi = _col_bounds(case, cols)
    return LP(a=_matrix(case, cols, rows, dur_lo_ix, dur_hi_ix), c=_costs(case, cols) * scaling.cost_factor,
              row_lo=row_lo * scaling.k_p, row_hi=row_hi * scaling.k_p, col_lo=col_lo * scaling.k_p,
              col_hi=col_hi * scaling.k_p, rows=rows.blocks, cols=cols.blocks, scaling=scaling)
