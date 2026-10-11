"""
Проверка, что backend уважает dps независимо от глобального состояния.

Это ключевой тест: раньше mpmath_backend полагался на глобальный
mp.mp.dps, который мог быть «унаследован» из другого места.
Context.__post_init__ + backend.activate() решают это.
"""

from __future__ import annotations
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends


@pytest.mark.parametrize("backend_name", list_backends())
@pytest.mark.parametrize("dps", [20, 50, 100])
def test_backend_respects_dps(backend_name, dps):
    """Backend даёт цифры в соответствии с dps Context'а."""
    b = get_backend(backend_name)

    # Намеренно портим глобальное состояние mpmath, но восстанавливаем
    # его через Context.activate() — этот тест проверяет ровно то,
    # что Context не полагается на глобальное состояние.
    try:
        import mpmath as mp
        original_dps = mp.mp.dps
        mp.mp.dps = 15
    except ImportError:
        original_dps = None

    # Создание Context должно активировать dps.
    ctx = Context(backend=b, dps=dps)

    # Два числа, различающиеся в (dps-1) знаке.
    a_str = "1." + "0" * (dps - 2) + "1"
    b_str = "1." + "0" * (dps - 1)
    x = ctx.number(a_str)
    y = ctx.number(b_str)
    d = b.digits_of(x, y, dps)
    assert d >= dps - 5, (
        f"{backend_name} dps={dps}: только {d} цифр "
        f"(ожидалось ≥ {dps - 5})"
    )
    try:
        if original_dps is not None:
            mp.mp.dps = original_dps
    except Exception:
        pass

    assert d >= dps - 5, (
        f"{backend_name} dps={dps}: только {d} цифр "
        f"(ожидалось ≥ {dps - 5})"
    )    


@pytest.mark.parametrize("backend_name", list_backends())
def test_context_activation_survives_switch(backend_name):
    """Переключение dps туда-обратно не ломает точность."""
    b = get_backend(backend_name)
    Context(backend=b, dps=20)
    Context(backend=b, dps=100)
    ctx = Context(backend=b, dps=20)  # вернулись к 20

    s = "1." + "0" * 10 + "1"
    x = ctx.number(s)
    y = ctx.number("1." + "0" * 11)
    d = b.digits_of(x, y, 20)
    assert d >= 10, f"{backend_name}: после switch только {d} цифр"


@pytest.mark.parametrize("backend_name", list_backends())
def test_two_contexts_same_dps(backend_name):
    """Два Context'а с одинаковым dps не мешают друг другу."""
    b = get_backend(backend_name)
    ctx1 = Context(backend=b, dps=50)
    ctx2 = Context(backend=b, dps=50)
    x1 = ctx1.number("1." + "0" * 48 + "1")
    x2 = ctx2.number("1." + "0" * 49)
    d = b.digits_of(x1, x2, 50)
    assert d >= 45