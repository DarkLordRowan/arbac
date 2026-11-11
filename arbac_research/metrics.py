"""High-precision, run-independent research metrics for Arbac trace Parquet.

All error metrics are computed OFFLINE using the reference limit (when present).
The best step and the best configuration are ORACLE choices, not implementable
online stopping policies. Never interpret finite trajectory metrics as proofs.

Two different gains are intentionally distinct:
  gain_best_orders: baseline error at THE SAME number of original inputs as
      the oracle-best accelerated approximation. This is the paper's G_j.
  cpp_orders_gain_vs_series_min: best original error / best accelerated error
      across their independent trajectories (C++ ranking convention).
Do not merge these into a single column.
"""
from __future__ import annotations
from collections import Counter
from statistics import median
from typing import Any
import mpmath as mp

METRICS_SCHEMA_VERSION = 3


def number(value: Any):
    """Parse high-precision real/complex data without converting via float."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, dict):
            re = mp.mpf(str(value.get("re", value.get("real", 0))))
            im = mp.mpf(str(value.get("im", value.get("imag", 0))))
            result = mp.mpc(re, im)
        else:
            s = str(value).strip().replace(" ", "")
            if s.startswith("(") and s.endswith(")"):
                s = s[1:-1]
            if s.lower().endswith("j"):
                body = s[:-1]
                split_at = None
                for i in range(1, len(body)):
                    if body[i] in "+-" and body[i - 1] not in "eE":
                        split_at = i
                if split_at is None:
                    result = mp.mpc(0, mp.mpf(body or "1"))
                else:
                    result = mp.mpc(mp.mpf(body[:split_at]), mp.mpf(body[split_at:]))
            else:
                result = mp.mpf(s)
        return result if mp.isfinite(result) else None
    except (ValueError, TypeError, ArithmeticError):
        return None


def metric_number(value):
    """Metrics may contain exact infinities; trace samples may not."""
    if value is None or str(value).lower() in ("", "none"):
        return None
    if str(value).lower().lstrip("+") in ("inf", "infinity"):
        return mp.inf
    if str(value).lower() in ("-inf", "-infinity"):
        return -mp.inf
    return number(value)


def fmt(x: Any, precision: int = 40) -> str | None:
    if x is None:
        return None
    return mp.nstr(x, n=max(15, int(precision)))


def gain(base_err, accelerated_err):
    """Decimal orders of ABSOLUTE error reduction, not a multiplicative factor."""
    if base_err is None or accelerated_err is None:
        return None
    if base_err == 0 and accelerated_err == 0:
        return None
    if accelerated_err == 0:
        return mp.inf if base_err > 0 else None
    if base_err == 0:
        return -mp.inf
    return mp.log10(base_err) - mp.log10(accelerated_err)


def cpp_orders_gain(base_err, accelerated_err):
    """Mirror C++ AlgoRankingTable.model.ts computeOrdersGain zero conventions.

    Unlike mathematical log(base/accelerated), the C++ ranking returns a
    FINITE magnitude at exact zero; this rule is kept only in cpp_* columns.
    """
    if base_err is None or accelerated_err is None:
        return None
    if base_err == 0:
        return mp.mpf(0) if accelerated_err == 0 else -abs(mp.log10(accelerated_err))
    if accelerated_err == 0:
        return abs(mp.log10(base_err))
    return gain(base_err, accelerated_err)


def _sample_sign(v, limit):
    if v is None or limit is None:
        return None
    difference = v - limit
    if isinstance(difference, mp.mpc) and difference.imag != 0:
        return None  # one/two-sided is only meaningful for real-valued errors
    return int(mp.sign(mp.re(difference)))


def _mp_stat(xs, op="median", precision=40):
    vals = [metric_number(v) for v in xs if v is not None]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    vals.sort()
    if op == "min": return fmt(vals[0], precision)
    if op == "max": return fmt(vals[-1], precision)
    if op == "mean":
        if mp.inf in vals and -mp.inf in vals:
            return None
        return fmt(sum(vals) / len(vals), precision)
    m = len(vals) // 2
    if len(vals) % 2:
        return fmt(vals[m], precision)
    if vals[m - 1] == vals[m]:
        return fmt(vals[m], precision)
    if not mp.isfinite(vals[m - 1]) or not mp.isfinite(vals[m]):
        return None if vals[m - 1] == -mp.inf and vals[m] == mp.inf else fmt(vals[m - 1] if mp.isinf(vals[m - 1]) else vals[m], precision)
    return fmt((vals[m - 1] + vals[m]) / 2, precision)


def _quantile(xs, q, precision=30):
    vals = sorted(v for raw in xs if (v := metric_number(raw)) is not None)
    if not vals:
        return None
    pos = (len(vals) - 1) * q
    a, b = int(pos), min(len(vals) - 1, int(pos) + 1)
    if a == b or vals[a] == vals[b]:
        return fmt(vals[a], precision)
    if not mp.isfinite(vals[a]) or not mp.isfinite(vals[b]):
        return None
    return fmt(vals[a] * (1 - (pos - a)) + vals[b] * (pos - a), precision)


def _monotonicity(inc: int, dec: int, eq: int) -> str:
    if inc + dec + eq == 0: return "unknown"
    if inc and dec: return "nonmonotonic"
    if inc and eq: return "nondecreasing_error"
    if inc: return "strictly_increasing_error"
    if dec and eq: return "nonincreasing_error"
    if dec: return "strictly_decreasing_error"
    return "constant_error"


def _failure_category(status, failure):
    if str(status) == "ok" and not failure:
        return None
    msg = str(failure or "").lower()
    if "zerodivision" in msg or "division by zero" in msg or "divide by zero" in msg or "деление на ноль" in msg:
        return "division_zero"
    if "overflow" in msg: return "overflow"
    if "timeout" in msg: return "timeout"
    if "invalid" in msg or "valueerror" in msg: return "invalid_input"
    if "arith" in msg: return "arithmetic"
    return "other_failure" if str(status) in ("failed", "error", "crashed", "timeout") or failure else None


def summarize_task(rows: list[dict], epsilon: str = "1e-8", precision: int | None = None) -> dict:
    """Recompute all possible metrics from one stored trace; no Arbac import.

    Missing reference, baseline, profiling or filter events are NULL (not zero).
    Uses all valid prefix estimates from failed trajectories. Success is an
    offline measure: first epsilon earlier if baseline reached epsilon; if not,
    best accelerated approximation must improve baseline at the SAME budget.
    """
    if not rows:
        raise ValueError("cannot summarize empty task")
    first = rows[0]
    p = max(40, int(precision or first.get("dps") or 50) + 20)
    with mp.workdps(p):
        eps = number(epsilon)
        if eps is None or eps <= 0:
            raise ValueError("epsilon must be finite and positive")
        limit = number(first.get("exact_sum"))
        baseline: dict[int, Any] = {}
        accels: list[tuple[int, int, Any]] = []
        invalid_points = 0
        events = []
        valid_step_times = []
        # Record operation API calls only if explicitly instrumented; older
        # trace v1 files retain NULL rather than becoming false zeros.
        op_categories = ("op_add", "op_mul", "op_div", "op_neg", "op_special", "op_total")
        op_sums = {key: 0 for key in op_categories}
        op_mode = None
        profiled_steps = 0
        for row in rows:
            n = int(row.get("n_used") or 0)
            typ = row.get("row_type", "accel")
            if typ == "event":
                events.append(row)
                # Failed step operations count toward total attempted work.
                if row.get("event_type") == "step_failure" and row.get("op_mode"):
                    profiled_steps += 1
                    op_mode = row.get("op_mode")
                    for key in op_categories:
                        op_sums[key] += int(row.get(key) or 0)
                continue
            if n <= 0: continue
            if typ == "accel":
                if row.get("step_elapsed_ms") is not None:
                    valid_step_times.append(row["step_elapsed_ms"])
                if row.get("op_mode"):
                    profiled_steps += 1
                    op_mode = row.get("op_mode")
                    for key in op_categories:
                        op_sums[key] += int(row.get(key) or 0)
            val = number(row.get("value"))
            if val is None:
                invalid_points += 1
                continue
            if typ == "baseline":
                baseline[n] = val
            elif typ == "accel":
                accels.append((n, int(row.get("k") or 0), val))
            else:
                raise ValueError(f"unknown row_type: {typ!r}")
        # A compatible imported dataset may store baseline only on accel rows.
        for row in rows:
            if row.get("row_type", "accel") == "accel":
                n = int(row.get("n_used") or 0)
                val = number(row.get("base_value"))
                if n > 0 and val is not None:
                    baseline.setdefault(n, val)
        accels.sort(key=lambda v: (v[0], v[1]))
        status = next((r.get("status") for r in rows if r.get("status")), "unknown")
        failure = next((r.get("failure") for r in rows if r.get("failure")), None)
        category = _failure_category(status, failure)
        out = {
            "metrics_schema_version": METRICS_SCHEMA_VERSION,
            "task_id": str(first.get("task_id", "")),
            "series_id": str(first.get("series_id", "")),
            "class_id": str(first.get("class_id", "")),
            "accel_id": str(first.get("accel_id", "")),
            "method_id": str(first.get("method_id") or first.get("accel_id", "")),
            "noise_id": str(first.get("noise_id", "")),
            "backend": str(first.get("backend", "")),
            "dps": int(first.get("dps") or 0),
            "status": status, "failure": failure, "failure_category": category,
            "baseline_failure": first.get("baseline_failure"),
            "reference_failure": first.get("reference_failure"),
            "params_json": first.get("params_json"),
            "epsilon": str(epsilon),
            "reference_available": int(limit is not None),
            "n_accel_valid": len(accels), "n_baseline_valid": len(baseline),
            "n_points_invalid": invalid_points,
            "n_steps_comparable": 0, "n_steps_better": 0,
            "n_steps_worse": 0, "n_steps_equal": 0, "step_better_share": None,
            "elapsed_ms": first.get("elapsed_ms"),
            "best_n": None, "best_k": None,
            "last_n": None, "last_k": None,
            "base_first_epsilon_n": None, "accel_first_epsilon_n": None,
            "epsilon_saved_terms": None, "base_reached_epsilon": None,
            "accel_reached_epsilon": None, "epsilon_earlier": None,
            "successful_acceleration": None,
            "division_zero_failure": int(category == "division_zero"),
            "best_error": None, "last_error": None,
            "base_min_error": None, "base_last_error": None,
            "base_error_at_best_n": None, "base_error_at_last_n": None,
            "gain_best_orders": None, "gain_last_orders": None,
            "last_best_loss_orders": None,
            "step_gain_mean_orders": None, "step_gain_median_orders": None,
            "step_gain_min_orders": None, "step_gain_max_orders": None,
            "relative_error_best": None,
            "cpp_relative_error_vs_series_min": None,
            "cpp_orders_gain_vs_series_min": None,
            "cpp_amp_at_best_n_orders": None,
            "cpp_step_series_amp_mean_orders": None,
            "cpp_step_series_amp_median_orders": None,
            "cpp_step_series_amp_worst_orders": None,
            "one_sided": None, "sign_changes": None, "side_type": None,
            "error_increases": None, "error_decreases": None, "error_equals": None,
            "error_monotonicity": None, "error_increase_share": None,
            "c1": None, "c5": None,
            # The v1 trace has no such observations. Never fabricate them.
            "op_add": None, "op_mul": None, "op_div": None, "op_special": None,
            "filter_trigger_n": None, "filter_trigger_loss_orders": None,
            "division_zero_first_n": None, "division_zero_recovered": None,
            "n_events": len(events), "n_step_failures": sum(e.get("event_type") == "step_failure" for e in events),
            "stop_reason": next((e.get("event_message") for e in reversed(events) if e.get("event_type") == "runner_stop"), None),
            "profile_mode": op_mode, "n_profiled_steps": profiled_steps,
            "op_neg": None, "op_total": None,
            "step_elapsed_ms_sum": None, "step_elapsed_ms_median": None,
        }
        if op_mode is not None:
            for key in op_categories:
                out[key] = op_sums[key]
        if valid_step_times:
            out["step_elapsed_ms_sum"] = sum(valid_step_times)
            out["step_elapsed_ms_median"] = _mp_stat(valid_step_times)
        first_div0 = next((e for e in events if e.get("event_type") == "step_failure" and
                           _failure_category("failed", e.get("event_message")) == "division_zero"), None)
        if first_div0:
            out["division_zero_first_n"] = int(first_div0.get("n_used") or 0)
            # The current runner stops on exception; a future recoverable
            # runner can update this from subsequent valid step events.
            out["division_zero_recovered"] = int(any(
                int(r.get("n_used") or 0) > out["division_zero_first_n"]
                for r in rows if r.get("row_type") == "accel" and number(r.get("value")) is not None))
            out["division_zero_failure"] = 1
        if limit is None or not accels:
            return out
        errors = [(n, k, abs(v - limit), v) for n, k, v in accels]
        best = min(errors, key=lambda z: (z[2], z[0], z[1]))
        last = errors[-1]
        out["best_n"], out["best_k"] = best[0], best[1]
        out["last_n"], out["last_k"] = last[0], last[1]
        out["best_error"], out["last_error"] = fmt(best[2], p), fmt(last[2], p)
        out["last_best_loss_orders"] = fmt(gain(last[2], best[2]), p)

        baseline_errors = {n: abs(v - limit) for n, v in baseline.items()}
        if baseline_errors:
            n0, bmin = min(baseline_errors.items(), key=lambda x: (x[1], x[0]))
            nb = max(baseline_errors)
            out["base_min_error"] = fmt(bmin, p)
            out["base_last_error"] = fmt(baseline_errors[nb], p)
            out["cpp_orders_gain_vs_series_min"] = fmt(cpp_orders_gain(bmin, best[2]), p)
            if bmin > 0:
                out["cpp_relative_error_vs_series_min"] = fmt(best[2] / bmin, p)
            elif bmin == best[2] == 0:
                out["cpp_relative_error_vs_series_min"] = "1"
        original_at_best = baseline_errors.get(best[0])
        original_at_last = baseline_errors.get(last[0])
        out["base_error_at_best_n"] = fmt(original_at_best, p)
        out["base_error_at_last_n"] = fmt(original_at_last, p)
        g_best = gain(original_at_best, best[2])
        g_last = gain(original_at_last, last[2])
        out["gain_best_orders"] = fmt(g_best, p)
        out["gain_last_orders"] = fmt(g_last, p)
        out["cpp_amp_at_best_n_orders"] = fmt(cpp_orders_gain(original_at_best, best[2]), p)
        if limit != 0:
            out["relative_error_best"] = fmt(best[2] / abs(limit), p)
        out["c1"] = None if g_best is None else int(g_best >= 1)
        out["c5"] = None if g_best is None else int(g_best >= 5)

        # Per-output-step matched-budget comparison to original sequence.
        step_gains = []
        step_amplifications = []
        for n, k, err, val in errors:
            if n not in baseline_errors:
                continue
            base_err = baseline_errors[n]
            out["n_steps_comparable"] += 1
            out["n_steps_better"] += int(err < base_err)
            out["n_steps_worse"] += int(err > base_err)
            out["n_steps_equal"] += int(err == base_err)
            step_gain = gain(base_err, err)
            if step_gain is not None:
                step_gains.append(step_gain)
            # C++ stepSeriesAmp compares |A_m-S_m| against |S_m-S|,
            # not against the true error |A_m-S|. Keep a separate field.
            step_amp = cpp_orders_gain(base_err, abs(val - baseline[n]))
            if step_amp is not None:
                step_amplifications.append(step_amp)
        if out["n_steps_comparable"]:
            out["step_better_share"] = out["n_steps_better"] / out["n_steps_comparable"]
        out["step_gain_mean_orders"] = _mp_stat(step_gains, "mean", p)
        out["step_gain_median_orders"] = _mp_stat(step_gains, "median", p)
        out["step_gain_min_orders"] = _mp_stat(step_gains, "min", p)
        out["step_gain_max_orders"] = _mp_stat(step_gains, "max", p)
        out["cpp_step_series_amp_mean_orders"] = _mp_stat(step_amplifications, "mean", p)
        out["cpp_step_series_amp_median_orders"] = _mp_stat(step_amplifications, "median", p)
        out["cpp_step_series_amp_worst_orders"] = _mp_stat(step_amplifications, "min", p)

        base_eps = next((n for n, e in sorted(baseline_errors.items()) if e < eps), None)
        accel_eps = next((n for n, _, err, _ in errors if err < eps), None)
        out["base_first_epsilon_n"] = base_eps
        out["accel_first_epsilon_n"] = accel_eps
        out["base_reached_epsilon"] = int(base_eps is not None) if baseline_errors else None
        out["accel_reached_epsilon"] = int(accel_eps is not None)
        if base_eps is not None and accel_eps is not None:
            out["epsilon_saved_terms"] = base_eps - accel_eps
            out["epsilon_earlier"] = int(accel_eps < base_eps)
        elif base_eps is None and baseline_errors and accel_eps is not None:
            out["epsilon_earlier"] = 1  # baseline censored within the saved budget
        if baseline_errors:
            if base_eps is None:
                out["successful_acceleration"] = (int(best[2] < original_at_best)
                                                  if original_at_best is not None else None)
            else:
                out["successful_acceleration"] = int(accel_eps is not None and accel_eps < base_eps)

        signs = [_sample_sign(v, limit) for _, _, _, v in errors]
        if all(s is not None for s in signs):
            signs = [s for s in signs if s != 0]
            changes = sum(a != b for a, b in zip(signs, signs[1:]))
            out["sign_changes"] = changes
            out["one_sided"] = int(changes == 0)
            out["side_type"] = "one_sided" if changes == 0 else "two_sided"
        inc = sum(y[2] > x[2] for x, y in zip(errors, errors[1:]))
        dec = sum(y[2] < x[2] for x, y in zip(errors, errors[1:]))
        eq = sum(y[2] == x[2] for x, y in zip(errors, errors[1:]))
        out["error_increases"], out["error_decreases"], out["error_equals"] = inc, dec, eq
        out["error_monotonicity"] = _monotonicity(inc, dec, eq)
        if len(errors) > 1:
            out["error_increase_share"] = inc / (len(errors) - 1)
        return out


def aggregate_summaries(summaries: list[dict], group_by: list[str] | None = None,
                        *, per_task: bool = False) -> list[dict]:
    """Aggregate over unique cases, with an explicitly labelled oracle policy.

    When several parameter configs are present, choose max matched-budget G
    separately within each (series, class, noise) and group. This is NOT
    cross-validated parameter selection. Counts of failures refer to *tasks*,
    while coverage/counts refer to distinct *cases*.
    """
    group_by = group_by or ["method_id", "backend", "dps"]
    groups: dict[tuple, list[dict]] = {}
    for row in summaries:
        groups.setdefault(tuple(row.get(k) for k in group_by), []).append(row)
    out = []
    for key, items in sorted(groups.items(), key=lambda kv: repr(kv[0])):
        cases: dict[tuple, list[dict]] = {}
        for idx, item in enumerate(items):
            case_key = (idx,) if per_task else (item.get("series_id"), item.get("class_id"), item.get("noise_id"))
            cases.setdefault(case_key, []).append(item)
        selected = []
        for case_items in cases.values():
            valid = [(metric_number(x.get("gain_best_orders")), x) for x in case_items]
            valid = [(g, x) for g, x in valid if g is not None]
            if valid:
                selected.append(max(valid, key=lambda p: p[0])[1])
        gains = [x.get("gain_best_orders") for x in selected]
        elapsed = [x.get("elapsed_ms") for x in items if x.get("elapsed_ms") is not None]
        gain_vals = [metric_number(g) for g in gains if g is not None]
        c1 = sum(g >= 1 for g in gain_vals)
        c5 = sum(g >= 5 for g in gain_vals)
        eligible = len(selected)
        data = dict(zip(group_by, key))
        data.update({
            "tasks": len(items), "cases": len(cases), "comparable": eligible,
            "uncomparable_cases": len(cases) - eligible,
            "c1": c1, "c5": c5,
            "c1_share": c1 / eligible if eligible else None,
            "c5_share": c5 / eligible if eligible else None,
            "successful_acceleration_cases": sum(x.get("successful_acceleration") == 1 for x in selected),
            "epsilon_reached_cases": sum(x.get("accel_reached_epsilon") == 1 for x in selected),
            "epsilon_earlier_cases": sum(x.get("epsilon_earlier") == 1 for x in selected),
            "cases_with_failure": sum(any(x.get("failure_category") for x in xs) for xs in cases.values()),
            "failed": sum(bool(x.get("failure_category")) for x in items),
            "unknown_status": sum(str(x.get("status")) == "unknown" for x in items),
            "failure_share": sum(bool(x.get("failure_category")) for x in items) / len(items),
            "division_zero_failures": sum(x.get("division_zero_failure") or 0 for x in items),
            "aggregation_policy": "per_configuration" if per_task else "best_configuration_per_case_ORACLE",
            "median_gain_orders": _mp_stat(gains, "median", 25),
            "mean_gain_orders": _mp_stat(gains, "mean", 25),
            "min_gain_orders": _mp_stat(gains, "min", 25),
            "max_gain_orders": _mp_stat(gains, "max", 25),
            "p05_gain_orders": _quantile(gains, 0.05),
            "p95_gain_orders": _quantile(gains, 0.95),
            "median_last_gain_orders": _mp_stat([x.get("gain_last_orders") for x in selected]),
            "median_cpp_orders_gain": _mp_stat([x.get("cpp_orders_gain_vs_series_min") for x in selected]),
            "median_best_error": _mp_stat([x.get("best_error") for x in selected]),
            "median_last_error": _mp_stat([x.get("last_error") for x in selected]),
            "median_last_best_loss_orders": _mp_stat([x.get("last_best_loss_orders") for x in selected]),
            "median_step_better_share": _mp_stat([x.get("step_better_share") for x in selected]),
            "median_epsilon_saved_terms": _mp_stat([x.get("epsilon_saved_terms") for x in selected]),
            "median_best_n": _mp_stat([x.get("best_n") for x in selected]),
            "median_last_n": _mp_stat([x.get("last_n") for x in selected]),
            "one_sided_cases": sum(x.get("one_sided") == 1 for x in selected),
            "nonincreasing_error_cases": sum(x.get("error_monotonicity") in ("nonincreasing_error", "strictly_decreasing_error", "constant_error") for x in selected),
            "median_sign_changes": _mp_stat([x.get("sign_changes") for x in selected]),
            "median_error_increases": _mp_stat([x.get("error_increases") for x in selected]),
            "median_error_increase_share": _mp_stat([x.get("error_increase_share") for x in selected]),
            "median_elapsed_ms": _mp_stat(elapsed, "median", 20),
            "mean_elapsed_ms": _mp_stat(elapsed, "mean", 20),
            "min_elapsed_ms": _mp_stat(elapsed, "min", 20),
            "max_elapsed_ms": _mp_stat(elapsed, "max", 20),
            "median_n_accel_valid": _mp_stat([x.get("n_accel_valid") for x in selected]),
            "tasks_with_profile": sum(bool(x.get("profile_mode")) for x in items),
            "profiled_steps": sum(int(x.get("n_profiled_steps") or 0) for x in items),
            "profile_modes": ", ".join(sorted({str(x["profile_mode"]) for x in items if x.get("profile_mode")})) or None,
            "op_add": sum(int(x["op_add"]) for x in items if x.get("op_add") is not None) if any(x.get("op_add") is not None for x in items) else None,
            "op_mul": sum(int(x["op_mul"]) for x in items if x.get("op_mul") is not None) if any(x.get("op_mul") is not None for x in items) else None,
            "op_div": sum(int(x["op_div"]) for x in items if x.get("op_div") is not None) if any(x.get("op_div") is not None for x in items) else None,
            "op_neg": sum(int(x["op_neg"]) for x in items if x.get("op_neg") is not None) if any(x.get("op_neg") is not None for x in items) else None,
            "op_special": sum(int(x["op_special"]) for x in items if x.get("op_special") is not None) if any(x.get("op_special") is not None for x in items) else None,
            "op_total": sum(int(x["op_total"]) for x in items if x.get("op_total") is not None) if any(x.get("op_total") is not None for x in items) else None,
            "median_op_total_per_profiled_task": _mp_stat([x.get("op_total") for x in items]),
            "median_step_elapsed_ms_sum": _mp_stat([x.get("step_elapsed_ms_sum") for x in items]),
            "step_failures": sum(int(x.get("n_step_failures") or 0) for x in items),
            "events_recorded": sum(int(x.get("n_events") or 0) for x in items),
            "median_division_zero_first_n": _mp_stat([x.get("division_zero_first_n") for x in items]),
        })
        out.append(data)
    return out
