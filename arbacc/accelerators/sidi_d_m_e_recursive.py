"""Independent E-recursion evaluator for Sidi's d^(m) determining system.

NOT labelled Ford-Sidi W^(m): this is a mathematically equivalent way of
eliminating the auxiliary basis in Sidi (2003), Def. 6.2.2, Eq. (6.2.3)
using the general E-algorithm recurrence. It serves as an independently
structured numerical comparison to the existing direct linear solver.

The source provides A_R, R>=1, as partials[R-1], and A_0=0.
"""
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials
from arbacc.accelerators.sidi_d_m import _orders


@register('accelerators','sidi_d_m_e_recursive')
class SidiDMRecursiveE(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Sidi, Practical Extrapolation Methods: Theory and Applications (2003)', 'url': 'https://doi.org/10.1017/CBO9780511546815', 'locator': 'section 6.2', 'relation': 'implementation_variant', 'implementation_note': 'Alternative E-recursive elimination for the same d^(m) system; not a new method.'}
    name=display_name='sidi_d_m_e_recursive'
    PARAM_SPEC={
        'order':{'type':'int','min':0,'default':2,'short':'N'},
        'm':{'type':'int','min':1,'default':2,'short':'m'},
        'alpha':{'type':'str','default':'0','short':'a'},
        'orders':{'type':'str','default':'','short':'orders'},
        'pivot_rel_tol':{'type':'str','default':'auto','short':'ptol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',2)
        self.m=self.params.get('m',2)
        if type(self.order) is not int or self.order<0:raise ValueError('order must be a nonnegative int')
        if type(self.m) is not int or self.m<1:raise ValueError('m must be a positive int')
        self.group_orders=_orders(self.params,self.order,self.m)
        self.active=max((j+1 for j,v in enumerate(self.group_orders) if v),default=0)

    def required_input(self,state):
        return state.iteration+self.order+max(1,self.active)

    def step(self,source,state,ctx):
        b,d,n,N=ctx.backend,ctx.dps,state.iteration,self.order
        alpha=ctx.number(self.params.get('alpha','0'))
        if not b.is_finite(alpha,d):raise ValueError('alpha must be finite')
        partials=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        if not N:
            result=state.with_estimate(partials[n]);result.extra.update(partials=partials,math_status='identity_order_zero')
            return result
        # Build all auxiliary sequences in the same row/column ordering
        # as the direct Sidi defining system, but without solving that system.
        gs=[[] for _ in range(N)]
        samples=[]
        for ell in range(N+1):
            R=n+ell+1
            r=ctx.number(R)
            shift=b.add(r,alpha,d)
            if b.sign(shift,d)==0:raise ArithmeticError('Sidi d^(m) singular R+alpha')
            inv=b.div(ctx.number(1),shift,d)
            samples.append(partials[R-1])
            col=0;r_power=ctx.number(1)
            for degree in range(1,self.m+1):
                r_power=b.mul(r_power,r,d)
                count=self.group_orders[degree-1]
                if not count:continue
                difference=ctx.number(0)
                for j in range(degree+1):
                    q=R-1+j
                    value=partials[q-1] if q else ctx.number(0)
                    difference=b.add(difference,b.mul(ctx.number((-1)**(degree-j)*comb(degree,j)),value,d),d)
                basis=b.mul(r_power,difference,d)
                factor=ctx.number(1)
                for _ in range(count):
                    gs[col].append(b.mul(basis,factor,d))
                    factor=b.mul(factor,inv,d)
                    col+=1
            assert col==N
        # General E-algorithm recurrence; g rows shrink after each step.
        cur=samples
        tol_text=self.params.get('pivot_rel_tol','auto')
        tol=ctx.number(f'1e-{max(12,d//2)}') if tol_text=='auto' else ctx.number(tol_text)
        if not b.is_finite(tol,d) or b.sign(tol,d)<0:raise ValueError('Invalid pivot tolerance')
        for level in range(N):
            g=gs[level]
            next_cur=[];next_gs={i:[] for i in range(level+1,N)}
            for j in range(len(cur)-1):
                a,bb=g[j],g[j+1]
                den=b.sub(bb,a,d)
                scale=b.abs_val(a,d)
                ab=b.abs_val(bb,d)
                if b.sign(b.sub(ab,scale,d),d)>0:scale=ab
                threshold=b.mul(tol,scale,d)
                if b.sign(den,d)==0 or b.sign(b.sub(b.abs_val(den,d),threshold,d),d)<=0:
                    raise ArithmeticError(f'Sidi d^(m) E evaluator: near singular level={level+1}, j={j}')
                next_cur.append(b.div(b.sub(b.mul(bb,cur[j],d),b.mul(a,cur[j+1],d),d),den,d))
                for i in range(level+1,N):
                    h=gs[i]
                    next_gs[i].append(b.div(b.sub(b.mul(bb,h[j],d),b.mul(a,h[j+1],d),d),den,d))
            for i,v in next_gs.items():gs[i]=v
            cur=next_cur
        if not b.is_finite(cur[0],d):raise ArithmeticError('Sidi d^(m) E nonfinite result')
        result=state.with_estimate(cur[0])
        result.extra.update(partials=partials,math_status='full_order',method_family='sidi_d_m',evaluator='E_recursion')
        return result
