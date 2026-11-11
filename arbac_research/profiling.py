"""Optional *algorithm-step-only* instrumentation for the Arbac precision API.

Counts calls through ctx.backend inside accelerator.step, rather than machine
operations or all arithmetic performed by a 3rd-party library. A method that
uses mpmath directly, or one backend operation that performs many internal
operations, is not fully represented by these counters.

Used only when research.profile_backend_ops=true, because instrumentation
necessarily adds overhead. Never benchmark elapsed time with profiling on and
compare it to non-instrumented runs as though they were equivalent.
"""
from __future__ import annotations
from collections import Counter
from time import perf_counter_ns

# These are backend API calls, NOT C++ profiling events / hardware counters.
CATEGORIES = {
    "add": "op_add", "sub": "op_add", "mul": "op_mul", "div": "op_div",
    "neg": "op_neg", "pow": "op_special", "sqrt": "op_special",
    "log": "op_special", "exp": "op_special", "sin": "op_special",
    "cos": "op_special", "tan": "op_special", "sinh": "op_special",
    "cosh": "op_special", "atan": "op_special", "asin": "op_special",
    "zeta": "op_special", "gamma": "op_special", "factorial": "op_special",
}
CATEGORY_NAMES = ("op_add", "op_mul", "op_div", "op_neg", "op_special")


class CountingBackend:
    """Transparent delegation of precision methods with per-step counters."""
    def __init__(self, delegate):
        self._delegate = delegate
        self.counts = Counter()

    def __getattr__(self, name):
        attr = getattr(self._delegate, name)
        category = CATEGORIES.get(name)
        if category is None or not callable(attr):
            return attr

        def counted(*args, **kwargs):
            self.counts[category] += 1
            return attr(*args, **kwargs)
        return counted


def _snapshot(counts):
    result = {key: int(counts.get(key, 0)) for key in CATEGORY_NAMES}
    result["op_total"] = sum(result.values())
    return result


class ProfilingAccelerator:
    """Adapter for Arbac's Accelerator contract, without modifying its source.

    Only the `step` call is timed and (optionally) counted; source generation
    done by runner before `step` is deliberately excluded. On exception, a
    structured failure event retains the attempted step's input count.
    """
    def __init__(self, accelerator, *, count_backend_ops=False):
        self._delegate = accelerator
        self.count_backend_ops = bool(count_backend_ops)
        self.measurements = []
        self.failures = []

    def __getattr__(self, name):
        return getattr(self._delegate, name)

    def required_input(self, state):
        return self._delegate.required_input(state)

    def step(self, source, state, ctx):
        real_backend = ctx.backend
        proxy = CountingBackend(real_backend) if self.count_backend_ops else None
        n_used = len(source)
        start = perf_counter_ns()
        try:
            if proxy is not None:
                # Arbac Context is frozen; temporary mutation affects this
                # worker's local Context, NOT the global backend registry.
                object.__setattr__(ctx, "backend", proxy)
            state_next = self._delegate.step(source, state, ctx)
        except Exception as exc:
            rec = self._record(start, n_used, state.iteration, proxy, ok=False)
            rec["failure_class"] = type(exc).__name__
            rec["failure_message"] = str(exc)
            self.failures.append(rec)
            raise
        finally:
            if proxy is not None:
                object.__setattr__(ctx, "backend", real_backend)
        rec = self._record(start, n_used, state_next.iteration - 1, proxy, ok=True)
        self.measurements.append(rec)
        return state_next

    @staticmethod
    def _record(start, n_used, k, proxy, *, ok):
        record = {"n_used": int(n_used), "k": int(k), "step_elapsed_ms":
                  (perf_counter_ns()-start)/1_000_000, "profile_ok": ok}
        if proxy is not None:
            record.update(_snapshot(proxy.counts))
            record["op_mode"] = "backend_api_step_only"
        return record
