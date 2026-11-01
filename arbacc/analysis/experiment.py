"""Experiment matrices and reports for the TypeScript experiment JSON schema.

Ports the computation behind AlgorithmSeriesView, profilingUtils and ranking
views in shanks-university/frontend/web/frontend/src/widgets. UI styling,
React state and browser downloads are deliberately outside this Python API.
Errors retain backend precision; profiling counters remain exact Python ints.
Rankings compare observed finite trajectories, not convergence proofs.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from arbacc.convergence import analyze_convergence


def analyze_profiling(points):
    """Port profilingUtils.ts, including gaps resetting total comparisons."""
    previous = None
    previous_kinds = {}
    deltas, decreases = [], []
    maxima, kind_decreases = {}, {}
    maximum = maximum_n = None
    for point in sorted(points, key=lambda p: p["n"]):
        n = point["n"]
        counters = {}
        for key in ("add", "mul", "div", "special"):
            value = (point.get("profiling") or {}).get(key)
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError("profiling counters must be nonnegative integers")
            counters[key] = value
            if key not in maxima or value > maxima[key]["max"]:
                maxima[key] = {"max": value, "n": n}
            if key in previous_kinds and value < previous_kinds[key]:
                kind_decreases.setdefault(key, []).append(n)
            previous_kinds[key] = value
        total = sum(counters.values()) if counters else None
        if total is not None and (maximum is None or total > maximum):
            maximum, maximum_n = total, n
        if previous is not None and total is not None:
            delta = total-previous
            deltas.append(delta)
            if delta < 0:
                decreases.append(n)
        previous = total
    trend = ("unknown" if not deltas else "decreasing_error" if any(v < 0 for v in deltas)
             else "constant" if all(v == 0 for v in deltas)
             else "increasing" if all(v > 0 for v in deltas) else "non_decreasing")
    return {"steps_analyzed": len(deltas), "trend_total": trend,
            "max_total_ops": maximum, "max_total_ops_n": maximum_n,
            "decrease_ns_total": decreases, "max_by_kind": maxima,
            "decrease_ns_by_kind": kind_decreases,
            "top_kinds": sorted(maxima, key=lambda k: -maxima[k]["max"])[:8]}


def _error_summary(errors, epsilon, ctx):
    b, d = ctx.backend, ctx.dps
    if not errors:
        return {"count": 0, "min": None, "min_n": None, "last": None,
                "first_tolerance_n": None, "mean": None}
    minimum_n, minimum = errors[0]
    total = ctx.number(0)
    first_tolerance = None
    for n, error in errors:
        total = b.add(total, error, d)
        if b.sign(b.sub(error, minimum, d), d) < 0:
            minimum_n, minimum = n, error
        if first_tolerance is None and b.sign(b.sub(error, epsilon, d), d) <= 0:
            first_tolerance = n
    return {"count": len(errors), "min": minimum, "min_n": minimum_n,
            "last": errors[-1][1], "first_tolerance_n": first_tolerance,
            "mean": b.div(total, ctx.number(len(errors)), d)}


def build_experiment_matrix(experiment, ctx, *, epsilon="1e-10",
                            series_ids=None, accel_ids=None):
    """Build sparse cells keyed by (series_id, accel_id), preserving identities.

    Optional sets filter axes. Missing pairs stay absent; duplicate IDs/pairs
    raise instead of silently replacing measurements. Unknown references raise.
    No binary64 conversion is used, including for subnormal-sized errors.
    """
    b, d = ctx.backend, ctx.dps
    threshold = ctx.number(epsilon)
    if not b.is_finite(threshold, d) or b.sign(threshold, d) < 0:
        raise ValueError("epsilon must be finite and nonnegative")
    def index(items):
        result = {}
        for item in items:
            if item["id"] in result:
                raise ValueError("duplicate experiment identifier")
            result[item["id"]] = item
        return result
    all_series = index(experiment.get("seriesList", []))
    all_accels = index(experiment.get("accelList", []))
    series = {k: v for k, v in all_series.items() if series_ids is None or k in series_ids}
    accels = {k: v for k, v in all_accels.items() if accel_ids is None or k in accel_ids}
    cells, seen = {}, set()
    for run in experiment.get("seriesAccelList", []):
        sid, aid = run["series_id"], run["accel_id"]
        key = sid, aid
        if sid not in all_series or aid not in all_accels:
            raise ValueError("unknown experiment reference")
        if key in seen:
            raise ValueError("duplicate series/accelerator measurement")
        seen.add(key)
        if sid not in series or aid not in accels:
            continue
        points = run.get("computed") or []
        convergence = analyze_convergence(points, series[sid].get("limit"), ctx)
        cells[key] = {"series_id": sid, "accel_id": aid,
                      "convergence": convergence,
                      "error": _error_summary(convergence["errors"], threshold, ctx),
                      "profiling": analyze_profiling(points),
                      "failures": len(run.get("errors") or [])}
    return {"series": series, "accelerators": accels, "cells": cells}


def rank_algorithms(matrix, ctx):
    """Dense rank by mean best absolute error, with exact ties.

    This explicit metric is a Python report option, not the browser's composite
    score. Empty/unknown-reference trajectories remain unranked, not zero-error.
    Comparisons across unlike scales should use separately filtered matrices.
    """
    from functools import cmp_to_key
    b, d = ctx.backend, ctx.dps
    rows = []
    for aid in matrix["accelerators"]:
        cells = [c for (_, a), c in matrix["cells"].items() if a == aid]
        valid = [c for c in cells if c["error"]["min"] is not None]
        total = ctx.number(0)
        for cell in valid:
            total = b.add(total, cell["error"]["min"], d)
        rows.append({"accel_id": aid, "trajectories": len(cells), "known_errors": len(valid),
                     "reached_tolerance": sum(c["error"]["first_tolerance_n"] is not None for c in valid),
                     "mean_best_error": b.div(total, ctx.number(len(valid)), d) if valid else None,
                     "rank": None})
    def compare(left, right):
        x, y = left["mean_best_error"], right["mean_best_error"]
        if x is None or y is None:
            return (x is None)-(y is None)
        return b.sign(b.sub(x, y, d), d)
    rows.sort(key=cmp_to_key(compare))
    rank, previous = 0, None
    for row in rows:
        if row["mean_best_error"] is None:
            continue
        if previous is None or compare(previous, row):
            rank += 1
        row["rank"], previous = rank, row
    return rows


def export_experiment_report(matrix, path, ctx):
    """Export flat matrix CSV or full JSON, storing backend numbers as strings.

    JSON uses an array of cells (tuple dictionary keys are not JSON keys).
    Numeric strings preserve precision and Arb radii via the backend serializer.
    """
    path = Path(path)
    def serialize(value):
        if value is None or isinstance(value, (str, int, bool, float)):
            return value
        if isinstance(value, dict):
            return {k: serialize(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)):
            return [serialize(v) for v in value]
        return ctx.backend.to_str(value, ctx.dps)
    rows = [{"series_id": c["series_id"], "accel_id": c["accel_id"],
             **c["error"], "side": c["convergence"]["side"],
             "monotonicity": c["convergence"]["monotonicity"],
             "max_total_ops": c["profiling"]["max_total_ops"], "failures": c["failures"]}
            for c in matrix["cells"].values()]
    if path.suffix.lower() == ".csv":
        fields = ["series_id", "accel_id", "count", "min", "min_n", "last", "first_tolerance_n", "mean", "side", "monotonicity", "max_total_ops", "failures"]
        with path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields)
            writer.writeheader()
            writer.writerows(serialize(rows))
    elif path.suffix.lower() == ".json":
        report = {"series": matrix["series"], "accelerators": matrix["accelerators"],
                  "cells": list(matrix["cells"].values()), "ranking": rank_algorithms(matrix, ctx)}
        path.write_text(json.dumps(serialize(report), ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    else:
        raise ValueError("report extension must be .csv or .json")
