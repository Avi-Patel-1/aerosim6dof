"""Time-alignment helpers for run output CSVs."""

from __future__ import annotations

import bisect
import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from aerosim6dof.reports.csv_writer import read_csv


RUN_TABLES = ("truth", "sensors", "history")


@dataclass(frozen=True)
class AlignedSample:
    """One report sample with nearest rows from each run table."""

    time_s: float
    truth: dict[str, Any]
    sensors: dict[str, Any]
    history: dict[str, Any]
    truth_time_s: float | None
    sensor_time_s: float | None
    history_time_s: float | None
    truth_time_delta_s: float | None
    sensor_time_delta_s: float | None
    history_time_delta_s: float | None


@dataclass(frozen=True)
class RunTables:
    """Loaded run output tables used by the fusion report."""

    truth: list[dict[str, Any]]
    sensors: list[dict[str, Any]]
    history: list[dict[str, Any]]
    warnings: list[str]
    source_files: list[str]


def load_run_tables(run_dir: str | Path) -> RunTables:
    """Read optional `truth.csv`, `sensors.csv`, and `history.csv` files."""

    root = Path(run_dir)
    warnings: list[str] = []
    source_files: list[str] = []
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in RUN_TABLES:
        path = root / f"{table}.csv"
        rows = _read_optional_csv(path, warnings)
        tables[table] = rows
        if rows:
            source_files.append(path.name)
    if not any(tables.values()):
        warnings.append("no run output rows found in truth.csv, sensors.csv, or history.csv")
    return RunTables(
        truth=tables["truth"],
        sensors=tables["sensors"],
        history=tables["history"],
        warnings=warnings,
        source_files=source_files,
    )


def align_run_tables(
    *,
    truth_rows: Iterable[dict[str, Any]] | None = None,
    sensor_rows: Iterable[dict[str, Any]] | None = None,
    history_rows: Iterable[dict[str, Any]] | None = None,
    max_time_gap_s: float | None = None,
) -> list[AlignedSample]:
    """Align truth, sensor, and history rows on a common time base.

    The time base is selected conservatively: truth rows first, then history,
    then sensor rows. Each table is matched by nearest finite time. Missing
    tables simply contribute empty dictionaries.
    """

    truth_index = _IndexedRows.from_rows(truth_rows or [], "truth")
    sensor_index = _IndexedRows.from_rows(sensor_rows or [], "sensors")
    history_index = _IndexedRows.from_rows(history_rows or [], "history")
    base = _select_base_index(truth_index, history_index, sensor_index)
    if base is None:
        return []
    max_gap = _finite_or_none(max_time_gap_s)
    samples: list[AlignedSample] = []
    for time_s in base.times:
        truth, truth_time = truth_index.nearest(time_s, max_gap)
        sensors, sensor_time = sensor_index.nearest(time_s, max_gap)
        history, history_time = history_index.nearest(time_s, max_gap)
        samples.append(
            AlignedSample(
                time_s=time_s,
                truth=truth,
                sensors=sensors,
                history=history,
                truth_time_s=truth_time,
                sensor_time_s=sensor_time,
                history_time_s=history_time,
                truth_time_delta_s=_delta(truth_time, time_s),
                sensor_time_delta_s=_delta(sensor_time, time_s),
                history_time_delta_s=_delta(history_time, time_s),
            )
        )
    return samples


class _IndexedRows:
    def __init__(self, rows: list[dict[str, Any]], times: list[float], table: str):
        self.rows = rows
        self.times = times
        self.table = table

    @classmethod
    def from_rows(cls, rows: Iterable[dict[str, Any]], table: str) -> "_IndexedRows":
        timed: list[tuple[float, dict[str, Any]]] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            time_s = row_time(row, table=table)
            if time_s is None:
                continue
            timed.append((time_s, dict(row)))
        timed.sort(key=lambda item: item[0])
        return cls([row for _, row in timed], [time_s for time_s, _ in timed], table)

    def nearest(self, time_s: float, max_gap_s: float | None) -> tuple[dict[str, Any], float | None]:
        if not self.times:
            return {}, None
        index = bisect.bisect_left(self.times, time_s)
        candidates: list[int] = []
        if index < len(self.times):
            candidates.append(index)
        if index > 0:
            candidates.append(index - 1)
        best_index = min(candidates, key=lambda idx: abs(self.times[idx] - time_s))
        best_time = self.times[best_index]
        if max_gap_s is not None and abs(best_time - time_s) > max_gap_s:
            return {}, None
        return self.rows[best_index], best_time


def row_time(row: dict[str, Any], *, table: str = "history") -> float | None:
    """Return the finite alignment time for a row."""

    keys = ("time_s", "sensor_time_s") if table == "sensors" else ("time_s", "sensor_time_s")
    for key in keys:
        value = _finite_or_none(row.get(key))
        if value is not None:
            return value
    return None


def _select_base_index(*indexes: _IndexedRows) -> _IndexedRows | None:
    for index in indexes:
        if index.times:
            return index
    return None


def _read_optional_csv(path: Path, warnings: list[str]) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        return list(read_csv(path))
    except (OSError, ValueError, csv.Error) as exc:
        warnings.append(f"{path.name} could not be read: {exc}")
        return []


def _finite_or_none(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number == number and abs(number) != float("inf") else None


def _delta(value: float | None, reference: float) -> float | None:
    return None if value is None else float(value - reference)
