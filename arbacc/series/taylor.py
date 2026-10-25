"""Verified Maclaurin series ported from shanks-university (zero-based terms).

Sources: NIST DLMF https://dlmf.nist.gov/4.6, /4.19, /4.24, /4.33.
All arithmetic uses the selected backend and ctx.dps; Python integers are exact.
The analytic sum is available only inside the stated real convergence domain.
"""
from math import comb

from arbacc.core.registry import register
from arbacc.core.series import SeriesBase


class _Taylor(SeriesBase):
    PARAM_SPEC = {"x": {"type": "str", "required": True, "default": "0.5", "short": "x"}}
    unit_domain = False

    def argument(self, ctx):
        x = ctx.number(self.params["x"])
        if not ctx.backend.is_finite(x, ctx.dps):
            raise ValueError("x must be finite")
        if self.unit_domain and ctx.backend.sign(
            ctx.backend.sub(ctx.number(1), ctx.backend.abs_val(x, ctx.dps), ctx.dps), ctx.dps
        ) <= 0:
            raise ValueError("This Taylor series requires |x| < 1")
        return x

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        x = self.argument(ctx)
        exponent, coefficient, denominator = self.coefficient(n)
        return b.div(b.mul(ctx.number(coefficient), b.pow(x, ctx.number(exponent), d), d),
                     ctx.number(denominator), d)


@register("series", "exp")
class ExpSeries(_Taylor):
    name = display_name = "exp"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        return ctx.backend.div(ctx.backend.pow(self.argument(ctx), ctx.number(n), ctx.dps),
                               ctx.backend.factorial(n, ctx.dps), ctx.dps)

    def analytic_sum(self, ctx):
        return ctx.backend.exp(self.argument(ctx), ctx.dps)


@register("series", "ln1mx")
class MinusLogOneMinusX(_Taylor):
    name = display_name = "ln1mx"
    unit_domain = True

    def coefficient(self, n):
        return n + 1, 1, n + 1

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.neg(b.log(b.sub(ctx.number(1), self.argument(ctx), d), d), d)


@register("series", "log1p")
class LogOnePlusX(MinusLogOneMinusX):
    name = display_name = "log1p"

    def coefficient(self, n):
        return n + 1, (-1)**n, n + 1

    def analytic_sum(self, ctx):
        return ctx.backend.log(ctx.backend.add(ctx.number(1), self.argument(ctx), ctx.dps), ctx.dps)


@register("series", "arctan_x")
class ArctanSeries(_Taylor):
    name = display_name = "arctan_x"
    unit_domain = True

    def coefficient(self, n):
        return 2*n + 1, (-1)**n, 2*n + 1

    def analytic_sum(self, ctx):
        return ctx.backend.atan(self.argument(ctx), ctx.dps)


@register("series", "arctanh_x")
class ArctanhSeries(_Taylor):
    name = display_name = "arctanh_x"
    unit_domain = True

    def coefficient(self, n):
        return 2*n + 1, 1, 2*n + 1

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(b.log(b.div(b.add(ctx.number(1), x, d), b.sub(ctx.number(1), x, d), d), d), ctx.number(2), d)


@register("series", "arcsin_x")
class ArcsinSeries(_Taylor):
    name = display_name = "arcsin_x"
    unit_domain = True

    def coefficient(self, n):
        return 2*n + 1, comb(2*n, n), 4**n * (2*n + 1)

    def analytic_sum(self, ctx):
        return ctx.backend.asin(self.argument(ctx), ctx.dps)


@register("series", "arcsinh_x")
class ArcsinhSeries(ArcsinSeries):
    name = display_name = "arcsinh_x"

    def coefficient(self, n):
        e, c, q = super().coefficient(n)
        return e, c * (-1)**n, q

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        root = b.pow(b.add(ctx.number(1), b.mul(x, x, d), d), ctx.number("0.5"), d)
        return b.log(b.add(x, root, d), d)


@register("series", "inverse_sqrt_1m4x")
class InverseSqrtSeries(_Taylor):
    name = display_name = "inverse_sqrt_1m4x"
    PARAM_SPEC = {"x": {"type": "str", "required": True, "default": "0.1", "short": "x"}}

    def argument(self, ctx):
        x = super().argument(ctx)
        if ctx.backend.sign(ctx.backend.sub(ctx.number("0.25"), ctx.backend.abs_val(x, ctx.dps), ctx.dps), ctx.dps) <= 0:
            raise ValueError("This series requires |x| < 1/4")
        return x

    def coefficient(self, n):
        return n, comb(2*n, n), 1

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.pow(b.sub(ctx.number(1), b.mul(ctx.number(4), self.argument(ctx), d), d), ctx.number("-0.5"), d)


@register("series", "one_minus_sqrt_1minus4x_div_2x")
class CatalanSeries(InverseSqrtSeries):
    name = "one_minus_sqrt_1minus4x_div_2x"
    display_name = "catalan"

    def coefficient(self, n):
        return n, comb(2*n, n) // (n + 1), 1

    def analytic_sum(self, ctx):
        # Rationalized form is defined also at x=0.
        b, d = ctx.backend, ctx.dps
        root = b.pow(b.sub(ctx.number(1), b.mul(ctx.number(4), self.argument(ctx), d), d), ctx.number("0.5"), d)
        return b.div(ctx.number(2), b.add(ctx.number(1), root, d), d)


@register("series", "sqrt_1plusx")
class SqrtOnePlusX(_Taylor):
    name = display_name = "sqrt_1plusx"
    unit_domain = True

    def coefficient(self, n):
        if n == 0:
            return 0, 1, 1
        return n, (-1)**(n-1) * comb(2*n, n), 4**n * (2*n-1)

    def analytic_sum(self, ctx):
        return ctx.backend.pow(ctx.backend.add(ctx.number(1), self.argument(ctx), ctx.dps), ctx.number("0.5"), ctx.dps)


@register("series", "sinh")
class SinhSeries(ExpSeries):
    name = display_name = "sinh"

    def generate(self, n, ctx):
        return super().generate(2*n + 1, ctx)

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(b.sub(b.exp(x, d), b.exp(b.neg(x, d), d), d), ctx.number(2), d)


@register("series", "cosh")
class CoshSeries(ExpSeries):
    name = display_name = "cosh"

    def generate(self, n, ctx):
        return super().generate(2*n, ctx)

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(b.add(b.exp(x, d), b.exp(b.neg(x, d), d), d), ctx.number(2), d)


@register("series", "x_div_1minx")
class XOverOneMinusX(_Taylor):
    """Legacy C++ id: the denominator is sqrt(1-x)."""
    name = display_name = "x_div_1minx"
    unit_domain = True

    def coefficient(self, n):
        return n + 1, comb(2*n, n), 4**n

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(x, b.pow(b.sub(ctx.number(1), x, d), ctx.number("0.5"), d), d)


@register("series", "x_div_1minx2")
class XOverOneMinusXSquared(XOverOneMinusX):
    name = display_name = "x_div_1minx2"

    def coefficient(self, n):
        return 2*n + 1, comb(2*n, n), 4**n

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(x, b.pow(b.sub(ctx.number(1), b.mul(x, x, d), d), ctx.number("0.5"), d), d)


@register("series", "x_1mx_squared")
class XOverSquaredOneMinusX(XOverOneMinusX):
    name = display_name = "x_1mx_squared"

    def coefficient(self, n):
        return n + 1, n + 1, 1

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.div(x, b.pow(b.sub(ctx.number(1), x, d), ctx.number(2), d), d)


@register("series", "sqrt_1plusx_min_1_min_x_div_2")
class SqrtRemainder(SqrtOnePlusX):
    name = "sqrt_1plusx_min_1_min_x_div_2"
    display_name = "sqrt_remainder"

    def coefficient(self, n):
        return super().coefficient(n+2)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.sub(b.sub(super().analytic_sum(ctx), ctx.number(1), d),
                     b.div(self.argument(ctx), ctx.number(2), d), d)
