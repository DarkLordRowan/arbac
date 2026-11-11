"""Ford--Sidi W^(m) recursion, normal column ordering.

Source: Ford & Sidi, SIAM J. Numer. Anal. 24 (1987), 1212--1232,
Section 4 and Appendix B; Sidi, Practical Extrapolation Methods (2003),
Algorithm 7.3.5.  The recurrence is implemented literally, retaining all
triangle cells for transparency (O(m*k^2) memory, NOT the optimized
O(m*k) storage of the original FORTRAN). No silent singularity fallback.

GREP(m) model: s_l = A + sum_{j=1}^m phi_j(t_l)*P_j(t_l).
For normally ordered columns: phi_1,...,phi_m,t*phi_1,t*phi_2,...
"""
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import extend_partials, series_term


def _parse_specs(text, label):
    values = [x.strip() for x in str(text).split(',') if x.strip()]
    if not values:
        raise ValueError(label + ' must be a nonempty comma-separated list')
    return values


def _check_divisor(v, reference, ctx, label, relative='auto'):
    b,d=ctx.backend,ctx.dps
    if not b.is_finite(v,d) or b.sign(v,d)==0:
        raise ArithmeticError('Ford-Sidi Wm singular/uncertain '+label)
    tol = ctx.number(f'1e-{max(14,d//2)}') if relative=='auto' else ctx.number(relative)
    if not b.is_finite(tol,d) or b.sign(tol,d)<0:
        raise ValueError('Ford-Sidi pivot_tol must be finite and nonnegative')
    if b.sign(tol,d)!=0 and b.sign(b.sub(b.abs_val(v,d),b.mul(tol,reference,d),d),d)<=0:
        raise ArithmeticError('Ford-Sidi Wm near-singular '+label)
    return v


def wm_approximations(samples,t_values,phi_values,ctx,pivot_tol='auto'):
    """Compute A_p^(0), p=0..L by EXACT recurrence of Sidi Alg. 7.3.5.

    samples: a(t_l), t_values: t_l!=0, phi_values[k][l]: phi_(k+1)(t_l).
    All arithmetic through the context backend, including the recurrence.
    """
    b,d=ctx.backend,ctx.dps
    m=len(phi_values); L=len(samples)-1
    if m<1 or L<0 or len(t_values)!=L+1 or any(len(x)!=L+1 for x in phi_values):
        raise ValueError('Ford-Sidi Wm inconsistent dimensions')
    psi_a={};psi_i={};g={};q={};output=[samples[0]]
    one=ctx.number(1)
    for j in range(L+1):
        v=phi_values[0][j];tj=t_values[j]
        _check_divisor(v,b.abs_val(v,d),ctx,f'phi1[{j}]',relative='0')
        _check_divisor(tj,b.abs_val(tj,d),ctx,f't[{j}]',relative='0')
        psi_a[j,0]=b.div(samples[j],v,d)
        psi_i[j,0]=b.div(one,v,d)
        for k in range(2,m+1):g[k,j,0]=b.div(phi_values[k-1][j],v,d)
        g[m+1,j,0]=tj
        q[1,j,0]=b.div(one,tj,d)
    for l in range(1,L+1):
        for p in range(1,l+1):
            j=l-p
            if p<=m:
                aa=g[p+1,j+1,p-1];bb=g[p+1,j,p-1]
                D=b.sub(aa,bb,d)
                scale=b.abs_val(aa,d)
                ab=b.abs_val(bb,d)
                if b.sign(b.sub(ab,scale,d),d)>0:scale=ab
                _check_divisor(D,scale,ctx,f'D[{j},{p}]',relative=pivot_tol)
                for k in range(p+2,m+2):
                    g[k,j,p]=b.div(b.sub(g[k,j+1,p-1],g[k,j,p-1],d),D,d)
            if p<=m-1:
                v=g[m+1,j,p]
                _check_divisor(v,b.abs_val(v,d),ctx,f'psi_g[{j},{p}]',relative=pivot_tol)
                q[p+1,j,p]=b.div(ctx.number((-1)**p),v,d)
            for i in range(1,min(p-1,m-1)+1):
                left=q[i,j,p-1];right=q[i,j+1,p-1]
                _check_divisor(left,b.abs_val(left,d),ctx,f'q_left[{j},{p},{i}]',relative=pivot_tol)
                _check_divisor(right,b.abs_val(right,d),ctx,f'q_right[{j},{p},{i}]',relative=pivot_tol)
                reciprocal_diff=b.sub(b.div(one,left,d),b.div(one,right,d),d)
                Dq=b.mul(q[i,j+1,p-2],reciprocal_diff,d)
                scale=b.abs_val(q[i,j+1,p-2],d)
                _check_divisor(Dq,scale,ctx,f'Dq[{j},{p},{i}]',relative=pivot_tol)
                q[i+1,j,p]=b.div(b.sub(q[i+1,j+1,p-1],q[i+1,j,p-1],d),Dq,d)
            if p>m:
                left=q[m,j,p-1];right=q[m,j+1,p-1]
                _check_divisor(left,b.abs_val(left,d),ctx,f'q_left[{j},{p},{m}]',relative=pivot_tol)
                _check_divisor(right,b.abs_val(right,d),ctx,f'q_right[{j},{p},{m}]',relative=pivot_tol)
                D=b.mul(q[m,j+1,p-2],b.sub(b.div(one,left,d),b.div(one,right,d),d),d)
                _check_divisor(D,b.abs_val(q[m,j+1,p-2],d),ctx,f'D[{j},{p}]',relative=pivot_tol)
            q[1,j,p]=b.div(b.sub(q[1,j+1,p-1],q[1,j,p-1],d),D,d)
            psi_a[j,p]=b.div(b.sub(psi_a[j+1,p-1],psi_a[j,p-1],d),D,d)
            psi_i[j,p]=b.div(b.sub(psi_i[j+1,p-1],psi_i[j,p-1],d),D,d)
            if not b.is_finite(psi_a[j,p],d) or not b.is_finite(psi_i[j,p],d):
                raise ArithmeticError(f'Ford-Sidi Wm nonfinite intermediate p={p}')
        v=psi_i[0,l]
        _check_divisor(v,b.abs_val(v,d),ctx,f'psi_i[0,{l}]',relative='0')
        ans=b.div(psi_a[0,l],v,d)
        if not b.is_finite(ans,d):raise ArithmeticError('Ford-Sidi Wm nonfinite estimate')
        output.append(ans)
    return output


@register('accelerators','ford_sidi_wm')
class FordSidiWM(AcceleratorBase):
    """Wm on custom phi_k(t)=t^power*(log(1/t))^log_power basis."""

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Ford & Sidi, An algorithm for a generalization of the Richardson extrapolation process, SIAM J. Numer. Anal. 24 (1987), 1212-1232', 'url': 'https://doi.org/10.1137/0724080', 'locator': 'section 4 and appendix B', 'relation': 'literature_family', 'implementation_note': 'Ford-Sidi W^(m) recurrence, generalized basis.'}
    name=display_name='ford_sidi_wm'
    PARAM_SPEC={
        'order':{'type':'int','default':3,'min':0,'short':'k'},
        'exponents':{'type':'str','default':'0.5,1.3','short':'exp'},
        'log_powers':{'type':'str','default':'0,0','short':'logs'},
        'shift':{'type':'str','default':'2','short':'shift'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',3)
        if type(self.order) is not int or self.order<0:raise ValueError('order must be nonnegative int')
        self.exponents=_parse_specs(self.params.get('exponents','0.5,1.3'),'exponents')
        self.logs=_parse_specs(self.params.get('log_powers','0,0'),'log_powers')
        if len(self.exponents)!=len(self.logs):raise ValueError('exponents/log_powers sizes differ')
        if len(self.exponents)>12:raise ValueError('m>12 not supported by this reference evaluator')
    def required_input(self,state):return state.iteration+self.order+1
    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        shift=ctx.number(self.params.get('shift','2'))
        if not b.is_finite(shift,d) or b.sign(shift,d)<=0:raise ValueError('shift must be positive')
        partials=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        if not k:
            out=state.with_estimate(partials[n]);out.extra.update(partials=partials,math_status='identity_order_zero');return out
        t=[];phi=[[] for _ in self.exponents]
        for j in range(n,n+k+1):
            tj=b.div(ctx.number(1),b.add(ctx.number(j),shift,d),d)
            if b.sign(tj,d)<=0:raise ValueError('t must be positive')
            t.append(tj)
            logt=b.neg(b.log(tj,d),d)
            for a,exptext in enumerate(self.exponents):
                v=b.pow(tj,ctx.number(exptext),d)
                lp=ctx.number(self.logs[a])
                if b.sign(lp,d):v=b.mul(v,b.pow(logt,lp,d),d)
                phi[a].append(v)
        result=wm_approximations(partials[n:n+k+1],t,phi,ctx,self.params.get('pivot_tol','auto'))[-1]
        out=state.with_estimate(result)
        out.extra.update(partials=partials,math_status='full_order',achieved_order=k,model_family='GREP(m)',m=len(phi))
        return out


def _grid_indices(first,count,mode,stride,sigma):
    if mode not in ('linear','stride','geometric'):raise ValueError('unknown Ford-Sidi grid mode')
    if mode=='linear':return list(range(first,first+count))
    if mode=='stride':return [stride*(first+j) for j in range(count)]
    # Rebuild from zero to preserve Ford--Sidi 1987 R_0=0,
    # R_(l+1)=floor(sigma*R_l)+1 (avoid floats, avoid drift).
    from decimal import Decimal,ROUND_FLOOR
    s=Decimal(str(sigma))
    if not s.is_finite() or s<=1:raise ValueError('geometric sigma must be >1')
    seq=[0]
    for _ in range(first+count-1):
        next_r=int((s*seq[-1]).to_integral_value(rounding=ROUND_FLOOR))+1
        if next_r>200000:raise ValueError('Ford-Sidi index cap exceeded (200000)')
        seq.append(next_r)
    return seq[first:]


@register('accelerators','ford_sidi_dm_wm')
class FordSidiDMWM(AcceleratorBase):
    """Original Ford--Sidi d-transform example from 1987, Eqs. B.3--B.5.

    g_k(l)=(R_l+1)^k * Delta^(k-1)u_(R_l), t_l=1/(R_l+1),
    a(l)=sum_(r=0)^R_l u_r, normal Wm ordering.
    """

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Ford & Sidi, An algorithm for a generalization of the Richardson extrapolation process, SIAM J. Numer. Anal. 24 (1987), 1212-1232', 'url': 'https://doi.org/10.1137/0724080', 'locator': 'appendix B', 'relation': 'literature_family', 'implementation_note': 'Ford-Sidi d example via W^(m) recursion.'}
    name=display_name='ford_sidi_dm_wm'
    PARAM_SPEC={
        'order':{'type':'int','default':3,'min':0,'short':'k'},
        'm':{'type':'int','default':2,'min':1,'short':'m'},
        'grid':{'type':'enum','default':'linear','values':['linear','stride','geometric'],'short':'grid'},
        'stride':{'type':'int','default':2,'min':1,'short':'stride'},
        'sigma':{'type':'str','default':'1.3','short':'sigma'},
        'pivot_tol':{'type':'str','default':'auto','short':'tol'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',3);self.m=self.params.get('m',2)
        self.grid=self.params.get('grid','linear');self.stride=self.params.get('stride',2)
        self.sigma=self.params.get('sigma','1.3')
        if type(self.order) is not int or self.order<0:raise ValueError('order must be nonnegative int')
        if type(self.m) is not int or not 1<=self.m<=8:raise ValueError('m must be 1..8')
        if type(self.stride) is not int or self.stride<1:raise ValueError('stride must be positive int')
        if self.grid not in ('linear','stride','geometric'):raise ValueError('unknown grid')
    def _indices(self,state):
        return _grid_indices(state.iteration,self.order+1,self.grid,self.stride,self.sigma)
    def required_input(self,state):
        return self._indices(state)[-1]+self.m
    def step(self,source,state,ctx):
        b,d,k=ctx.backend,ctx.dps,self.order
        idx=self._indices(state)
        partials=extend_partials(source,state.extra.get('partials',[]),ctx,self.required_input(state))
        if not k:
            out=state.with_estimate(partials[idx[0]])
            out.extra.update(partials=partials,math_status='identity_order_zero');return out
        samples=[];t=[];phi=[[] for _ in range(self.m)]
        for R in idx:
            samples.append(partials[R])
            t.append(b.div(ctx.number(1),ctx.number(R+1),d))
            for j in range(1,self.m+1):
                diff=ctx.number(0)
                for q in range(j):
                    term=series_term(source,R+q,ctx)
                    diff=b.add(diff,b.mul(ctx.number((-1)**(j-1-q)*comb(j-1,q)),term,d),d)
                phi[j-1].append(b.mul(ctx.number((R+1)**j),diff,d))
        estimate=wm_approximations(samples,t,phi,ctx,self.params.get('pivot_tol','auto'))[-1]
        result=state.with_estimate(estimate)
        result.extra.update(partials=partials,math_status='full_order',achieved_order=k,m=self.m,
                            model_family='Ford-Sidi d-via-Wm',R_indices=idx)
        return result
