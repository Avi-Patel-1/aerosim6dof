"""Small trade-space analysis primitives for AeroLab studies.

The original trade-space explorer uses NumPy-only statistics and CSV/JSON
artifacts. This module keeps the same spirit while operating directly on
AeroLab run summary rows.
"""

from __future__ import annotations

import itertools
import math
from typing import Any

import numpy as np


DEFAULT_OBJECTIVES = [
    {"metric": "miss_distance_m", "sense": "min"},
    {"metric": "max_qbar_pa", "sense": "min"},
    {"metric": "robustness_margin", "sense": "max"},
]


def as_float(value: Any, default: float = math.nan) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def as_bool(value: Any) -> bool:
    return value in {True, "True", "true", "yes", "1", 1}


def numeric_series(rows: list[dict[str, Any]], key: str) -> np.ndarray:
    return np.array([as_float(row.get(key)) for row in rows], dtype=float)


def numeric_columns(rows: list[dict[str, Any]], *, exclude: set[str] | None = None) -> list[str]:
    excluded = exclude or {"run", "case", "sample", "seed", "success", "failed", "scenario"}
    names: set[str] = set()
    for row in rows:
        for key, value in row.items():
            if key in excluded:
                continue
            if isinstance(value, (int, float)) and math.isfinite(float(value)):
                names.add(key)
    return sorted(names)


def wilson_interval(successes: int, n: int, confidence: float = 0.95) -> tuple[float, float]:
    if n <= 0:
        return 0.0, 0.0
    z = abs(normal_ppf(0.5 + confidence / 2.0))
    phat = successes / n
    denom = 1.0 + z * z / n
    center = (phat + z * z / (2.0 * n)) / denom
    half = z * math.sqrt((phat * (1.0 - phat) + z * z / (4.0 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def normal_ppf(p: float) -> float:
    """Acklam approximation for the inverse standard normal CDF."""

    if not 0.0 < p < 1.0:
        if p == 0.0:
            return -math.inf
        if p == 1.0:
            return math.inf
        raise ValueError("p must be in [0, 1]")
    a = [
        -3.969683028665376e01,
        2.209460984245205e02,
        -2.759285104469687e02,
        1.383577518672690e02,
        -3.066479806614716e01,
        2.506628277459239e00,
    ]
    b = [
        -5.447609879822406e01,
        1.615858368580409e02,
        -1.556989798598866e02,
        6.680131188771972e01,
        -1.328068155288572e01,
    ]
    c = [
        -7.784894002430293e-03,
        -3.223964580411365e-01,
        -2.400758277161838e00,
        -2.549732539343734e00,
        4.374664141464968e00,
        2.938163982698783e00,
    ]
    d = [
        7.784695709041462e-03,
        3.224671290700398e-01,
        2.445134137142996e00,
        3.754408661907416e00,
    ]
    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    if p > phigh:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / (
            (((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0
        )
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / (
        ((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0
    )


def bootstrap_ci(values: np.ndarray, statistic: str = "mean", confidence: float = 0.95, resamples: int = 400, seed: int = 2026) -> dict[str, float]:
    finite = values[np.isfinite(values)]
    if len(finite) == 0:
        return {"estimate": math.nan, "low": math.nan, "high": math.nan}
    rng = np.random.default_rng(seed)
    fn = np.median if statistic == "median" else np.mean
    draws = np.array([float(fn(rng.choice(finite, size=len(finite), replace=True))) for _ in range(max(20, resamples))], dtype=float)
    alpha = (1.0 - confidence) / 2.0
    return {"estimate": float(fn(finite)), "low": float(np.quantile(draws, alpha)), "high": float(np.quantile(draws, 1.0 - alpha))}


def objective_value(row: dict[str, Any], objective: dict[str, Any]) -> float:
    value = as_float(row.get(str(objective.get("metric", ""))), 0.0)
    return value if objective.get("sense", "min") == "min" else -value


def dominates(a: dict[str, Any], b: dict[str, Any], objectives: list[dict[str, Any]]) -> bool:
    av = [objective_value(a, objective) for objective in objectives]
    bv = [objective_value(b, objective) for objective in objectives]
    return all(left <= right for left, right in zip(av, bv)) and any(left < right for left, right in zip(av, bv))


def is_feasible(row: dict[str, Any], constraints: dict[str, Any] | None = None) -> bool:
    rules = constraints or {"require_success": False}
    if rules.get("require_success") and "success" in row and not as_bool(row.get("success")):
        return False
    for metric, rule in rules.items():
        if metric == "require_success" or not isinstance(rule, dict):
            continue
        value = as_float(row.get(metric))
        if "max" in rule and value > float(rule["max"]):
            return False
        if "min" in rule and value < float(rule["min"]):
            return False
    return True


def pareto_front(rows: list[dict[str, Any]], objectives: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    objectives = objectives or DEFAULT_OBJECTIVES
    front: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if any(dominates(other, row, objectives) for other_index, other in enumerate(rows) if other_index != index):
            continue
        next_row = dict(row)
        next_row["pareto"] = True
        front.append(next_row)
    return front


def score_designs(
    rows: list[dict[str, Any]],
    *,
    objectives: list[dict[str, Any]] | None = None,
    constraints: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    objectives = objectives or DEFAULT_OBJECTIVES
    ranked = [dict(row) for row in rows]
    for row in ranked:
        row["feasible"] = is_feasible(row, constraints)
        row["dominance_rank"] = sum(1 for other in ranked if other is not row and dominates(other, row, objectives))
    for objective in objectives:
        metric = str(objective.get("metric", ""))
        values = numeric_series(ranked, metric)
        finite = values[np.isfinite(values)]
        if len(finite) <= 1 or float(np.ptp(finite)) <= 1e-12:
            scores = np.full(len(values), 0.5)
        else:
            order = np.argsort(np.where(np.isfinite(values), values, np.nanmax(finite)))
            if objective.get("sense", "min") == "max":
                order = order[::-1]
            scores = np.zeros(len(values), dtype=float)
            scores[order] = np.linspace(1.0, 0.0, len(values))
        for row, score in zip(ranked, scores):
            row[f"{metric}_percentile_score"] = float(score)
    for row in ranked:
        objective_scores = [as_float(row.get(f"{objective.get('metric')}_percentile_score"), 0.0) for objective in objectives]
        row["percentile_score"] = float(np.mean(objective_scores)) if objective_scores else 0.0
    ranked.sort(key=lambda item: (not bool(item.get("feasible")), int(item.get("dominance_rank", 999)), -as_float(item.get("percentile_score"), 0.0)))
    return ranked


def sensitivity_table(samples: list[dict[str, Any]], results: list[dict[str, Any]], metrics: list[str] | None = None) -> list[dict[str, Any]]:
    features = numeric_columns(samples)
    metrics = metrics or [
        metric
        for metric in ["miss_distance_m", "final_altitude_m", "max_qbar_pa", "max_load_factor_g", "robustness_margin"]
        if any(math.isfinite(as_float(row.get(metric))) for row in results)
    ]
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        y = numeric_series(results, metric)
        for feature in features:
            x = numeric_series(samples, feature)
            mask = np.isfinite(x) & np.isfinite(y)
            if int(mask.sum()) < 3 or float(np.std(x[mask])) <= 1e-12 or float(np.std(y[mask])) <= 1e-12:
                continue
            corr = float(np.corrcoef(x[mask], y[mask])[0, 1])
            rows.append({"parameter": feature, "metric": metric, "correlation": corr, "abs_correlation": abs(corr), "samples": int(mask.sum())})
    rows.sort(key=lambda row: float(row["abs_correlation"]), reverse=True)
    return rows


def reliability_summary(results: list[dict[str, Any]], *, margin_metric: str = "robustness_margin") -> dict[str, Any]:
    n = len(results)
    successes = sum(1 for row in results if as_bool(row.get("success")))
    low, high = wilson_interval(successes, n)
    margins = numeric_series(results, margin_metric)
    failures: dict[str, int] = {}
    for row in results:
        if as_bool(row.get("success")):
            continue
        reason = str(row.get("failure_reason", "failed"))
        failures[reason] = failures.get(reason, 0) + 1
    p = successes / max(n, 1)
    return {
        "runs": n,
        "successes": successes,
        "failures": n - successes,
        "success_probability": p,
        "success_probability_low": low,
        "success_probability_high": high,
        "reliability_index": float(normal_ppf(min(max(p, 1e-9), 1.0 - 1e-9))),
        "margin_metric": margin_metric,
        "margin_mean": float(np.nanmean(margins)) if len(margins) else math.nan,
        "margin_p05": float(np.nanpercentile(margins, 5)) if len(margins) else math.nan,
        "failure_modes": [
            {"failure_reason": reason, "count": count, "fraction_of_runs": count / max(n, 1)}
            for reason, count in sorted(failures.items(), key=lambda item: item[1], reverse=True)
        ],
    }


def uq_summary(results: list[dict[str, Any]], *, metric: str = "miss_distance_m") -> dict[str, Any]:
    values = numeric_series(results, metric)
    success_count = sum(1 for row in results if as_bool(row.get("success")))
    low, high = wilson_interval(success_count, len(results))
    finite = values[np.isfinite(values)]
    quantiles = {f"q{int(q * 100):02d}": float(np.quantile(finite, q)) for q in [0.05, 0.25, 0.5, 0.75, 0.95]} if len(finite) else {}
    return {
        "metric": metric,
        "runs": len(results),
        "bootstrap_mean": bootstrap_ci(values, "mean"),
        "bootstrap_median": bootstrap_ci(values, "median"),
        "quantiles": quantiles,
        "success_probability": {"estimate": success_count / max(len(results), 1), "low": low, "high": high},
    }


def fit_surrogate_model(
    samples: list[dict[str, Any]],
    results: list[dict[str, Any]],
    *,
    metric: str = "miss_distance_m",
    degree: int = 2,
    ridge: float = 1e-6,
) -> dict[str, Any]:
    features = numeric_columns(samples)
    if not features:
        raise ValueError("no numeric sample features available for surrogate fitting")
    x = np.array([[as_float(row.get(name)) for name in features] for row in samples], dtype=float)
    y = numeric_series(results, metric)
    mask = np.isfinite(y) & np.all(np.isfinite(x), axis=1)
    x = x[mask]
    y = y[mask]
    if len(y) < max(4, len(features) + 1):
        raise ValueError("not enough finite rows for surrogate fitting")
    x_mean = np.mean(x, axis=0)
    x_scale = np.std(x, axis=0)
    x_scale[x_scale <= 1e-12] = 1.0
    z = (x - x_mean) / x_scale
    terms = _poly_terms(len(features), max(1, min(degree, 2)))
    design = _poly_design(z, terms)
    reg = ridge * np.eye(design.shape[1])
    reg[0, 0] = 0.0
    coef = np.linalg.solve(design.T @ design + reg, design.T @ y)
    pred = design @ coef
    residual = y - pred
    ss_tot = float(np.sum((y - np.mean(y)) ** 2))
    ss_res = float(np.sum(residual**2))
    return {
        "model_type": "polynomial",
        "degree": max(1, min(degree, 2)),
        "metric": metric,
        "features": features,
        "rows": int(len(y)),
        "x_mean": x_mean.tolist(),
        "x_scale": x_scale.tolist(),
        "terms": [list(term) for term in terms],
        "coefficients": coef.tolist(),
        "train_metrics": {
            "rmse": float(np.sqrt(np.mean(residual**2))),
            "mae": float(np.mean(np.abs(residual))),
            "r2": 0.0 if ss_tot <= 1e-12 else float(1.0 - ss_res / ss_tot),
        },
    }


def predict_surrogate_model(model: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    features = [str(feature) for feature in model.get("features", [])]
    if not features:
        return []
    x = np.array([[as_float(row.get(feature), 0.0) for feature in features] for row in rows], dtype=float)
    z = (x - np.array(model["x_mean"], dtype=float)) / np.array(model["x_scale"], dtype=float)
    terms = [tuple(term) for term in model["terms"]]
    pred = _poly_design(z, terms) @ np.array(model["coefficients"], dtype=float)
    return [{**row, f"predicted_{model['metric']}": float(value)} for row, value in zip(rows, pred)]


def optimize_from_surrogate(
    model: dict[str, Any],
    samples: list[dict[str, Any]],
    *,
    candidates: int = 200,
    seed: int = 2026,
) -> list[dict[str, Any]]:
    features = [str(feature) for feature in model.get("features", [])]
    if not features:
        return []
    rng = np.random.default_rng(seed)
    bounds: dict[str, tuple[float, float]] = {}
    for feature in features:
        values = numeric_series(samples, feature)
        finite = values[np.isfinite(values)]
        if len(finite):
            bounds[feature] = (float(np.min(finite)), float(np.max(finite)))
        else:
            bounds[feature] = (0.0, 1.0)
    rows = []
    for index in range(max(1, candidates)):
        row = {"candidate": index}
        for feature, (low, high) in bounds.items():
            row[feature] = float(rng.uniform(low, high)) if abs(high - low) > 1e-12 else low
        rows.append(row)
    predicted = predict_surrogate_model(model, rows)
    metric_key = f"predicted_{model['metric']}"
    predicted.sort(key=lambda row: as_float(row.get(metric_key), math.inf))
    return predicted


def grid_cases(parameters: dict[str, list[Any]], max_cases: int) -> list[dict[str, Any]]:
    keys = list(parameters)
    cases: list[dict[str, Any]] = []
    for values in itertools.product(*(parameters[key] for key in keys)):
        cases.append(dict(zip(keys, values)))
        if len(cases) >= max_cases:
            break
    return cases


def _poly_terms(dim: int, degree: int) -> list[tuple[int, ...]]:
    terms: list[tuple[int, ...]] = [()]
    terms.extend((index,) for index in range(dim))
    if degree >= 2:
        terms.extend((index, index) for index in range(dim))
        terms.extend((left, right) for left in range(dim) for right in range(left + 1, dim))
    return terms


def _poly_design(x: np.ndarray, terms: list[tuple[int, ...]]) -> np.ndarray:
    design = np.ones((len(x), len(terms)), dtype=float)
    for column, term in enumerate(terms):
        for index in term:
            design[:, column] *= x[:, index]
    return design
