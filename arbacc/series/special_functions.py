"""Special-function series, using backend-native independent reference values.

Sources: https://dlmf.nist.gov/10.2#E2 (Bessel J), /8.7 (lower gamma),
/19.5 (elliptic modulus k; backend parameter m=k^2), /4.13 (Lambert W),
/27.4 (totient Dirichlet series), /18.12 (Legendre generating functions).
Domains below are explicit real convergence domains, not analytic continuation.
"""
from math import comb
from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor
from arbacc.series.rational_catalogue import _Arithmetic


class _AlphaSeries(_Taylor):
    PARAM_SPEC={**_Taylor.PARAM_SPEC,
                'alpha':{'type':'str','required':True,'default':'0.5','short':'a'}}

    def alpha(self,ctx,allow_zero=False):
        value=ctx.number(self.params['alpha'])
        sign=ctx.backend.sign(value,ctx.dps)
        if not ctx.backend.is_finite(value,ctx.dps) or sign<0 or (sign==0 and not allow_zero):
            raise ValueError('alpha must be positive' if not allow_zero else 'alpha must be nonnegative')
        return value

    def argument(self,ctx):
        value=super().argument(ctx)
        if ctx.backend.sign(value,ctx.dps)<0:
            raise ValueError('This real series requires x >= 0')
        return value


@register('series','bessel_first_kind')
class BesselFirstKind(_AlphaSeries):
    name=display_name='bessel_first_kind'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        b,d=ctx.backend,ctx.dps
        alpha=self.alpha(ctx,allow_zero=True)
        exponent=b.add(ctx.number(2*n),alpha,d)
        numerator=b.pow(b.div(self.argument(ctx),ctx.number(2),d),exponent,d)
        denominator=b.mul(b.factorial(n,d),b.gamma(b.add(ctx.number(n+1),alpha,d),d),d)
        return b.div(b.mul(ctx.number((-1)**n),numerator,d),denominator,d)

    def analytic_sum(self,ctx):
        return ctx.backend.bessel_j(self.alpha(ctx,allow_zero=True),self.argument(ctx),ctx.dps)


@register('series','incomplete_Gamma_func')
class LowerGamma(_AlphaSeries):
    name=display_name='incomplete_Gamma_func'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        b,d=ctx.backend,ctx.dps
        alpha=self.alpha(ctx)
        exponent=b.add(ctx.number(n),alpha,d)
        numerator=b.mul(ctx.number((-1)**n),b.pow(self.argument(ctx),exponent,d),d)
        return b.div(numerator,b.mul(b.factorial(n,d),exponent,d),d)

    def analytic_sum(self,ctx):
        return ctx.backend.gamma_lower(self.alpha(ctx),self.argument(ctx),ctx.dps)


@register('series','k_x')
class EllipticK(_Taylor):
    name=display_name='k_x'
    unit_domain=True

    def coefficient(self,n):
        return 2*n,comb(2*n,n)**2,16**n

    def generate(self,n,ctx):
        value=super().generate(n,ctx)
        return ctx.backend.mul(value,ctx.backend.div(ctx.backend.pi(ctx.dps),ctx.number(2),ctx.dps),ctx.dps)

    def analytic_sum(self,ctx):
        x=self.argument(ctx)
        return ctx.backend.ellipk(ctx.backend.mul(x,x,ctx.dps),ctx.dps)


@register('series','e_x')
class EllipticE(EllipticK):
    name=display_name='e_x'

    def coefficient(self,n):
        return 2*n,comb(2*n,n)**2,16**n*(1-2*n)

    def analytic_sum(self,ctx):
        x=self.argument(ctx)
        return ctx.backend.ellipe(ctx.backend.mul(x,x,ctx.dps),ctx.dps)


@register('series','lambert_W_func')
class LambertW(_Taylor):
    name=display_name='lambert_W_func'
    PARAM_SPEC={'x':{'type':'str','required':True,'default':'0.1','short':'x'}}

    def argument(self,ctx):
        value=super().argument(ctx)
        b,d=ctx.backend,ctx.dps
        radius=b.exp(ctx.number(-1),d)
        if b.sign(b.sub(radius,b.abs_val(value,d),d),d)<=0:
            raise ValueError('Lambert Taylor series requires |x| < 1/e')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        k=n+1
        b,d=ctx.backend,ctx.dps
        numerator=b.mul(ctx.number((-1)**n*k**n),b.pow(self.argument(ctx),ctx.number(k),d),d)
        return b.div(numerator,b.factorial(k,d),d)

    def analytic_sum(self,ctx):
        return ctx.backend.lambertw(self.argument(ctx),ctx.dps)


def _totient(n):
    """Exact Euler phi by factorization; no floating-point divisibility tests."""
    result,left=n,n
    prime=2
    while prime*prime<=left:
        if left%prime==0:
            result-=result//prime
            while left%prime==0: left//=prime
        prime+=1
    if left>1: result-=result//left
    return result


@register('series','riemann_zeta_func_xmin1_div_Riemann_zeta_func_x')
class TotientDirichlet(_Taylor):
    name='riemann_zeta_func_xmin1_div_Riemann_zeta_func_x'
    display_name='totient_dirichlet'
    PARAM_SPEC={'x':{'type':'str','required':True,'default':'3','short':'s'}}

    def argument(self,ctx):
        value=super().argument(ctx)
        if ctx.backend.sign(ctx.backend.sub(value,ctx.number(2),ctx.dps),ctx.dps)<=0:
            raise ValueError('Totient Dirichlet series requires s > 2')
        return value

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        b,d=ctx.backend,ctx.dps
        denominator=b.pow(ctx.number(n+1),self.argument(ctx),d)
        return b.div(ctx.number(_totient(n+1)),denominator,d)

    def analytic_sum(self,ctx):
        b,d,s=ctx.backend,ctx.dps,self.argument(ctx)
        return b.div(b.zeta(b.sub(s,ctx.number(1),d),d),b.zeta(s,d),d)


@register('series','legendre1')
class LegendreExpansion(_Taylor):
    name=display_name='legendre1'
    unit_domain=True

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        b,d=ctx.backend,ctx.dps
        value=b.legendre(n,self.argument(ctx),d)
        return b.div(b.neg(value,d),ctx.number((2*n-1)*(2*n+3)),d)

    def analytic_sum(self,ctx):
        a=_Arithmetic(ctx)
        return a.power(a.div(a.sub(1,self.argument(ctx)),8),'0.5')
