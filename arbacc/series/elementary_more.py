"""Further elementary expansions, with source indexing preserved.

https://dlmf.nist.gov/4.6 (logarithm, binomial theorem),
https://dlmf.nist.gov/4.22 (Euler sine product), /4.19 (trigonometric series).
"""
from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor, SqrtOnePlusX
from arbacc.series.rational_catalogue import _Arithmetic


@register('series','cos3xmin1_div_xsquare')
class ShiftedCosine(_Taylor):
    name=display_name='cos3xmin1_div_xsquare'

    def argument(self,ctx):
        value=super().argument(ctx)
        if ctx.backend.sign(value,ctx.dps)==0: raise ValueError('x must be nonzero')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.div(a.mul((-1)**n,a.power(a.sub(a.mul(3,x),1),2*n)),
                     a.mul(a.power(x,2),ctx.backend.factorial(2*n,ctx.dps)))

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.div(ctx.backend.cos(a.sub(a.mul(3,x),1),ctx.dps),a.power(x,2))


@register('series','exp_m_cos_x_sinsin_x')
class ExponentialTrigonometric(_Taylor):
    name=display_name='exp_m_cos_x_sinsin_x'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx)
        value=ctx.backend.sin(a.mul(n+1,self.argument(ctx)),ctx.dps)
        return a.div(a.mul((-1)**n,value),ctx.backend.factorial(n+1,ctx.dps))

    def analytic_sum(self,ctx):
        b,d,x=ctx.backend,ctx.dps,self.argument(ctx); a=_Arithmetic(ctx)
        return a.mul(b.exp(b.neg(b.cos(x,d),d),d),b.sin(b.sin(x,d),d))


@register('series','ln_1plusx_div_1plusx2')
class LogarithmRational(_Taylor):
    name=display_name='ln_1plusx_div_1plusx2'
    unit_domain=True

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.div(a.mul((-1)**n,a.power(x,n+1)),a.mul(n+1,a.add(1,a.power(x,2))))

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.div(a.log(a.add(1,x)),a.add(1,a.power(x,2)))


@register('series','ln_cosx')
class LogCosine(_Taylor):
    name=display_name='ln_cosx'

    def argument(self,ctx):
        value=super().argument(ctx); a=_Arithmetic(ctx)
        if ctx.backend.sign(a.sub(a.div(a.pi,2),ctx.backend.abs_val(value,ctx.dps)),ctx.dps)<=0:
            raise ValueError('log-cos series requires |x| < pi/2')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx); sine=ctx.backend.sin(self.argument(ctx),ctx.dps)
        return a.div(a.power(sine,2*n+2),-2*(n+1))

    def analytic_sum(self,ctx):
        return ctx.backend.log(ctx.backend.cos(self.argument(ctx),ctx.dps),ctx.dps)


@register('series','ln_x_plus_one_x_minus_one_halfed')
class LegacyLogCosine(LogCosine):
    """Legacy id really computes log(cos(x)), as documented in its C++ header."""
    name=display_name='ln_x_plus_one_x_minus_one_halfed'


@register('series','ln_sinx_minus_ln_x')
class LogSincProduct(_Taylor):
    name=display_name='ln_sinx_minus_ln_x'

    def argument(self,ctx):
        value=super().argument(ctx); a=_Arithmetic(ctx)
        if ctx.backend.sign(a.sub(a.pi,ctx.backend.abs_val(value,ctx.dps)),ctx.dps)<=0:
            raise ValueError('Real log-sinc product requires |x| < pi')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx)
        return a.log(a.sub(1,a.power(a.div(self.argument(ctx),a.mul(a.pi,n+1)),2)))

    def analytic_sum(self,ctx):
        x=self.argument(ctx); a=_Arithmetic(ctx)
        if ctx.backend.sign(x,ctx.dps)==0: return ctx.number(0)
        return a.log(a.div(ctx.backend.sin(x,ctx.dps),x))


class _AroundOne(_Taylor):
    PARAM_SPEC={'x':{'type':'str','required':True,'default':'1.1','short':'x'}}

    def argument(self,ctx):
        value=super().argument(ctx); a=_Arithmetic(ctx)
        if ctx.backend.sign(a.sub(1,ctx.backend.abs_val(a.sub(value,1),ctx.dps)),ctx.dps)<=0:
            raise ValueError('Expansion around one requires 0 < x < 2')
        return value


@register('series','x_min_sqrt_x')
class XMinusSqrt(_AroundOne):
    name=display_name='x_min_sqrt_x'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx); shifted=a.sub(self.argument(ctx),1)
        if n==0: return shifted
        _,coefficient,denominator=SqrtOnePlusX.coefficient(self,n)
        return a.mul(a.div(-coefficient,denominator),a.power(shifted,n))

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.sub(x,a.power(x,'0.5'))


@register('series','xsquareplus3_div_xsquareplus2multix_minus_1')
class ShiftedRational(_AroundOne):
    name='xsquareplus3_div_xsquareplus2multix_minus_1'
    display_name='shifted_rational'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.mul(a.div(a.mul((-1)**n,a.sub(3,a.div(7,3**(n+1)))),2),a.power(a.sub(x,1),n))

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.sub(a.div(a.add(a.power(x,2),3),a.add(a.power(x,2),a.mul(2,x))),1)


@register('series','one_div_two_minus_x_multi_three_plus_x')
class PartialFractionGeometric(_Taylor):
    name='one_div_two_minus_x_multi_three_plus_x'
    display_name='partial_fraction_geometric'

    def argument(self,ctx):
        value=super().argument(ctx); a=_Arithmetic(ctx)
        if ctx.backend.sign(a.sub(2,ctx.backend.abs_val(value,ctx.dps)),ctx.dps)<=0:
            raise ValueError('This geometric expansion requires |x| < 2')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        a=_Arithmetic(ctx)
        coefficient=a.div(a.add(a.div((-1)**n,3**(n+1)),a.div(1,2**(n+1))),5)
        return a.mul(a.power(self.argument(ctx),n),coefficient)

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx); x=self.argument(ctx)
        return a.div(1,a.mul(a.sub(2,x),a.add(3,x)))
