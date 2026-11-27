"""DC power flow network pieces for the LP (formulation 7.4a.2): susceptances, electrical islands, PTDF."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

if TYPE_CHECKING:
    from .data import Case

PTDF_NOISE = 1e-10


@dataclass(frozen=True)
class Islands:
    """Electrical islands: connected components of (zones, links), ids i1, i2, ... by smallest zone row index."""
    ids: tuple[str, ...]
    node: np.ndarray       # (N,) island index of each zone
    ref: np.ndarray        # (I,) reference zone index n0(i)


def susceptance_mw_rad(case: Case) -> np.ndarray:
    """b_l = base_mva_l / reactance_pu_l in MW/rad, shape (L,)."""
    return case.links.base_mva / case.links.x_pu


def _labels(case: Case) -> np.ndarray:
    """Component label of each zone, numbered by the smallest zone index in the component."""
    n, lk = len(case.zones), case.links
    graph = coo_matrix((np.ones(len(lk.ids)), (lk.origin, lk.end)), shape=(n, n))
    labels = connected_components(graph, directed=False)[1]
    _, first = np.unique(labels, return_index=True)
    return np.argsort(np.argsort(first))[labels]


def ref_bus_ids(case: Case) -> list[str]:
    """Zone ids named by `tx.ref_bus` (one id or a list of ids); empty when the key is absent."""
    given = case.switches.get("tx.ref_bus", [])
    return [given] if isinstance(given, str) else list(given)


def islands(case: Case) -> Islands:
    """Islands and their reference zones: `tx.ref_bus` entries, else the first zone of the island in row order."""
    node = _labels(case)
    n_isl = int(node.max()) + 1 if len(node) else 0
    ref = np.array([np.flatnonzero(node == i)[0] for i in range(n_isl)], dtype=np.int64)
    for z in map(case.zones.index, ref_bus_ids(case)):
        ref[node[z]] = z
    return Islands(ids=tuple(f"i{i + 1}" for i in range(n_isl)), node=node, ref=ref)


def ptdf(case: Case, isl: Islands) -> np.ndarray:
    """H = diag(b) A X with X the inverse of the reduced bus susceptance matrix per island (shape (L,N))."""
    n, lk = len(case.zones), case.links
    b = susceptance_mw_rad(case)
    a = np.zeros((len(b), n))
    a[np.arange(len(b)), lk.origin] = 1.0
    a[np.arange(len(b)), lk.end] = -1.0
    bus = a.T @ (b[:, None] * a)
    x = np.zeros((n, n))
    for i in range(len(isl.ids)):
        keep = np.flatnonzero((isl.node == i) & (np.arange(n) != isl.ref[i]))
        if len(keep):
            x[np.ix_(keep, keep)] = np.linalg.inv(bus[np.ix_(keep, keep)])
    h = b[:, None] * (a @ x)
    h[np.abs(h) <= PTDF_NOISE] = 0.0
    return h
