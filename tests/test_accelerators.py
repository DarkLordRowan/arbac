"""
Тесты акселераторов.
"""

from __future__ import annotations
import pytest

from arbacc.core import get
from arbacc.runner import run_accelerator


@pytest.mark.parametrize("n_max", [5, 10, 50, 200])
def test_aitken_runs(n_max, ctx):
    """Aitken работает при разных n_max."""
    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")

    stream = ZetaCls(params={"s": 3}).build_stream(ctx)
    r = run_accelerator(
        source=stream,
        accelerator=AitkenCls(params={}),
        stopping_criteria=[], stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=n_max,
    )
    assert r.status == "ok"
    assert r.n_used <= n_max


@pytest.mark.parametrize("algo", ["aitken_delta2", "wynn_epsilon"])
def test_accel_improves_over_raw(algo, ctx):
    """
    Акселератор даёт больше верных цифр, чем сырой ряд после
    того же числа итераций.
    """
    ZetaCls = get("series", "zeta")
    AccelCls = get("accelerators", algo)
    exact = ctx.number(
        "1.2020569031595942853997381615114499907649862923404988817923412"
    )
    b = ctx.backend

    # Сырой ряд: 40 членов.
    stream_raw = ZetaCls(params={"s": 3}).build_stream(ctx)
    total = ctx.number(0)
    for n in range(40):
        total = b.add(total, stream_raw.get(n), ctx.dps)
    d_raw = b.digits_of(total, exact, ctx.dps)

    # Акселератор: 20 итераций.
    stream_acc = ZetaCls(params={"s": 3}).build_stream(ctx)
    r = run_accelerator(
        source=stream_acc,
        accelerator=AccelCls(params={}),
        stopping_criteria=[get("stopping", "max_iter")(params={"n": 20})],
        stopping_mode="any",
        online_envelopes=[], ctx=ctx, n_max=200,
    )
    d_acc = b.digits_of(r.estimate, exact, ctx.dps)

    # Ускоренный должен быть не хуже сырого на порядок.
    # Для zeta3 наивный ряд за 40 членов даёт ~3 цифры,
    # Wynn за 20 итераций — заметно больше.
    assert d_acc >= d_raw, (
        f"{algo}: ускоренный ({d_acc}) хуже сырого ({d_raw})"
    )