"""Generalized Weniger-style inverse factorial remainder basis.

Model s_n = S + omega_n sum_j c_j Gamma(n+beta)/Gamma(n+beta+j*delta).
For delta=1 the model reduces to the usual inverse rising-factorial
family. Fractional delta is a new explicit generalization, NOT an
attribution of this fractional variant to Weniger (1989).
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import Levin
from arbacc.accelerators._generalized_models import build_levin_model


@register('accelerators','weniger_fractional_factorial')
class WenigerFractionalFactorial(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Weniger, Nonlinear Sequence Transformations (1989 dissertation; 2003 arXiv version)', 'url': 'https://arxiv.org/abs/math/0306302', 'locator': 'inverse-power and inverse-factorial Levin-type constructions', 'relation': 'local_extension', 'implementation_note': 'Fractional step in inverse-factorial basis is local generalization, not published Weniger formula.'}
    name=display_name='weniger_fractional_factorial'
    PARAM_SPEC={**Levin.PARAM_SPEC,
        'factorial_step':{'type':'str','default':'0.5','short':'delta'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'}}
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',2)
        if type(self.order) is not int or self.order<0:raise ValueError('order must be nonnegative int')
    def required_input(self,state):
        from arbacc.accelerators._generalized_models import base_levin
        return base_levin(self.params).required_input(state)
    def step(self,source,state,ctx):
        b,d=ctx.backend,ctx.dps
        delta=ctx.number(self.params.get('factorial_step','0.5'))
        if not b.is_finite(delta,d) or b.sign(delta,d)<=0:raise ValueError('factorial_step must be positive')
        def term(x,j,c):
            if j==0:return ctx.number(1)
            y=b.add(x,b.mul(ctx.number(j),delta,d),d)
            return b.div(b.gamma(x,d),b.gamma(y,d),d)
        value,partials=build_levin_model(source,state,ctx,self.params,term)
        out=state.with_estimate(value)
        out.extra.update(partials=partials,math_status='identity_order_zero' if not self.order else 'full_order',
                         achieved_order=self.order,model_family='generalized inverse-factorial')
        return out
