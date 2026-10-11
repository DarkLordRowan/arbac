"""
Тесты всех серий.
"""

from __future__ import annotations
import pytest

from arbacc.core import get
from tests.conftest import KNOWN


# --- Параметризация по сериям -----------------------------------------------

@pytest.mark.parametrize("s", [2, 3, 4, 5, 10, 20])
def test_zeta_first_terms(s, ctx):
    """zeta(s): a_0 = 1, a_1 = 1/2^s."""
    Cls = get("series", "zeta")
    z = Cls(params={"s": s})
    stream = z.build_stream(ctx)
    b = ctx.backend
    a0 = stream.get(0)
    a1 = stream.get(1)
    assert b.digits_of(a0, ctx.number("1.0"), 50) >= 48
    expected_a1 = b.pow(ctx.number(2), b.neg(ctx.number(s), 50), 50)
    assert b.digits_of(a1, expected_a1, 50) >= 48


@pytest.mark.parametrize("q", ["0.5", "0.7", "0.9", "-0.3", "0.99"])
def test_geometric_first_terms(q, ctx):
    """geometric(q): a_n = q^n."""
    Cls = get("series", "geometric")
    g = Cls(params={"q": q})
    stream = g.build_stream(ctx)
    b = ctx.backend
    q_num = ctx.number(q)
    for n in range(5):
        expected = b.pow(q_num, ctx.number(n), 50)
        assert b.digits_of(stream.get(n), expected, 50) >= 48


@pytest.mark.parametrize("x", ["0.6", "1", "2"])
def test_cos_sin_analytic(x, ctx):
    """cos/sin: analytic_sum = backend.cos/sin."""
    b = ctx.backend
    for name, fn in [("cos", b.cos), ("sin", b.sin)]:
        Cls = get("series", name)
        s = Cls(params={"x": x})
        got = s.analytic_sum(ctx)
        expected = fn(ctx.number(x), 50)
        d = b.digits_of(got, expected, 50)
        assert d >= 48, f"{name}({x}): {d} знаков"


def test_zeta3_analytic(ctx):
    """zeta(3) через backend.zeta совпадает с константой."""
    Cls = get("series", "zeta")
    z = Cls(params={"s": 3})
    got = z.analytic_sum(ctx)
    expected = ctx.number(KNOWN["zeta3"])
    d = ctx.backend.digits_of(got, expected, 50)
    assert d >= 48


def test_from_file_missing(ctx, tmp_path):
    """from_file: несуществующий файл → FileNotFoundError."""
    Cls = get("series", "from_file")
    s = Cls(params={"path": str(tmp_path / "nonexistent.csv")})
    with pytest.raises(FileNotFoundError):
        s.build_stream(ctx).get(0)