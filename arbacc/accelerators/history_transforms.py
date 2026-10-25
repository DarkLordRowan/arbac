"""Scalar observed-pair Anderson, Ford-Sidi elimination, legacy Aitken search.

AA uses (x_i,g_i)=(s_i,s_(i+1)); it does not evaluate a fixed-point function
or feed transformed values back into it. Walker/Ni (2011), Secs. 1 and 4:
https://doi.org/10.1137/10078356X. Regularization is a ridge penalty on the
unconstrained difference coefficients, not on affine mixing weights.
Ford/Sidi (1987): https://doi.org/10.1137/0724080; basis
omega_i*(beta+i)^(-r), r=0..k-1, evaluated by recursive elimination.
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import Levin,_partials


@register('accelerators','anderson')
class Anderson(AcceleratorBase):
    name=display_name='anderson'
    PARAM_SPEC={'memory':{'type':'int','default':50,'min':1,'short':'m'},
        'beta':{'type':'str','default':'1','short':'b'},
        'regularization':{'type':'str','default':'1e-12','short':'reg'}}

    def __init__(self,params=None):
        super().__init__(params)
        self.memory=self.params.get('memory',50)
        if isinstance(self.memory,bool) or not isinstance(self.memory,int) or self.memory<1:
            raise ValueError('memory must be a positive integer')

    def required_input(self,state):return state.iteration+1

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        beta=ctx.number(self.params.get('beta','1'))
        reg=ctx.number(self.params.get('regularization','1e-12'))
        if not b.is_finite(beta,d) or b.sign(beta,d)<=0 or b.sign(b.sub(beta,ctx.number(1),d),d)>0:
            raise ValueError('beta must be finite and in (0,1]')
        if not b.is_finite(reg,d) or b.sign(reg,d)<0:
            raise ValueError('regularization must be finite and nonnegative')
        s=_partials(source,state,ctx,n+1)
        estimate=s[n]
        if n:
            residual=b.sub(s[n],s[n-1],d)
            estimate=b.add(s[n-1],b.mul(beta,residual,d),d)
            denominator,cross=reg,ctx.number(0)
            for j in range(n-1-min(self.memory,n-1),n-1):
                dx=b.sub(s[j+1],s[j],d)
                df=b.sub(b.sub(s[j+2],s[j+1],d),dx,d)
                denominator=b.add(denominator,b.mul(df,df,d),d)
                cross=b.add(cross,b.mul(b.add(dx,b.mul(beta,df,d),d),df,d),d)
            if b.sign(denominator,d)>0:
                estimate=b.sub(estimate,b.div(b.mul(residual,cross,d),denominator,d),d)
        result=state.with_estimate(estimate);result.extra['partials']=s
        return result


@register('accelerators','ford_sidi')
class FordSidi(Levin):
    """Ford-Sidi elimination for a Levin error basis (same model, new algorithm)."""
    name=display_name='ford_sidi'

    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        beta=self.beta(ctx)
        s=_partials(source,state,ctx,n+k+1)
        estimate=s[n+k]
        if not k:estimate=s[n]
        else:
            num,den=[],[]
            for i in range(n,n+k+1):
                inverse=self.inverse_remainder(source,i,ctx)
                if inverse is None:break
                den.append(inverse);num.append(b.mul(s[i],inverse,d))
            else:
                # g_(r+1)/g_1 = (beta+i)^(-r), r=1..k-1.
                auxiliary={r:[b.pow(b.add(beta,ctx.number(i),d),ctx.number(-r),d) for i in range(n,n+k+1)]
                           for r in range(1,k)}
                valid=True
                for level in range(1,k+1):
                    for j in range(k-level+1):
                        divisor=ctx.number(1) if level==k else b.sub(auxiliary[level][j+1],auxiliary[level][j],d)
                        if b.sign(divisor,d)==0:
                            valid=False;break
                        for row in [num,den]+[auxiliary[r] for r in range(level+1,k)]:
                            row[j]=b.div(b.sub(row[j+1],row[j],d),divisor,d)
                    if not valid:break
                if valid and b.sign(den[0],d):estimate=b.div(num[0],den[0],d)
        result=state.with_estimate(estimate);result.extra['partials']=s
        return result


@register('accelerators','aitken_backtracking')
class AitkenBacktracking(AcceleratorBase):
    """Legacy Ford-Sidi-2 helper: search backward for a usable Aitken triple."""
    name=display_name='aitken_backtracking'
    PARAM_SPEC={}

    def required_input(self,state):return state.iteration+3

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        s=_partials(source,state,ctx,n+3)
        estimate=s[n+2]
        for i in range(n,-1,-1):
            delta=b.sub(s[i+1],s[i],d)
            denominator=b.add(b.sub(s[i+2],b.mul(ctx.number(2),s[i+1],d),d),s[i],d)
            if b.sign(denominator,d):
                estimate=b.sub(s[i],b.div(b.mul(delta,delta,d),denominator,d),d);break
        result=state.with_estimate(estimate);result.extra['partials']=s
        return result
