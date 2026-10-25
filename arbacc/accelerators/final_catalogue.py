"""Final catalogue families; references beside the mathematical definitions."""
from arbacc.core.registry import register
from arbacc.accelerators.direct import _FixedOrder,_partials,Levin


@register('accelerators','chang_wynn')
class ChangWynn(_FixedOrder):
    """Return T_(2k)^(n) of Chang et al. (2019), Eq. (3.20).

    https://arxiv.org/pdf/1903.10198. k>=1 needs 2k+2 values; this is not
    the input contract of ordinary epsilon. Unavailable cells propagate.
    """
    name=display_name='chang_wynn'

    def required_input(self,state):return state.iteration+(2*self.order+2 if self.order else 1)

    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        s=_partials(source,state,ctx,self.required_input(state))
        estimate=s[-1]
        if not k:estimate=s[n]
        else:
            values=s[n:n+2*k+2]
            differences=[b.sub(values[i+1],values[i],d) for i in range(len(values)-1)]
            previous=[None if b.sign(x,d)==0 else b.div(ctx.number(1),x,d) for x in differences]
            row,factors=[],[]
            for j in range(len(values)-3):
                a,c,e=differences[j:j+3]
                left,right=b.sub(c,a,d),b.sub(e,c,d)
                denominator=b.sub(b.mul(e,left,d),b.mul(a,right,d),d)
                value=factor=None
                if b.sign(denominator,d):
                    value=b.sub(values[j+1],b.div(b.mul(b.mul(a,c,d),right,d),denominator,d),d)
                    factor=b.div(b.mul(left,right,d),denominator,d)
                row.append(value);factors.append(factor)
            if row[0] is not None:estimate=row[0]
            for column in range(2,2*k):
                following=[]
                for j in range(len(row)-1):
                    value=None
                    if row[j] is not None and row[j+1] is not None and previous[j+1] is not None and factors[j] is not None:
                        difference=b.sub(row[j+1],row[j],d)
                        if b.sign(difference,d):
                            coefficient=b.add(ctx.number(1-column),b.mul(ctx.number(column),factors[j],d),d)
                            value=b.add(previous[j+1],b.div(coefficient,difference,d),d)
                    following.append(value)
                previous,row=row,following
                if (column+1)%2==0 and row[0] is not None:estimate=row[0]
        result=state.with_estimate(estimate);result.extra['partials']=s
        return result


@register('accelerators','homeier_j')
class HomeierJ(Levin):
    """Generalized differences Delta/delta, Homeier (2000), (33),(94).

    https://arxiv.org/pdf/math/0005209. Constant delta gives Drummond;
    pochhammer with shift=p-1 gives pJ. Power is another explicit nonzero
    choice of delta, not a claim of convergence for arbitrary input.
    """
    name=display_name='homeier_j'
    PARAM_SPEC={**Levin.PARAM_SPEC,
        'max_order':{'type':'int','default':30,'min':1,'short':'max'},
        'safeguard':{'type':'str','default':'1e-12','short':'safe'},
        'delta_mode':{'type':'enum','values':['constant','pochhammer','power'],'default':'constant','short':'delta'},
        'delta_shift':{'type':'str','default':'2','short':'shift'},
        'delta_power':{'type':'int','default':2,'min':1,'short':'power'}}

    def __init__(self,params=None):
        super().__init__(params)
        self.max_order=self.params.get('max_order',30)
        self.power=self.params.get('delta_power',2)
        for x in (self.max_order,self.power):
            if isinstance(x,bool) or not isinstance(x,int) or x<1:raise ValueError('max_order and delta_power must be positive integers')
        if self.order>self.max_order:raise ValueError('order exceeds max_order')
        self.mode=self.params.get('delta_mode','constant')
        if self.mode not in self.PARAM_SPEC['delta_mode']['values']:raise ValueError('unknown delta mode')

    def delta(self,index,level,ctx):
        b,d=ctx.backend,ctx.dps
        if self.mode=='constant':return ctx.number(1)
        z=b.add(b.add(ctx.number(index),self.beta(ctx),d),b.mul(ctx.number(self.params.get('delta_shift','2')),ctx.number(level),d),d)
        divisor=b.mul(z,b.add(z,ctx.number(1),d),d) if self.mode=='pochhammer' else b.pow(z,ctx.number(self.power),d)
        return b.div(ctx.number(1),divisor,d)

    def step(self,source,state,ctx):
        b,d,n,k=ctx.backend,ctx.dps,state.iteration,self.order
        self.beta(ctx)
        safe=ctx.number(self.params.get('safeguard','1e-12'))
        shift=ctx.number(self.params.get('delta_shift','2'))
        if not b.is_finite(safe,d) or b.sign(safe,d)<0 or b.sign(b.sub(ctx.number(1),safe,d),d)<=0:
            raise ValueError('safeguard must be finite and in [0,1)')
        if not b.is_finite(shift,d) or b.sign(shift,d)<0:raise ValueError('delta_shift must be finite and nonnegative')
        s=_partials(source,state,ctx,n+k+1);estimate=s[n+k]
        if not k:estimate=s[n]
        else:
            num,den,bound=[],[],[]
            for i in range(n,n+k+1):
                inverse=self.inverse_remainder(source,i,ctx)
                if inverse is None:break
                num.append(b.mul(s[i],inverse,d));den.append(inverse);bound.append(b.abs_val(inverse,d))
            else:
                for level in range(k):
                    for j in range(k-level):
                        delta=self.delta(n+j,level,ctx)
                        for row in (num,den):row[j]=b.div(b.sub(row[j+1],row[j],d),delta,d)
                        bound[j]=b.div(b.add(bound[j+1],bound[j],d),b.abs_val(delta,d),d)
                if b.sign(b.sub(b.abs_val(den[0],d),b.mul(safe,bound[0],d),d),d)>0:
                    estimate=b.div(num[0],den[0],d)
        result=state.with_estimate(estimate);result.extra['partials']=s
        return result


def condensed_epsilon(values,ctx,threshold,tolerance):
    """QELG-style diagonal selection and 50-cell compaction.

    https://www.netlib.org/quadpack/dqelg.f. Missing cell denotes infinity,
    so its reciprocal contribution is zero without a fabricated huge number.
    On a converged diagonal restart from the latest raw value, preserving
    the last estimate while refilling. Subsequent input is still consumed.
    """
    b,d=ctx.backend,ctx.dps
    one=ctx.number(1)
    table=[None]*52
    count=0;estimate=values[0];have_estimate=False
    stats={'compactions':0,'restarts':0,'accepted':0,'peak_length':0,'capacity_trims':0}
    def absval(x):return b.abs_val(x,d)
    def near(x,tol):return b.sign(b.sub(absval(x),tol,d),d)<=0
    def proven_le(a,c):return b.sign(b.sub(c,a,d),d)>0 or a==c
    def tol(a,c):
        aa,cc=absval(a),absval(c)
        return b.mul(aa if b.sign(b.sub(aa,cc,d),d)>=0 else cc,tolerance,d)
    for raw in values:
        table[count]=raw;count+=1
        stats['peak_length']=max(stats['peak_length'],count)
        if count<3:
            if not have_estimate:estimate=raw
            continue
        end=count-1;newelm=end//2;final=end
        table[end+2]=raw;table[end]=None
        candidate=raw;best_error=None;restart=False
        for i in range(newelm):
            at=end-2*i
            e0,e1,e2=table[at-2],table[at-1],table[at+2]
            if e0 is None or e1 is None or e2 is None:
                final=2*i;break
            d2,d3=b.sub(e2,e1,d),b.sub(e1,e0,d)
            err2,err3=absval(d2),absval(d3)
            if proven_le(err2,tol(e2,e1)) and proven_le(err3,tol(e1,e0)):
                candidate=e2;restart=True;break
            e3=table[at];table[at]=e1
            d1=None if e3 is None else b.sub(e1,e3,d)
            if near(d2,tol(e2,e1)) or near(d3,tol(e1,e0)) or (d1 is not None and near(d1,tol(e1,e3))):
                final=2*i;break
            reciprocal1=ctx.number(0) if d1 is None else b.div(one,d1,d)
            ss=b.sub(b.add(reciprocal1,b.div(one,d2,d),d),b.div(one,d3,d),d)
            if b.sign(ss,d)==0 or b.sign(b.sub(absval(b.mul(ss,e1,d)),threshold,d),d)<=0:
                final=2*i;break
            value=b.add(e1,b.div(one,ss,d),d)
            if not b.is_finite(value,d):final=2*i;break
            table[at]=value
            error=b.add(b.add(err2,absval(b.sub(value,e2,d)),d),err3,d)
            if best_error is None or proven_le(error,best_error):
                candidate,best_error=value,error;stats['accepted']+=1
        estimate=candidate;have_estimate=True
        if restart:
            table=[None]*52;table[0]=raw;count=1;stats['restarts']+=1
            continue
        if final==49:
            final=48;stats['capacity_trims']+=1
        parity=end%2
        for i in range(newelm+1):table[parity+2*i]=table[parity+2*i+2]
        if final!=end:
            for i in range(final+1):table[i]=table[end-final+i]
            stats['compactions']+=1
        count=final+1
    return estimate,stats


@register('accelerators','wynn_epsilon_adaptive')
class WynnEpsilonAdaptive(_FixedOrder):
    """Condensed epsilon diagonals within a moving 2k+1 window."""
    name=display_name='wynn_epsilon_adaptive'
    PARAM_SPEC={**_FixedOrder.PARAM_SPEC,
        'irregularity_threshold':{'type':'str','default':'1e-4','short':'irreg'},
        'tolerance':{'type':'str','default':'auto','short':'tol'}}

    def required_input(self,state):return state.iteration+2*self.order+1

    def step(self,source,state,ctx):
        b,d,n=ctx.backend,ctx.dps,state.iteration
        threshold=ctx.number(self.params.get('irregularity_threshold','1e-4'))
        configured=self.params.get('tolerance','auto')
        tolerance=ctx.number('1e-'+str(d)) if configured=='auto' else ctx.number(configured)
        if not b.is_finite(threshold,d) or b.sign(threshold,d)<=0:raise ValueError('irregularity_threshold must be finite and positive')
        if not b.is_finite(tolerance,d) or b.sign(tolerance,d)<=0 or b.sign(b.sub(ctx.number(1),tolerance,d),d)<=0:
            raise ValueError('tolerance must be finite and in (0,1)')
        s=_partials(source,state,ctx,self.required_input(state))
        estimate,stats=condensed_epsilon(s[n:n+2*self.order+1],ctx,threshold,tolerance)
        result=state.with_estimate(estimate);result.extra.update(partials=s,adaptive=stats)
        return result
