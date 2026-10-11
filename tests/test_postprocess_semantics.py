"""
Семантика постобработки: фильтры действительно сглаживают,
а не просто не падают.
"""

from __future__ import annotations
import statistics

from arbacc.core import get


def test_kz_reduces_variance(ctx):
    """KZ действительно сглаживает: std(выход) < std(вход)."""
    KZCls = get("postprocess", "kolmogorov_zurbenko")

    vals = [1.0 + 0.1 * ((-1) ** i) for i in range(50)]
    estimates = [ctx.number(str(v)) for v in vals]

    kz = KZCls(params={"window": 5, "passes": 3})
    post = kz.apply(estimates, ctx)

    std_in = statistics.pstdev([float(v) for v in estimates])
    std_out = statistics.pstdev([float(v) for v in post.values])
    assert std_out < std_in * 0.5, (
        f"KZ не сглаживает: std_in={std_in:.4f}, std_out={std_out:.4f}"
    )


def test_median_removes_outlier(ctx):
    """Медиана убирает единственный выброс в середине."""
    MedCls = get("postprocess", "median")
    vals = [1.0] * 25 + [100.0] + [1.0] * 24
    estimates = [ctx.number(str(v)) for v in vals]

    med = MedCls(params={"window": 5})
    post = med.apply(estimates, ctx)

    for v in post.values:
        assert abs(float(v) - 1.0) < 0.5, f"выброс прошёл: {v}"