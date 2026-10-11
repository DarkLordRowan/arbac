"""
Семантика огибающих: находят ли они точку выхода на плато.
"""

from __future__ import annotations
import math

import pytest

from arbacc.core import get


@pytest.mark.parametrize("env_name", ["hilbert", "emd"])
def test_envelope_detects_plateau(env_name, ctx):
    """Огибающая находит точку выхода на плато."""
    Cls = get("envelopes", env_name)

    vals = []
    for k in range(100):
        if k < 40:
            v = 1.0 + 0.1 * math.sin(k * 0.7) * math.exp(-k / 15)
        else:
            v = 1.0
        vals.append(ctx.number(str(v)))

    env = Cls(params={
        "window": 11,
        "detrend_window": 11,
        "threshold": 0.3,
        "min_history": 20,
    })
    for v in vals:
        env.push(v)

    result = env.result()
    s = result["suggested_stop_at"]
    assert s is not None, f"{env_name}: плато не найдено"
    assert 20 <= s <= 90, f"{env_name}: suggested_stop_at={s} вне [20, 90]"