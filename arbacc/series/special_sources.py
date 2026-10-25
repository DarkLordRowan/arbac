"""Divergent ordinary series and a sequence of corrected quadrature estimates.

Integral substitution: t=u^2 gives log(t)/(1+t) dt = 4u log(u)/(1+u^2) du.
The transformed integrand is continuous at zero, so every panel is included.
Target integral: -eta(2)=-pi^2/12, https://dlmf.nist.gov/25.2.
Zeta regularization of 0+1+2+... is distinct from its divergent ordinary sum:
https://dlmf.nist.gov/25.6.
"""
from arbacc.core.registry import register
from arbacc.core.series import SeriesBase,SequenceBase


@register('series','natural_series')
class NaturalSeries(SeriesBase):
    name=display_name='natural_series'
    PARAM_SPEC={}
    reference_kind='divergent_no_ordinary_sum'

    def generate(self,n,ctx):
        if n<0: raise IndexError('negative term index')
        return ctx.number(n)

    def regularized_value(self,ctx):
        return ctx.backend.div(ctx.number(-1),ctx.number(12),ctx.dps)


@register('series','integral1')
class IntegralQuadrature(SequenceBase):
    name=display_name='integral1'
    reference_kind='quadrature_limit'
    PARAM_SPEC={
        'steps':{'type':'int','required':True,'default':8,'min':1,'short':'N'},
        'max_panels':{'type':'int','default':16384,'min':1,'short':'cap'},
    }

    def __init__(self,params,**kwargs):
        super().__init__(params,**kwargs)
        self.steps=self.params.get('steps',8)
        self.max_panels=self.params.get('max_panels',16384)
        for value in (self.steps,self.max_panels):
            if isinstance(value,bool) or not isinstance(value,int) or value<1:
                raise ValueError('steps and max_panels must be positive integers')
        if self.steps>self.max_panels: raise ValueError('steps exceeds max_panels')

    def sequence_step(self,n,values,state,ctx):
        panels=self.steps*(n+1)
        if panels>self.max_panels: raise ValueError('quadrature exceeds max_panels')
        b,d=ctx.backend,ctx.dps
        h=b.div(ctx.number(1),ctx.number(panels),d)
        total=ctx.number(0)
        # Trapezoid endpoints both have value zero after substitution.
        for j in range(1,panels):
            u=b.div(ctx.number(j),ctx.number(panels),d)
            numerator=b.mul(b.mul(ctx.number(4),u,d),b.log(u,d),d)
            denominator=b.add(ctx.number(1),b.mul(u,u,d),d)
            total=b.add(total,b.div(numerator,denominator,d),d)
        return b.mul(h,total,d)

    def analytic_sum(self,ctx):
        b,d=ctx.backend,ctx.dps
        return b.div(b.mul(ctx.number(-1),b.mul(b.pi(d),b.pi(d),d),d),ctx.number(12),d)
