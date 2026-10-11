"""
Тесты фильтров.
"""

from __future__ import annotations
import pytest

from arbacc.core import get


@pytest.fixture
def estimates(ctx):
    """Траектория оценок — имитация итераций акселератора."""
    b = ctx.backend
    return [b.add(ctx.number("1.0"),
                  b.div(ctx.number(i), ctx.number(1000), 50), 50)
            for i in range(50)]


@pytest.mark.parametrize("window", [3, 5, 7])
@pytest.mark.parametrize("passes", [1, 2, 3])
def test_kz(window, passes, estimates, ctx):
    """KZ работает при разных window/passes."""
    Cls = get("postprocess", "kolmogorov_zurbenko")
    kz = Cls(params={"window": window, "passes": passes})
    post = kz.apply(estimates, ctx)
    assert post.final is not None
    assert len(post.values) <= len(estimates)


@pytest.mark.parametrize("window,order", [(5, 1), (5, 2), (7, 2), (7, 3)])
def test_sg(window, order, estimates, ctx):
    """SG работает при разных window/order."""
    Cls = get("postprocess", "savitzky_golay")
    sg = Cls(params={"window": window, "order": order})
    post = sg.apply(estimates, ctx)
    assert post.final is not None


@pytest.mark.parametrize("window", [3, 5, 7])
def test_median(window, estimates, ctx):
    """median работает при разных окнах."""
    Cls = get("postprocess", "median")
    med = Cls(params={"window": window})
    post = med.apply(estimates, ctx)
    assert post.final is not None


def test_kz_odd_window_required(estimates, ctx):
    """KZ требует нечётное окно."""
    Cls = get("postprocess", "kolmogorov_zurbenko")
    kz = Cls(params={"window": 4, "passes": 1})
    with pytest.raises(ValueError):
        kz.apply(estimates, ctx)