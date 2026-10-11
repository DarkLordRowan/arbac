"""
Тесты огибающих.
"""

from __future__ import annotations
import pytest

from arbacc.core import get


@pytest.fixture
def trajectory(ctx):
    """
    Траектория оценок для огибающей: сходящаяся с колебаниями.
    Значения: 1 + 0.1*sin(k) / (k+1).
    """
    import math
    b = ctx.backend
    out = []
    for k in range(100):
        v = 1.0 + 0.1 * math.sin(k) / (k + 1)
        out.append(ctx.number(str(v)))
    return out


@pytest.mark.parametrize("env_name", ["hilbert", "emd"])
@pytest.mark.parametrize("used_as", ["observer", "stopping_criterion"])
def test_envelope_runs(env_name, used_as, trajectory, ctx):
    """Огибающая работает в обоих режимах used_as."""
    Cls = get("envelopes", env_name)
    env = Cls(params={"window": 11, "threshold": 0.5,
                      "min_history": 20, "used_as": used_as})
    for v in trajectory:
        env.push(v)
    result = env.result()
    assert "envelope" in result
    assert result["envelope"] == env_name


@pytest.mark.parametrize("env_name", ["hilbert", "emd"])
def test_envelope_has_upper_lower(env_name, trajectory, ctx):
    """Огибающая возвращает envelope_upper, envelope_lower, indices."""
    Cls = get("envelopes", env_name)
    env = Cls(params={"window": 11, "threshold": 0.5, "min_history": 20})
    for v in trajectory:
        env.push(v)
    result = env.result()
    assert isinstance(result["envelope_upper"], list)
    assert isinstance(result["envelope_lower"], list)
    assert isinstance(result["envelope_indices"], list)
    # Длины совпадают.
    n = len(result["envelope_upper"])
    assert len(result["envelope_lower"]) == n
    assert len(result["envelope_indices"]) == n