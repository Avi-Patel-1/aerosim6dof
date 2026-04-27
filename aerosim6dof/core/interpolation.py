"""Interpolation helpers for simple coefficient and thrust tables."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np


def interp1(x: float, xs: Iterable[float], ys: Iterable[float]) -> float:
    x_arr = np.array(list(xs), dtype=float)
    y_arr = np.array(list(ys), dtype=float)
    if len(x_arr) == 0 or len(x_arr) != len(y_arr):
        raise ValueError("interpolation table must have equal non-empty x/y arrays")
    order = np.argsort(x_arr)
    return float(np.interp(float(x), x_arr[order], y_arr[order]))


@dataclass
class Table1D:
    x: list[float]
    y: list[float]

    @classmethod
    def from_pairs(cls, pairs: Iterable[Iterable[float]]) -> "Table1D":
        rows = [list(row) for row in pairs]
        if not rows:
            raise ValueError("table cannot be empty")
        return cls([float(r[0]) for r in rows], [float(r[1]) for r in rows])

    def __call__(self, x: float) -> float:
        return interp1(x, self.x, self.y)

