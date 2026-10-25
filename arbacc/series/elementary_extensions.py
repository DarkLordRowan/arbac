"""Further verified C++ series, with original registry ids and indexing.

NIST DLMF: https://dlmf.nist.gov/4.6, /4.19, /4.24, /6.6, /7.6.
In the historical catalogue `erf` denotes integral_0^x exp(-t^2) dt,
NOT the normalized error function. Constants use backend precision.
"""
from math import comb

from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor, ArctanSeries, ArcsinSeries, ExpSeries


@register("series", "bin")
class BinomialSeries(_Taylor):
    name = display_name = "bin"
    unit_domain = True
    PARAM_SPEC = {**_Taylor.PARAM_SPEC,
                  "alpha": {"type": "str", "required": True, "default": "0.5", "short": "a"}}

    def exponent(self, ctx):
        alpha = ctx.number(self.params["alpha"])
        if not ctx.backend.is_finite(alpha, ctx.dps):
            raise ValueError("alpha must be finite")
        return alpha

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d, x, alpha = ctx.backend, ctx.dps, self.argument(ctx), self.exponent(ctx)
        coefficient = ctx.number(1)
        for j in range(n):
            coefficient = b.div(b.mul(coefficient, b.sub(alpha, ctx.number(j), d), d), ctx.number(j+1), d)
        return b.mul(coefficient, b.pow(x, ctx.number(n), d), d)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.pow(b.add(ctx.number(1), self.argument(ctx), d), self.exponent(ctx), d)


@register("series", "m_fact_1mx_mp1_inverse")
class GeometricDerivative(_Taylor):
    name = "m_fact_1mx_mp1_inverse"
    display_name = "geom_derivative"
    unit_domain = True
    PARAM_SPEC = {**_Taylor.PARAM_SPEC,
                  "m": {"type": "int", "required": True, "default": 2, "min": 0, "short": "m"}}

    def __init__(self, params, **kwargs):
        super().__init__(params, **kwargs)
        self.m = self.params["m"]
        if isinstance(self.m, bool) or not isinstance(self.m, int) or self.m < 0:
            raise ValueError("m must be a nonnegative integer")

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        coefficient = b.div(b.factorial(n+self.m, d), b.factorial(n, d), d)
        return b.mul(coefficient, b.pow(self.argument(ctx), ctx.number(n), d), d)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.div(b.factorial(self.m, d), b.pow(b.sub(ctx.number(1), self.argument(ctx), d), ctx.number(self.m+1), d), d)


@register("series", "four_arctan")
class FourArctan(ArctanSeries):
    name = display_name = "four_arctan"

    def coefficient(self, n):
        e, c, q = super().coefficient(n)
        return e, 4*c, q

    def analytic_sum(self, ctx):
        return ctx.backend.mul(ctx.number(4), super().analytic_sum(ctx), ctx.dps)


@register("series", "arcsin_x_minus_x")
class ArcsinRemainder(ArcsinSeries):
    name = display_name = "arcsin_x_minus_x"

    def coefficient(self, n):
        return super().coefficient(n+1)

    def analytic_sum(self, ctx):
        return ctx.backend.sub(super().analytic_sum(ctx), self.argument(ctx), ctx.dps)


@register("series", "half_asin_two_x")
class HalfArcsinDoubleX(_Taylor):
    name = display_name = "half_asin_two_x"
    PARAM_SPEC = {"x": {"type": "str", "required": True, "default": "0.2", "short": "x"}}

    def argument(self, ctx):
        x = super().argument(ctx)
        b, d = ctx.backend, ctx.dps
        if b.sign(b.sub(ctx.number("0.5"), b.abs_val(x, d), d), d) <= 0:
            raise ValueError("half_asin_two_x requires |x| < 1/2")
        return x

    def coefficient(self, n):
        return 2*n+1, comb(2*n, n), 2*n+1

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.div(b.asin(b.mul(ctx.number(2), self.argument(ctx), d), d), ctx.number(2), d)


@register("series", "two_arcsin_square_x_halfed")
class ArcsinSquared(_Taylor):
    name = display_name = "two_arcsin_square_x_halfed"
    def argument(self, ctx):
        x = super().argument(ctx)
        b, d = ctx.backend, ctx.dps
        if b.sign(b.sub(ctx.number(2), b.abs_val(x, d), d), d) <= 0:
            raise ValueError("two_arcsin_square_x_halfed requires |x| < 2")
        return x

    def coefficient(self, n):
        m = n+1
        return 2*m, 1, m*m*comb(2*m, m)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        a = b.asin(b.div(self.argument(ctx), ctx.number(2), d), d)
        return b.mul(ctx.number(2), b.mul(a, a, d), d)


@register("series", "cos_sqrt_x")
class CosSqrtX(_Taylor):
    name = display_name = "cos_sqrt_x"

    def argument(self, ctx):
        x = super().argument(ctx)
        if ctx.backend.sign(x, ctx.dps) < 0:
            raise ValueError("Real cos_sqrt_x requires x >= 0")
        return x

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        return b.div(b.mul(ctx.number((-1)**n), b.pow(self.argument(ctx), ctx.number(n), d), d), b.factorial(2*n, d), d)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        return b.cos(b.pow(self.argument(ctx), ctx.number("0.5"), d), d)


@register("series", "one_div_sqrt2_sin_xdivsqrt2")
class ScaledSine(_Taylor):
    name = "one_div_sqrt2_sin_xdivsqrt2"
    display_name = "scaled_sin"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        power = b.pow(self.argument(ctx), ctx.number(2*n+1), d)
        denominator = b.mul(ctx.number(2**(n+1)), b.factorial(2*n+1, d), d)
        return b.div(b.mul(ctx.number((-1)**n), power, d), denominator, d)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        root = b.pow(ctx.number(2), ctx.number("0.5"), d)
        return b.div(b.sin(b.div(self.argument(ctx), root, d), d), root, d)


@register("series", "mean_sinh_sin")
class MeanSinhSin(ExpSeries):
    name = display_name = "mean_sinh_sin"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        return super().generate(4*n+1, ctx)

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        sinh = b.div(b.sub(b.exp(x, d), b.exp(b.neg(x, d), d), d), ctx.number(2), d)
        return b.div(b.add(sinh, b.sin(x, d), d), ctx.number(2), d)


@register("series", "two_degree_x")
class TwoPowerX(ExpSeries):
    name = display_name = "two_degree_x"

    def argument(self, ctx):
        return ctx.backend.mul(super().argument(ctx), ctx.backend.log(ctx.number(2), ctx.dps), ctx.dps)


@register("series", "ln_1plussqrt1plusxsquare_minus_ln_2")
class LogSqrtRemainder(_Taylor):
    name = "ln_1plussqrt1plusxsquare_minus_ln_2"
    display_name = "log_sqrt"
    unit_domain = True

    def coefficient(self, n):
        m = n+1
        return 2*m, (-1)**(m+1)*comb(2*m, m), 2*m*4**m

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        root = b.pow(b.add(ctx.number(1), b.mul(x, x, d), d), ctx.number("0.5"), d)
        return b.log(b.div(b.add(ctx.number(1), root, d), ctx.number(2), d), d)


@register("series", "sqrt_oneminussqrtoneminusx_div_x")
class NestedSqrt(_Taylor):
    name = "sqrt_oneminussqrtoneminusx_div_x"
    display_name = "nested_sqrt"
    unit_domain = True

    def coefficient(self, n):
        return n, comb(4*n, 2*n), 16**n*(2*n+1)

    def generate(self, n, ctx):
        return ctx.backend.div(super().generate(n, ctx), ctx.backend.pow(ctx.number(2), ctx.number("0.5"), ctx.dps), ctx.dps)

    def analytic_sum(self, ctx):
        # Rationalization includes the removable singularity x=0.
        b, d = ctx.backend, ctx.dps
        inner = b.pow(b.sub(ctx.number(1), self.argument(ctx), d), ctx.number("0.5"), d)
        return b.pow(b.add(ctx.number(1), inner, d), ctx.number("-0.5"), d)


@register("series", "erf")
class GaussianIntegral(_Taylor):
    name = "erf"
    display_name = "gaussian_integral"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        numerator = b.mul(ctx.number((-1)**n), b.pow(self.argument(ctx), ctx.number(2*n+1), d), d)
        return b.div(numerator, b.mul(b.factorial(n, d), ctx.number(2*n+1), d), d)

    def analytic_sum(self, ctx):
        b, d = ctx.backend, ctx.dps
        root_pi = b.pow(b.pi(d), ctx.number("0.5"), d)
        return b.div(b.mul(root_pi, b.erf(self.argument(ctx), d), d), ctx.number(2), d)


@register("series", "exp_squared_erf")
class ExpSquaredErf(_Taylor):
    name = display_name = "exp_squared_erf"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        coefficient = b.div(b.mul(ctx.number(2*4**n), b.factorial(n, d), d), b.factorial(2*n+1, d), d)
        numerator = b.mul(coefficient, b.pow(self.argument(ctx), ctx.number(2*n+1), d), d)
        return b.div(numerator, b.pow(b.pi(d), ctx.number("0.5"), d), d)

    def analytic_sum(self, ctx):
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        return b.mul(b.exp(b.mul(x, x, d), d), b.erf(x, d), d)


@register("series", "si_x")
class SineIntegral(_Taylor):
    name = display_name = "si_x"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        numerator = b.mul(ctx.number((-1)**n), b.pow(self.argument(ctx), ctx.number(2*n+1), d), d)
        return b.div(numerator, b.mul(b.factorial(2*n+1, d), ctx.number(2*n+1), d), d)

    def analytic_sum(self, ctx):
        return ctx.backend.si(self.argument(ctx), ctx.dps)


@register("series", "ci_x")
class CosineIntegral(_Taylor):
    name = display_name = "ci_x"

    def argument(self, ctx):
        x = super().argument(ctx)
        if ctx.backend.sign(x, ctx.dps) <= 0:
            raise ValueError("Real ci_x requires x > 0")
        return x

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d, x = ctx.backend, ctx.dps, self.argument(ctx)
        if n == 0:
            return b.euler_constant(d)
        if n == 1:
            return b.log(x, d)
        m = n-1
        numerator = b.mul(ctx.number((-1)**m), b.pow(x, ctx.number(2*m), d), d)
        return b.div(numerator, b.mul(b.factorial(2*m, d), ctx.number(2*m), d), d)

    def analytic_sum(self, ctx):
        return ctx.backend.ci(self.argument(ctx), ctx.dps)


@register("series", "ln2")
class ScaledLogTwo(_Taylor):
    name = display_name = "ln2"

    def coefficient(self, n):
        return 1, (-1)**n, n+1

    def analytic_sum(self, ctx):
        return ctx.backend.mul(self.argument(ctx), ctx.backend.log(ctx.number(2), ctx.dps), ctx.dps)


@register("series", "two_ln2")
class TwiceScaledLogTwo(ScaledLogTwo):
    name = display_name = "two_ln2"

    def coefficient(self, n):
        k = n+1
        return 1, 12*k*k-1, k*(4*k*k-1)**2

    def analytic_sum(self, ctx):
        return ctx.backend.mul(ctx.number(2), super().analytic_sum(ctx), ctx.dps)


@register("series", "euler_mascheroni")
class ScaledEulerConstant(_Taylor):
    name = display_name = "euler_mascheroni"

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError("negative term index")
        b, d = ctx.backend, ctx.dps
        inv = b.div(ctx.number(1), ctx.number(n+1), d)
        term = b.sub(inv, b.log(b.add(ctx.number(1), inv, d), d), d)
        return b.mul(self.argument(ctx), term, d)

    def analytic_sum(self, ctx):
        return ctx.backend.mul(self.argument(ctx), ctx.backend.euler_constant(ctx.dps), ctx.dps)
