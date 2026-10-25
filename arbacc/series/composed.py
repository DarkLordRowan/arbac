"""Power substitutions in verified series; see https://dlmf.nist.gov/4.6.

Names match the C++ registry. Delegation passes backend numbers directly so
neither precision nor Arb radii are lost through a float/string round trip.
"""
from arbacc.core.registry import register, get
from arbacc.core.series import SeriesBase


class _PowerSubstitution(SeriesBase):
    PARAM_SPEC={"x":{"type":"str","required":True,"default":"0.5","short":"x"}}
    base=""
    power=2
    negate=False

    def wrapped(self,ctx):
        x=ctx.number(self.params["x"])
        if not ctx.backend.is_finite(x,ctx.dps):
            raise ValueError("x must be finite")
        argument=ctx.backend.pow(x,ctx.number(self.power),ctx.dps)
        return get("series",self.base)({"x":argument})

    def generate(self,n,ctx):
        result=self.wrapped(ctx).generate(n,ctx)
        return ctx.backend.neg(result,ctx.dps) if self.negate else result

    def analytic_sum(self,ctx):
        result=self.wrapped(ctx).analytic_sum(ctx)
        return ctx.backend.neg(result,ctx.dps) if self.negate else result


@register("series","sin_x2")
class SinSquaredArgument(_PowerSubstitution):
    name=display_name="sin_x2"
    base="sin"


@register("series","cos_x2")
class CosSquaredArgument(_PowerSubstitution):
    name=display_name="cos_x2"
    base="cos"


@register("series","sinh_x2")
class SinhSquaredArgument(_PowerSubstitution):
    name=display_name="sinh_x2"
    base="sinh"


@register("series","arcsin_x2")
class ArcsinSquaredArgument(_PowerSubstitution):
    name=display_name="arcsin_x2"
    base="arcsin_x"


@register("series","arctanh_x2")
class ArctanhSquaredArgument(_PowerSubstitution):
    name=display_name="arctanh_x2"
    base="arctanh_x"


@register("series","arctan_x2")
class ArctanSquaredArgument(_PowerSubstitution):
    name=display_name="arctan_x2"
    base="arctan_x"


@register("series","arctan_x3")
class ArctanCubedArgument(_PowerSubstitution):
    name=display_name="arctan_x3"
    base="arctan_x"
    power=3


@register("series","ln1px4")
class LogQuarticArgument(_PowerSubstitution):
    name=display_name="ln1px4"
    base="log1p"
    power=4


@register("series","ln_1_plus_x3")
class LogCubicArgument(_PowerSubstitution):
    name=display_name="ln_1_plus_x3"
    base="log1p"
    power=3


@register("series","ln1_m_x2")
class LogOneMinusSquaredArgument(_PowerSubstitution):
    name=display_name="ln1_m_x2"
    base="ln1mx"
    negate=True
