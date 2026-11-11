"""Sidi d^(m) defining equations on nonuniform R_l = 1+stride*(n+l).

Source: Sidi (2003), Section 6.2; Ford--Sidi (1987) Section 1.
This is a new sampling variant of the existing direct d^(m) implementation,
not a new fundamental mathematical transform.
"""
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials
from arbacc.accelerators.sidi_d_m import _orders
from arbacc.accelerators._generalized_models import solve_linear


@register('accelerators','sidi_dm_strided')
class SidiDMStrided(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Sidi, Practical Extrapolation Methods: Theory and Applications (2003)', 'url': 'https://doi.org/10.1017/CBO9780511546815', 'locator': 'section 6.2', 'relation': 'local_variant', 'implementation_note': 'Nonuniform R_l sampling extension of the defining d^(m) system.'}
    name=display_name='sidi_dm_strided'
    PARAM_SPEC={
        'order':{'type':'int','default':3,'min':0,'short':'k'},
        'm':{'type':'int','default':2,'min':1,'short':'m'},
        'alpha':{'type':'str','default':'0','short':'alpha'},
        'orders':{'type':'str','default':'','short':'orders'},
        'stride':{'type':'int','default':1,'min':1,'short':'stride'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',3);self.m=self.params.get('m',2);self.stride=self.params.get('stride',1)
        if type(self.order) is not int or self.order<0:raise ValueError('order must be nonnegative int')
        if type(self.m) is not int or self.m<1:raise ValueError('m must be positive int')
        if type(self.stride) is not int or self.stride<1:raise ValueError('stride must be positive int')
        self.group_orders=_orders(self.params,self.order,self.m)
        self.active=max((k+1 for k,count in enumerate(self.group_orders) if count),default=0)
    def R(self,state,j):return 1+self.stride*(state.iteration+j)
    def required_input(self,state):return self.R(state,self.order)+max(1,self.active)-1
    def step(self,source,state,ctx):
        b,d,k=ctx.backend,ctx.dps,self.order
        alpha=ctx.number(self.params.get('alpha','0'))
        if not b.is_finite(alpha,d):raise ValueError('invalid alpha')
        partials=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        if not k:
            out=state.with_estimate(partials[self.R(state,0)-1]);out.extra.update(partials=partials,math_status='identity_order_zero');return out
        A=[];rows=[]
        for ell in range(k+1):
            R=self.R(state,ell)
            r=ctx.number(R)
            shift=b.add(r,alpha,d)
            if b.sign(shift,d)==0:raise ArithmeticError('Sidi d^(m) singular R+alpha')
            inv=b.div(ctx.number(1),shift,d)
            row=[ctx.number(1)]
            degree_factor=ctx.number(1)
            for degree in range(1,self.m+1):
                degree_factor=b.mul(degree_factor,r,d)
                count=self.group_orders[degree-1]
                if not count:continue
                diff=ctx.number(0)
                for j in range(degree+1):
                    q=R-1+j
                    value=partials[q-1] if q>0 else ctx.number(0)
                    diff=b.add(diff,b.mul(ctx.number((-1)**(degree-j)*comb(degree,j)),value,d),d)
                base=b.mul(degree_factor,diff,d)
                power=ctx.number(1)
                for _ in range(count):
                    row.append(b.mul(base,power,d))
                    power=b.mul(power,inv,d)
            if len(row)!=k+1:raise RuntimeError('incorrect Sidi d^(m) basis length')
            rows.append(row);A.append(partials[R-1])
        answer=solve_linear(rows,A,ctx,self.params.get('pivot_tol','auto'))[0]
        out=state.with_estimate(answer)
        out.extra.update(partials=partials,math_status='full_order',achieved_order=k,m=self.m,stride=self.stride,
                         model_family='Sidi d^(m) strided')
        return out
