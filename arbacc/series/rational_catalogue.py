"""Scaled rational test series, retaining the historical C++ identifiers.

Each entry supplies exact integer coefficients and a separately evaluated sum.
Identities follow by partial fractions and harmonic/digamma sums:
https://dlmf.nist.gov/5.9, https://dlmf.nist.gov/5.15,
https://dlmf.nist.gov/25.6. Alternating odd powers give the Dirichlet beta values.
The numerical C++ catalogue probe alone was not used to certify these entries.
"""
from arbacc.core.registry import register
from arbacc.series.taylor import _Taylor


class _Arithmetic:
    """Small expression helper; every operation respects backend and precision."""
    def __init__(self, ctx):
        self.ctx, self.backend, self.dps = ctx, ctx.backend, ctx.dps

    @property
    def pi(self):
        return self.backend.pi(self.dps)

    def add(self, a, b):
        return self.backend.add(self.ctx.number(a), self.ctx.number(b), self.dps)

    def sub(self, a, b):
        return self.backend.sub(self.ctx.number(a), self.ctx.number(b), self.dps)

    def mul(self, a, b):
        return self.backend.mul(self.ctx.number(a), self.ctx.number(b), self.dps)

    def div(self, a, b):
        return self.backend.div(self.ctx.number(a), self.ctx.number(b), self.dps)

    def power(self, a, b):
        return self.backend.pow(self.ctx.number(a), self.ctx.number(b), self.dps)

    def log(self, a):
        return self.backend.log(self.ctx.number(a), self.dps)


# Functions take k=n+1. sign=-1 means (-1)^n; a negative numerator flips it.
# (numerator, denominator, sign, limit of the unscaled series).
RATIONAL_SPECS = {
    'eighth_pi_m_one_third': (lambda k: 1, lambda k:(2*k-1)*(2*k+1)*(2*k+3), -1,
                             lambda a:a.sub(a.div(a.pi,8),a.div(1,3))),
    'five_pi_twelve': (lambda k:5, lambda k:3*(2*k-1), -1,
                      lambda a:a.div(a.mul(5,a.pi),12)),
    'four_ln2_m_3': (lambda k:-1, lambda k:k*k*(k+1)**2, -1,
                    lambda a:a.sub(a.mul(4,a.log(2)),3)),
    'ln13_min_ln7_div_7': (lambda k:6**k, lambda k:k*7**(k+1), -1,
                         lambda a:a.div(a.log(a.div(13,7)),7)),
    'minus_one_quarter': (lambda k:-1, lambda k:k*(k+2), -1, lambda a:a.div(-1,4)),
    'minus_three_plus_ln3_three_devided_two_plus_two_ln2':
        (lambda k:1, lambda k:k*(36*k*k-1), 1,
         lambda a:a.sub(a.add(a.log(4),a.mul(a.div(3,2),a.log(3))),3)),
    'one': (lambda k:1, lambda k:k*(k+1), 1, lambda a:1),
    'one_third_pi_squared_m_nine': (lambda k:1, lambda k:k*k*(k+1)**2, 1,
                                  lambda a:a.div(a.sub(a.power(a.pi,2),9),3)),
    'one_twelfth': (lambda k:1, lambda k:(2*k-1)*(2*k+1)*(2*k+3), 1,
                   lambda a:a.div(1,12)),
    'pi_3': (lambda k:1, lambda k:k*(2*k-1)*(4*k-3), 1, lambda a:a.div(a.pi,3)),
    'pi_4': (lambda k:1, lambda k:2*k-1, -1, lambda a:a.div(a.pi,4)),
    'pi_cubed_32': (lambda k:1, lambda k:(2*k-1)**3, -1,
                    lambda a:a.div(a.power(a.pi,3),32)),
    'pi_four_minus_ln2_halfed': (lambda k:1, lambda k:(2*k-1)*(2*k), -1,
                               lambda a:a.sub(a.div(a.pi,4),a.div(a.log(2),2))),
    'pi_six_min_half': (lambda k:1, lambda k:(6*k-1)*(6*k+1), -1,
                        lambda a:a.sub(a.div(a.pi,6),a.div(1,2))),
    'pi_squared_6_minus_one': (lambda k:1, lambda k:k*k*(k+1), 1,
                              lambda a:a.sub(a.div(a.power(a.pi,2),6),1)),
    'pi_squared_twelve': (lambda k:1, lambda k:k*k, -1,
                          lambda a:a.div(a.power(a.pi,2),12)),
    'three_minus_pi': (lambda k:-1, lambda k:k*(k+1)*(2*k+1), -1,
                       lambda a:a.sub(3,a.pi)),
    'x_two': (lambda k:1, lambda k:(2*k-1)*(2*k+1), 1, lambda a:a.div(1,2)),
    'x_two_throught_squares': (lambda k:2*k*k-1, lambda k:4*k**4+1, 1,
                              lambda a:a.div(1,2)),
}


class _ScaledRational(_Taylor):
    PARAM_SPEC = {'x':{'type':'str','required':True,'default':'1','short':'x'}}

    def generate(self, n, ctx):
        if n < 0:
            raise IndexError('negative term index')
        numerator, denominator, sign, _ = self.SPEC
        b, d = ctx.backend, ctx.dps
        value = b.div(ctx.number(numerator(n+1)*sign**n),ctx.number(denominator(n+1)),d)
        return b.mul(self.argument(ctx),value,d)

    def analytic_sum(self, ctx):
        value = self.SPEC[3](_Arithmetic(ctx))
        return ctx.backend.mul(self.argument(ctx),ctx.number(value),ctx.dps)


# A data catalogue makes coefficients auditable without duplicating arithmetic.
# Publish named classes as well, so multiprocessing can resolve them by module/name.
for _name, _spec in RATIONAL_SPECS.items():
    _class_name = ''.join(part.capitalize() for part in _name.split('_'))+'Series'
    _class = type(_class_name,(_ScaledRational,),{
        '__module__':__name__, 'name':_name, 'display_name':_name, 'SPEC':_spec,
        '__doc__':'Scaled rational series; see RATIONAL_SPECS and NIST DLMF 5.9/5.15.',
    })
    globals()[_class_name] = register('series',_name)(_class)


@register('series','pi')
class PiSeries(_Taylor):
    name = display_name = 'pi'

    def generate(self,n,ctx):
        if n<0:
            raise IndexError('negative term index')
        a=_Arithmetic(ctx)
        return a.mul(self.argument(ctx),a.mul(a.power(12,'0.5'),
                     a.div((-1)**n,3**n*(2*n+1))))

    def analytic_sum(self,ctx):
        return ctx.backend.mul(self.argument(ctx),ctx.backend.pi(ctx.dps),ctx.dps)
