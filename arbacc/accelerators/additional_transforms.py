"""Fixed-window transforms, evaluated in the selected precision backend.

Wynn: https://dlmf.nist.gov/3.9.E11.
Iterated Aitken and M: Weniger (1989), (5.1-15), (9.2-5), (9.4-1):
https://arxiv.org/pdf/math/0306302. M is Weniger's factorial analogue,
traditionally named levin_sidi_m in the C++ catalogue.
"""
from arbacc.core.registry import register
from arbacc.core.stream import series_term
from arbacc.accelerators.direct import _FixedOrder,_partials,Levin


@register('accelerators','iterated_aitken')
class IteratedAitken(_FixedOrder):
    name=display_name='iterated_aitken'

    def required_input(self,state):
        return state.iteration+2*self.order+1

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        s=_partials(source,state,ctx,self.required_input(state))
        row=s[n:n+2*self.order+1]
        for _ in range(self.order):
            following=[]
            for i in range(len(row)-2):
                delta=b.sub(row[i+1],row[i],d)
                denominator=b.add(b.sub(row[i+2],b.mul(ctx.number(2),row[i+1],d),d),row[i],d)
                value=row[i+2]
                if b.sign(denominator,d):
                    value=b.sub(row[i],b.div(b.mul(delta,delta,d),denominator,d),d)
                following.append(value)
            row=following
        result=state.with_estimate(row[0])
        result.extra['partials']=s
        return result


@register('accelerators','wynn_epsilon_fixed')
class WynnEpsilonFixed(_FixedOrder):
    """Return epsilon_(2k)^(n), fixed k and a moving starting index n.

    Unresolved cells propagate as None; use the latest lower even order in
    this window when the requested order is singular. Never mix an odd
    auxiliary cell (inverse units) into the returned estimate.
    """
    name=display_name='wynn_epsilon_fixed'

    def required_input(self,state):
        return state.iteration+2*self.order+1

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        s=_partials(source,state,ctx,self.required_input(state))
        row=s[n:n+2*self.order+1]
        previous=[ctx.number(0)]*(len(row)+1)
        estimate=row[-1]
        for column in range(1,2*self.order+1):
            following=[]
            for j in range(len(row)-1):
                value=None
                if row[j] is not None and row[j+1] is not None and previous[j+1] is not None:
                    difference=b.sub(row[j+1],row[j],d)
                    if b.sign(difference,d):
                        value=b.add(previous[j+1],b.div(ctx.number(1),difference,d),d)
                following.append(value)
            previous,row=row,following
            if column%2==0 and row[0] is not None:
                estimate=row[0]
        result=state.with_estimate(estimate)
        result.extra['partials']=s
        return result


@register('accelerators','levin_sidi_m')
class LevinSidiM(Levin):
    name=display_name='levin_sidi_m'
    PARAM_SPEC={**_FixedOrder.PARAM_SPEC,
        'gamma':{'type':'str','default':'100.5','short':'g'},
        'remainder':Levin.PARAM_SPEC['remainder']}

    def beta(self,ctx):
        # The parent calls beta() to validate the parameter before processing.
        value=ctx.number(self.params.get('gamma','100.5'))
        b,d=ctx.backend,ctx.dps
        if not b.is_finite(value,d) or b.sign(value,d)<=0 or b.sign(b.sub(value,ctx.number(self.order-1),d),d)<0:
            raise ValueError('gamma must be finite, positive and >= order-1')
        return value

    def weight(self,index,ctx):
        b,d,gamma=ctx.backend,ctx.dps,self.beta(ctx)
        start=b.add(gamma,ctx.number(index),d)
        value=ctx.number(1)
        # Common (-1)^(k-1) cancels in the ratio of weighted sums.
        for m in range(self.order-1):
            value=b.mul(value,b.sub(start,ctx.number(m),d),d)
        return value

    def inverse_remainder(self,source,index,ctx):
        if self.remainder!='u':return super().inverse_remainder(source,index,ctx)
        b,d=ctx.backend,ctx.dps
        omega=b.mul(b.neg(b.add(self.beta(ctx),ctx.number(index),d),d),series_term(source,index,ctx),d)
        return None if b.sign(omega,d)==0 else b.div(ctx.number(1),omega,d)
