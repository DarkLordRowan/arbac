"""Generalized rho of Osada and a two-stage exponent-estimated variant.

Static recurrence: Osada, SIAM J. Numer. Anal. 27 (1990), Eq. (3.1).
Auxiliary exponent estimator T_n: Osada (1990), Eq. (5.1), then apply
rho with alpha=-2 to T_n to estimate exponent theta of n**theta.
This *two-stage estimator* is not advertised as an exact port of the
paper's automatic algorithm Eq. (6.1); that is a distinct adaptive table.

Singular cells never silently count as full-order results.  Optional
lower-order recovery is explicitly reported with achieved_order.
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials


def rho_even(values,alpha,order,ctx,recover=False,pivot_tol="auto"):
    """Wynn--Osada recurrence rho[-1,n]=0, rho[0,n]=S_n.

    Returns (estimate, achieved_even_order, status). The calculated
    lower order is not represented as the requested order when recovering.
    """
    b,d=ctx.backend,ctx.dps
    if type(order) is not int or order<0:raise ValueError('order must be nonnegative int')
    if len(values)<2*order+1:raise ValueError('insufficient data')
    tol = ctx.number(f'1e-{max(12,d//2)}') if pivot_tol=='auto' else ctx.number(pivot_tol)
    if not b.is_finite(tol,d) or b.sign(tol,d)<0:raise ValueError('invalid rho pivot_tol')
    prev=[ctx.number(0)]*(2*order+2)
    row=values[:2*order+1]
    last_even=None;last_k=0
    for col in range(1,2*order+1):
        next_row=[]
        fac=b.sub(ctx.number(col-1),alpha,d)
        for j in range(len(row)-1):
            delta=b.sub(row[j+1],row[j],d)
            scale=b.abs_val(row[j],d)
            oth=b.abs_val(row[j+1],d)
            if b.sign(b.sub(oth,scale,d),d)>0:scale=oth
            near = bool(b.sign(tol,d)) and b.sign(b.sub(b.abs_val(delta,d),b.mul(tol,scale,d),d),d)<=0
            if b.sign(delta,d)==0 or not b.is_finite(delta,d) or near:
                if recover and last_even is not None:
                    return last_even,last_k,'lower_order_singular'
                raise ArithmeticError(f'Osada rho singular column={col}, row={j}')
            value=b.add(prev[j+1],b.div(fac,delta,d),d)
            if not b.is_finite(value,d):
                if recover and last_even is not None:
                    return last_even,last_k,'lower_order_nonfinite'
                raise ArithmeticError(f'Osada rho nonfinite column={col}, row={j}')
            next_row.append(value)
        prev,row=row,next_row
        if col%2==0:
            last_even=row[0];last_k=col//2
    return (row[0] if order else values[0]),order,'full_order' if order else 'identity_order_zero'


def exponent_T(samples,n,ctx):
    """Osada Eq. 5.1: T_n = 1 / Delta [(S_(n+1)-S_n)/Delta^2 S_(n-1)] +1.

    Accesses S_(n-1),S_n,S_(n+1),S_(n+2). n>=1.
    """
    b,d=ctx.backend,ctx.dps
    if n<1 or len(samples)<=n+2:raise ValueError('Osada T needs S[n-1:n+3]')
    def Q(j):
        delta=b.sub(samples[j+1],samples[j],d)
        second=b.add(b.sub(samples[j+1],b.mul(ctx.number(2),samples[j],d),d),samples[j-1],d)
        if b.sign(second,d)==0:raise ArithmeticError('Osada T denominator zero')
        return b.div(delta,second,d)
    diff=b.sub(Q(n+1),Q(n),d)
    if b.sign(diff,d)==0:raise ArithmeticError('Osada T extrapolated exponent singular')
    return b.add(ctx.number(1),b.div(ctx.number(1),diff,d),d)


@register('accelerators','osada_rho_safe')
class OsadaRhoSafe(AcceleratorBase):
    """Original Osada rho Eq (3.1), optionally recover last valid even row."""

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189', 'url': 'https://doi.org/10.1137/0727012', 'locator': 'Eq. (3.1)', 'relation': 'local_variant', 'implementation_note': 'Published generalized rho recurrence plus local last-valid-row recovery.'}
    name=display_name='osada_rho_safe'
    PARAM_SPEC={
        'order':{'type':'int','default':3,'min':0,'short':'k'},
        'alpha':{'type':'str','default':'-1','short':'theta'},
        'on_singular':{'type':'enum','default':'lower_order','values':['raise','lower_order'],'short':'mode'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',3)
        if type(self.order) is not int or self.order<0:raise ValueError('order must be nonnegative int')
    def required_input(self,state):return state.iteration+2*self.order+1
    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        alpha=ctx.number(self.params.get('alpha','-1'))
        if not b.is_finite(alpha,d):raise ValueError('alpha must be finite')
        part=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        value,got,status=rho_even(part[n:n+2*k+1],alpha,k,ctx,
                                  recover=self.params.get('on_singular','lower_order')=='lower_order',
                                  pivot_tol=self.params.get('pivot_tol','auto'))
        out=state.with_estimate(value)
        out.extra.update(partials=part,math_status=status,achieved_order=got,requested_order=k,
                         family='Osada rho')
        return out


@register('accelerators','osada_rho_theta_estimated')
class OsadaRhoThetaEstimated(AcceleratorBase):
    """Two-stage Osada Eq.5.1 exponent estimate + rho(-2) + rho(theta).

    This is NOT a literal implementation of the full automatic Eq.6.1
    triangle. The theta estimate and approximation share raw observations;
    an independent holdout budget is needed to claim adaptive performance.
    """

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189', 'url': 'https://doi.org/10.1137/0727012', 'locator': 'Eq. (5.1) + Eq. (3.1)', 'relation': 'local_variant', 'implementation_note': 'Two-stage exponent estimate is NOT literal published automatic algorithm (6.1).'}
    name=display_name='osada_rho_theta_estimated'
    PARAM_SPEC={
        'order':{'type':'int','default':2,'min':0,'short':'k'},
        'theta_order':{'type':'int','default':1,'min':0,'short':'kt'},
        'theta_min':{'type':'str','default':'-20','short':'min'},
        'theta_max':{'type':'str','default':'0','short':'max'},
        'on_singular':{'type':'enum','default':'raise','values':['raise','lower_order'],'short':'mode'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'},
        'on_invalid':{'type':'enum','default':'report','values':['raise','report'],'short':'invalid'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',2)
        self.theta_order=self.params.get('theta_order',1)
        if type(self.order) is not int or self.order<0 or type(self.theta_order) is not int or self.theta_order<0:
            raise ValueError('orders must be nonnegative ints')
    def required_input(self,state):
        return state.iteration+max(2*self.order+1,2*self.theta_order+4)
    def step(self,source,state,ctx):
        b,d,n,k,tk=ctx.backend,ctx.dps,state.iteration,self.order,self.theta_order
        part=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        if k==0:
            out=state.with_estimate(part[n]);out.extra.update(partials=part,math_status='identity_order_zero');return out
        try:
            Ts=[exponent_T(part,n+1+j,ctx) for j in range(2*tk+1)]
            theta,tgot,tstatus=rho_even(Ts,ctx.number(-2),tk,ctx,recover=False,
                                        pivot_tol=self.params.get('pivot_tol','auto'))
            low=ctx.number(self.params.get('theta_min','-20'))
            high=ctx.number(self.params.get('theta_max','0'))
            if not b.is_finite(theta,d) or b.sign(b.sub(theta,low,d),d)<=0 or b.sign(b.sub(high,theta,d),d)<=0:
                raise ArithmeticError('Osada estimated exponent outside declared model range')
            est,got,status=rho_even(part[n:n+2*k+1],theta,k,ctx,
                                    recover=self.params.get('on_singular','raise')=='lower_order',
                                    pivot_tol=self.params.get('pivot_tol','auto'))
        except (ArithmeticError,ZeroDivisionError,ValueError) as exc:
            if self.params.get('on_invalid','report')=='raise':raise
            out=state.with_estimate(part[n])
            out.extra.update(partials=part,math_status='not_applicable',achieved_order=0,
                             requested_order=k,reason=str(exc),
                             family='two-stage Osada (not literal Eq 6.1)')
            return out
        out=state.with_estimate(est)
        out.extra.update(partials=part,math_status=status,achieved_order=got,requested_order=k,
                         theta_estimate=b.to_str(theta,d),theta_order=tk,theta_status=tstatus,
                         family='two-stage Osada (not literal Eq 6.1)')
        return out
