"""Regression tests for backend API instrumentation and event-safe analysis."""
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from arbac_research.profiling import CountingBackend, ProfilingAccelerator
from arbac_research.metrics import summarize_task, aggregate_summaries


class Backend:
    name = "fake"
    def add(self, a, b, dps): return a + b
    def sub(self, a, b, dps): return a - b
    def mul(self, a, b, dps): return a * b
    def div(self, a, b, dps): return a / b
    def neg(self, a, dps): return -a
    def pow(self, a, b, dps): return a ** b


@dataclass(frozen=True)
class Context:
    backend: object
    dps: int = 50


class Accelerator:
    name = "fake"
    params = {}
    def required_input(self, state):
        return state.iteration + 1
    def step(self, source, state, ctx):
        b = ctx.backend
        x = b.add(1, 2, 50)
        x = b.mul(x, 2, 50)
        x = b.div(x, 2, 50)
        x = b.sub(x, 1, 50)
        x = b.neg(x, 50)
        x = b.pow(x, 2, 50)
        return SimpleNamespace(iteration=state.iteration + 1, estimate=x)


class FailingAccelerator(Accelerator):
    def step(self, source, state, ctx):
        return ctx.backend.div(1, 0, 50)


def test_profile_backend_step_counts_and_restores_frozen_context():
    backend = Backend()
    ctx = Context(backend)
    accel = ProfilingAccelerator(Accelerator(), count_backend_ops=True)
    src = [1, 2, 3]
    output = accel.step(src, SimpleNamespace(iteration=0), ctx)
    assert output.iteration == 1
    assert ctx.backend is backend
    rec = accel.measurements[0]
    assert rec["n_used"] == 3 and rec["k"] == 0
    assert rec["op_add"] == 2 and rec["op_mul"] == 1
    assert rec["op_div"] == 1 and rec["op_special"] == 1
    assert rec["op_neg"] == 1 and rec["op_total"] == 6
    assert rec["op_mode"] == "backend_api_step_only"
    assert rec["step_elapsed_ms"] >= 0


def test_profile_off_does_not_fabricate_counters():
    backend=Backend()
    ctx=Context(backend)
    accel=ProfilingAccelerator(Accelerator())
    accel.step([1],SimpleNamespace(iteration=0),ctx)
    assert "op_add" not in accel.measurements[0]
    assert "op_mode" not in accel.measurements[0]
    assert ctx.backend is backend


def test_failure_event_counters_and_no_context_leak():
    backend = Backend()
    ctx = Context(backend)
    accel = ProfilingAccelerator(FailingAccelerator(), count_backend_ops=True)
    with pytest.raises(ZeroDivisionError):
        accel.step([1, 2], SimpleNamespace(iteration=0), ctx)
    assert ctx.backend is backend
    assert not accel.measurements
    assert accel.failures[0]["op_div"] == 1
    assert accel.failures[0]["failure_class"] == "ZeroDivisionError"
    assert accel.failures[0]["n_used"] == 2


def trace_row(row_type, n, v, **kw):
    row = dict(task_id="abc", row_type=row_type, n_used=n, k=n, value=v,
               exact_sum="1", series_id="s", class_id="power", accel_id="a",
               method_id="m", backend="mpmath", dps=50, status="failed",
               failure="ZeroDivisionError", elapsed_ms=10)
    row.update(kw)
    return row


def test_offline_event_rows_do_not_count_as_invalid_estimates():
    rows = [
        trace_row("baseline", 2, "1.01"),
        trace_row("accel", 2, "1.0001", op_add=3, op_mul=2,
                  op_div=1, op_neg=0, op_special=1, op_total=7,
                  op_mode="backend_api_step_only", step_elapsed_ms=0.5),
        trace_row("event", 3, None, event_type="step_failure",
                  event_message="ZeroDivisionError: division by zero",
                  op_add=0, op_mul=0, op_div=1, op_neg=0,
                  op_special=0, op_total=1, op_mode="backend_api_step_only"),
        trace_row("event", 3, None, event_type="runner_stop",
                  event_message="exception: ZeroDivisionError"),
    ]
    t = summarize_task(rows)
    assert t["n_accel_valid"] == 1
    assert t["n_points_invalid"] == 0
    assert t["n_events"] == 2 and t["n_step_failures"] == 1
    assert t["op_add"] == 3 and t["op_div"] == 2 and t["op_total"] == 8
    assert t["n_profiled_steps"] == 2
    assert t["division_zero_first_n"] == 3
    assert t["division_zero_recovered"] == 0
    assert t["stop_reason"] == "exception: ZeroDivisionError"
    assert t["c1"] == 1 and t["c5"] == 0
    group=aggregate_summaries([t])[0]
    assert group["tasks_with_profile"]==1
    assert group["op_total"]==8
    assert group["step_failures"]==1


def test_v1_compatibility_missing_event_and_counts_is_null():
    rows=[trace_row("baseline",1,"1.01",status="ok",failure=None),
          trace_row("accel",1,"1.001",status="ok",failure=None)]
    result=summarize_task(rows)
    assert result["op_add"] is None
    assert result["op_total"] is None
    assert result["n_profiled_steps"] == 0
    assert result["n_events"] == 0
    assert result["division_zero_first_n"] is None
    group=aggregate_summaries([result])[0]
    assert group["op_add"] is None
    assert group["tasks_with_profile"] == 0
