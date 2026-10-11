"""
Онлайн-огибающая: run_mode="during" реально останавливает акселератор.
"""

from __future__ import annotations

from arbacc.core import get
from arbacc.runner import run_accelerator


def test_envelope_during_stops(ctx):
    """Огибающая с run_mode=during останавливает акселератор."""
    HilbertCls = get("envelopes", "hilbert")
    env = HilbertCls(params={
        "window": 11,
        "threshold": 0.5,
        "min_history": 20,
        "run_mode": "during",
        "used_as": "stopping_criterion",
    })

    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    r = run_accelerator(
        source=ZetaCls(params={"s": 3}).build_stream(ctx),
        accelerator=AitkenCls(params={}),
        stopping_criteria=[MaxIterCls(params={"n": 5000})],
        stopping_mode="any",
        online_envelopes=[env],
        ctx=ctx,
        n_max=10000,
    )
    assert "envelope" in r.stopped_by, (
        f"огибающая не остановила: stopped_by={r.stopped_by}"
    )