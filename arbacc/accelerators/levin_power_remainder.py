"""Generalized Levin-type power-basis collocation (not a named historical t/u/v transform).

Model: s_n = S + omega_n sum_(j=0)^(k-1) c_j*(n+beta)^(-j*lambda).
At lambda=1 this is Levin's usual inverse power remainder model; the
solver is independent direct collocation, not Levin's binomial recurrence.
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import Levin
from arbacc.accelerators._generalized_models import build_levin_model


@register('accelerators','levin_power_remainder')
class LevinPowerRemainder(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Levin, Development of non-linear transformations for improving convergence of sequences, Int. J. Comput. Math. 3 (1973)', 'url': 'https://doi.org/10.1080/00207167308803075', 'locator': 'Levin family; remainder estimates', 'relation': 'local_extension', 'implementation_note': 'Independent power-model collocation with variable exponent; do not attribute generalized formula to Levin.'}
    name=display_name='levin_power_remainder'
    PARAM_SPEC={**Levin.PARAM_SPEC,
        'power_step':{'type':'str','default':'0.5','short':'lam'},
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
        lam=ctx.number(self.params.get('power_step','0.5'))
        if not b.is_finite(lam,d) or b.sign(lam,d)<=0:raise ValueError('power_step must be positive')
        def term(x,j,c):
            exponent=b.neg(b.mul(ctx.number(j),lam,d),d)
            return b.pow(x,exponent,d)
        value,partials=build_levin_model(source,state,ctx,self.params,term)
        out=state.with_estimate(value)
        out.extra.update(partials=partials,math_status='identity_order_zero' if not self.order else 'full_order',
                         achieved_order=self.order,model_family='generalized Levin inverse-power')
        return out
