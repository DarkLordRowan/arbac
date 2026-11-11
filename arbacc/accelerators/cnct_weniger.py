"""Van Wijngaarden condensation + Weniger delta: CNCT, Jentschura et al. 1999.

Original: https://arxiv.org/pdf/math/9809111, Eqs. (2.2)-(2.4), (3.14).

IMPORTANT: a(k) at exponentially large k must be computable by random
access. The ordinary Arbac Stream.get(k) may materialise all intermediate
terms, so this class REFUSES to use it. Supply a source with
source.term_at(k), returning the k-th non-negative term of a positive,
monotonically decreasing and summable series. No support for partial sums.

A_j = sum_{q>=0} 2**q a(2**q*(j+1)-1).
Then the alternating partial sums are accelerated by the original Arbac
Weniger transform using the next condensed term as omega estimate.

Each A_j is truncated numerically. The threshold is a HEURISTIC, not a
rigorous bound on the tail. An inconclusive condensation raises; no
silent claim of accurately computed infinite condensed sums.
"""
from __future__ import annotations
from arbacc.core.accelerator import AcceleratorBase,AlgoState
from arbacc.core.registry import get


class _PrecomputedTerms:
    kind='terms'
    def __init__(self,terms):
        self.terms=terms
    def extend_to(self,n):
        if n<0 or n>=len(self.terms):raise IndexError(n)
    def get(self,n):
        self.extend_to(n)
        return self.terms[n]
    def __len__(self):return len(self.terms)


# Intentionally NOT in the generic accelerator registry: normal streams
# materialise all 2^q-th terms and destroy memory. Use a sparse adapter.
class CNCTWeniger(AcceleratorBase):
    name=display_name='cnct_weniger'
    PARAM_SPEC={
        'order':{'type':'int','min':1,'default':3,'short':'k'},
        'beta':{'type':'str','default':'1','short':'b'},
        'condensation_tol':{'type':'str','default':'1e-24','short':'ctol'},
        'max_condensation_steps':{'type':'int','min':8,'default':512,'short':'maxq'},
    }
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',3)
        self.max_steps=self.params.get('max_condensation_steps',512)
        if type(self.order) is not int or not (1<=self.order<=32):
            raise ValueError('CNCT order must be integer 1..32')
        if type(self.max_steps) is not int or not (8<=self.max_steps<=8192):
            raise ValueError('max_condensation_steps must be integer in 8..8192')

    def required_input(self,state):
        # Contract is count of condensed coefficients, NOT number of raw
        # source evaluations or highest exponentially sampled index.
        return state.iteration+self.order+2

    def step(self,source,state,ctx):
        if getattr(source,'kind',None) not in {'terms',None} or not callable(getattr(source,'term_at',None)):
            raise TypeError('CNCT requires random-access nonnegative series terms: source.term_at(k)')
        b,d=ctx.backend,ctx.dps
        tol=ctx.number(self.params.get('condensation_tol','1e-24'))
        if not b.is_finite(tol,d) or b.sign(tol,d)<=0:
            raise ValueError('condensation_tol must be finite and positive')
        beta=ctx.number(self.params.get('beta','1'))
        if not b.is_finite(beta,d) or b.sign(beta,d)<=0:
            raise ValueError('CNCT beta must be positive and finite')
        zero,one=ctx.number(0),ctx.number(1)
        ncols=self.required_input(state)
        condensed=[]
        calls=0
        max_idx=0
        depths=[]
        for j in range(ncols):
            total=zero
            small=0
            prev=None
            for q in range(self.max_steps):
                index=(1<<q)*(j+1)-1
                a=ctx.number(source.term_at(index))
                calls+=1;max_idx=max(max_idx,index)
                if not b.is_finite(a,d) or b.sign(a,d)<0:
                    raise ValueError('CNCT source requires nonnegative finite terms')
                if prev is not None and b.sign(b.sub(a,prev,d),d)>0:
                    raise ValueError('CNCT needs a monotonically nonincreasing source')
                prev=a
                summand=b.mul(ctx.number(1<<q),a,d)
                total=b.add(total,summand,d)
                # small contribution is not itself a rigorous truncation
                # estimate; require a succession of negligible terms.
                scale=b.abs_val(total,d)
                if b.sign(b.sub(scale,one,d),d)<0:scale=one
                if b.sign(b.sub(b.abs_val(summand,d),b.mul(tol,scale,d),d),d)<0:
                    small+=1
                else:small=0
                if small>=4:
                    depths.append(q+1)
                    break
            else:
                raise ArithmeticError(f'CNCT condensed sum A_{j} did not reach tolerance in {self.max_steps} terms')
            condensed.append(total if j%2==0 else b.neg(total,d))
        transform=get('accelerators','weniger')({'order':self.order,'beta':self.params.get('beta','1'),'remainder':'next'})
        intermediate=transform.step(_PrecomputedTerms(condensed),AlgoState(iteration=state.iteration),ctx)
        status=intermediate.extra.get('math_status','unreported')
        if status not in {'full_order','unreported'}:
            raise ArithmeticError(f'CNCT Weniger did not deliver full order (status={status})')
        result=state.with_estimate(intermediate.estimate)
        result.extra.update(math_status='full_order_condensation_truncated',
            condensation_rigorous=False,
            condensed_terms=ncols,raw_source_calls=calls,
            max_raw_source_index=max_idx,condensation_depths=depths,
            calculated_condensed_terms=condensed)
        return result
