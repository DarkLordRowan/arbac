"""
Акселераторы на зашумлённых рядах.

Проверяет, что акселератор не хуже сырой суммы того же числа членов —
и на чистом ряду, и на зашумлённом.
"""

from __future__ import annotations
import pytest

from arbacc.core import get
from arbacc.runner import run_accelerator


@pytest.mark.parametrize("accel", ["aitken_delta2", "wynn_epsilon"])
@pytest.mark.parametrize("sigma", ["0", "1e-6", "1e-3"])
def test_accel_on_noisy_zeta3(accel, sigma, ctx):
    """
    Акселератор даёт не меньше цифр, чем сырая сумма того же числа
    членов, для чистого и зашумлённого zeta(3).
    """
    ZetaCls = get("series", "zeta")
    AccelCls = get("accelerators", accel)
    MaxIterCls = get("stopping", "max_iter")

    N = 100
    exact = ctx.number(
        "1.2020569031595942853997381615114499907649862923404988817923412"
    )
    b = ctx.backend

    def _make_stream():
        s = ZetaCls(params={"s": 3}).build_stream(ctx)
        if sigma != "0":
            NoiseCls = get("noise", "gaussian")
            s = NoiseCls(
                params={"sigma": sigma, "mode": "absolute"}, seed=42,
            ).wrap(s, ctx)
        return s

    # Ускоренный результат.
    r = run_accelerator(
        source=_make_stream(),
        accelerator=AccelCls(params={}),
        stopping_criteria=[MaxIterCls(params={"n": N})],
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx,
        n_max=500,
    )
    d_acc = b.digits_of(r.estimate, exact, ctx.dps)

    # Сырая сумма N членов того же (за)шумлённого ряда.
    raw = _make_stream()
    total = ctx.number(0)
    for n in range(N):
        total = b.add(total, raw.get(n), ctx.dps)
    d_raw = b.digits_of(total, exact, ctx.dps)

    # Требование: акселератор не хуже сырого ряда (с запасом в 1 цифру).
    # Это «сходимость», а не «обязательно больше» — на линейно
    # сходящихся рядах Aitken лишь немного лучше сырого.
    assert d_acc >= d_raw - 1, (
        f"{accel}, sigma={sigma}: акселератор {d_acc} цифр, "
        f"сырой ряд {d_raw} цифр"
    )