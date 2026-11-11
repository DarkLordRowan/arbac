"""Verify that optional backend call-counting did not change numeric results."""
from __future__ import annotations
from .storage import iterate_tasks


def _numeric_records(path):
    tasks={}
    for trace in iterate_tasks(path):
        if not trace:continue
        tid=str(trace[0]["task_id"])
        if tid in tasks:
            raise ValueError(f"duplicate task_id across shards: {tid}")
        # Ignore timing and metadata; compare ALL numeric samples and statuses.
        tasks[tid]=sorted((str(r.get("row_type")),int(r.get("n_used") or 0),
                           int(r.get("k") or 0) if r.get("k") is not None else None,
                           str(r.get("value")) if r.get("value") is not None else None,
                           str(r.get("base_value")) if r.get("base_value") is not None else None)
                          for r in trace if r.get("row_type") in ("baseline", "accel"))
    return tasks


def verify_profile_equivalence(plain, profiled):
    """Exact serialized values and budgets must agree across both datasets.

    This guards against the instrumenting adapter changing the mathematical
    computation. It does not prove that the algorithm itself is correct.
    """
    a,b=_numeric_records(plain),_numeric_records(profiled)
    missing=sorted(a.keys()-b.keys())
    extra=sorted(b.keys()-a.keys())
    bad=[tid for tid in sorted(a.keys() & b.keys()) if a[tid] != b[tid]]
    return {"ok":not(missing or extra or bad),"tasks_plain":len(a),
            "tasks_profiled":len(b),"missing_tasks":missing[:20],
            "extra_tasks":extra[:20],"different_numeric_traces":bad[:20]}
