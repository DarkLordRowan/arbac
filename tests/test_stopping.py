"""
Тесты критериев остановки.
"""

from __future__ import annotations
from arbacc.core import get
from arbacc.core.accelerator import AlgoState
from arbacc.runner import run_accelerator


def test_max_iter(ctx):
    """max_iter останавливает после N итераций."""
    Cls = get("stopping", "max_iter")
    s = Cls(params={"n": 10})
    state = AlgoState(iteration=10, estimate=ctx.number(0),
                      history=[ctx.number(0)] * 10)
    assert s.should_stop(state, ctx)
    assert "max_iter" in s.reason


def test_max_iter_not_yet(ctx):
    """max_iter не срабатывает до лимита."""
    Cls = get("stopping", "max_iter")
    s = Cls(params={"n": 10})
    state = AlgoState(iteration=5, estimate=ctx.number(0),
                      history=[ctx.number(0)] * 5)
    assert not s.should_stop(state, ctx)


def test_digits_stable(ctx):
    """digits_stable срабатывает при стабилизации."""
    Cls = get("stopping", "digits_stable")
    s = Cls(params={"window": 3, "min_digits": 5})
    v = ctx.number("1.23456789")
    state = AlgoState(iteration=5, estimate=v, history=[v, v, v, v])
    assert s.should_stop(state, ctx)


def test_divergence(ctx):
    """divergence срабатывает при резком росте."""
    Cls = get("stopping", "divergence")
    s = Cls(params={"window": 3, "factor": "10"})
    # История: маленькие значения, потом резкий скачок.
    history = [
        ctx.number("1.0"),
        ctx.number("1.0"),
        ctx.number("1.0"),
        ctx.number("1.0"),
        ctx.number("1e10"),
    ]
    state = AlgoState(iteration=5, estimate=history[-1], history=history)
    assert s.should_stop(state, ctx)