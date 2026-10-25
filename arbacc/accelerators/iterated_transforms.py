"""Overholt and iterated four-point W transformation.

Overholt: Homeier (2000), Eq. (64), https://arxiv.org/pdf/math/0005209.
W: equivalent elementary theta_2 formula, Weniger (1989), Sec. 10.3,
https://arxiv.org/pdf/math/0306302; same rational expression as C++ lubkin_w.
"""
from arbacc.core.registry import register
from arbacc.core.stream import series_term
from arbacc.accelerators.direct import _FixedOrder,_partials


@register('accelerators','overholt')
class Overholt(_FixedOrder):
    name=display_name='overholt'

    def required_input(self,state):
        return state.iteration+self.order+(2 if self.order else 1)

    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        sums=_partials(source,state,ctx,self.required_input(state))
        values=sums[n:n+k+1]
        for level in range(1,k+1):
            following=[]
            for j in range(len(values)-1):
                left=b.pow(series_term(source,n+level+j,ctx),ctx.number(level),d)
                right=b.pow(series_term(source,n+level+j+1,ctx),ctx.number(level),d)
                denominator=b.sub(left,right,d)
                value=values[j]
                if b.sign(denominator,d)!=0:
                    numerator=b.sub(b.mul(left,values[j+1],d),b.mul(right,values[j],d),d)
                    value=b.div(numerator,denominator,d)
                following.append(value)
            values=following
        result=state.with_estimate(values[0])
        result.extra['partials']=sums
        return result


@register('accelerators','lubkin_w')
class LubkinW(_FixedOrder):
    name=display_name='lubkin_w'

    def required_input(self,state):
        return state.iteration+3*self.order+1

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        sums=_partials(source,state,ctx,self.required_input(state))
        values=sums[n:n+3*self.order+1]
        for _ in range(self.order):
            following=[]
            for j in range(len(values)-3):
                d0=b.sub(values[j+1],values[j],d)
                d1=b.sub(values[j+2],values[j+1],d)
                d2=b.sub(values[j+3],values[j+2],d)
                left=b.mul(d0,b.sub(d2,d1,d),d)
                right=b.mul(d2,b.sub(d1,d0,d),d)
                denominator=b.sub(right,left,d)
                value=values[j+1]
                if b.sign(denominator,d)!=0:
                    value=b.sub(value,b.div(b.mul(d1,left,d),denominator,d),d)
                following.append(value)
            values=following
        result=state.with_estimate(values[0])
        result.extra['partials']=sums
        return result
