"""CVZ 2000 alternating-series acceleration, Algorithms 1, 2_A and 2_B.

Cohen, Rodriguez Villegas & Zagier, Exp. Math. 9 (2000) 3-12:
https://people.math.harvard.edu/~ctm/home/text/others/zagier/acceleration_series/acceleration_series.pdf

Each order N consumes N consecutive signed series terms; the current
iteration n is the start of the tail, and the preceding partial sum is
added without transformation. CVZ guarantees apply only to the moment
classes specified by the authors, not arbitrary alternating series.

The 2_A/2_B implementations compute exact-integer Chebyshev polynomials
and the defining polynomial quotient. The extra O(N^3) integer work is
not a claimed optimal implementation of Algorithm 2; it is a transparent
and independently testable reference.
"""
from __future__ import annotations
from functools import lru_cache
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import series_term, extend_partials


def cvz1_ratios(N):
    """Exact rational c_(N,k)/d_N, for literature regression tests."""
    if N < 1: raise ValueError('N must be >= 1')
    # d_N = T_N(3), integral and satisfies d_{n+1}=6*d_n-d_{n-1}.
    d0,d1=1,3
    for _ in range(2,N+1): d0,d1=d1,6*d1-d0
    d = 3 if N==1 else d1
    # c coefficients using Chebyshev polynomial P_N(1-2x).
    pol = _chebyshev_shifted(N)
    coeff = _quotient_coefficients(pol)
    from fractions import Fraction
    return [Fraction(c,d) for c in coeff]


@lru_cache(maxsize=256)
def _chebyshev_shifted(N):
    """Coefficients of T_N(1-2*x), exactly as integers."""
    if N == 0: return (1,)
    if N == 1: return (1,-2)
    prev=(1,); cur=(1,-2)
    for k in range(2,N+1):
        nxt=[0]*(k+1)
        for i,x in enumerate(cur):
            nxt[i]+=2*x; nxt[i+1]-=4*x
        for i,x in enumerate(prev): nxt[i]-=x
        prev,cur=cur,tuple(nxt)
    return cur


@lru_cache(maxsize=256)
def _cvz_polynomial(N, flavor):
    if flavor=='one': return _chebyshev_shifted(N)
    if flavor not in {'A','B'}:raise ValueError(flavor)
    m=N-1 if flavor=='A' else N//2
    result=[0]*(N+1)
    # CVZ Equations (7)-(8), unnormalised. Common factor cancels.
    for r in range(m+1):
        j=N-2*r
        factor=(-1)**r * comb(m,r) * (j**(m+1))
        for k,x in enumerate(_chebyshev_shifted(abs(j))):
            result[k]+=factor*x
    return tuple(result)


def _quotient_coefficients(pol):
    """[x^j] (Q(-1)-Q(x))/(1+x), j=0..N-1."""
    N=len(pol)-1
    d=sum(v*(-1)**j for j,v in enumerate(pol))
    if d==0:raise ArithmeticError('CVZ denominator Q(-1)=0')
    ans=[d-pol[0]]
    for j in range(1,N):ans.append(-pol[j]-ans[-1])
    assert -pol[N]==ans[-1] if N else True
    return ans


def cvz_integer_weights(N,flavor):
    pol=_cvz_polynomial(N,flavor)
    return _quotient_coefficients(pol),sum(v*(-1)**j for j,v in enumerate(pol))


class _CVZ(AcceleratorBase):
    PARAM_SPEC={'order':{'type':'int','min':1,'default':8,'short':'N'}}
    flavor='one'
    def __init__(self,params=None):
        super().__init__(params)
        self.order=self.params.get('order',8)
        if type(self.order) is not int or not (1<=self.order<=256):
            raise ValueError('CVZ order must be an integer from 1 to 256')

    def required_input(self,state):
        return state.iteration+self.order

    def step(self,source,state,ctx):
        n,N=state.iteration,self.order
        b,d=ctx.backend,ctx.dps
        # For sequence sources, term extraction is by difference. For terms,
        # the prefix sum is computed in the original precision backend.
        partials=extend_partials(source,state.extra.get('partials',[]),ctx,n+N)
        prefix=partials[n-1] if n else ctx.number(0)
        coeff,den=cvz_integer_weights(N,self.flavor)
        numerator=ctx.number(0)
        for j,c in enumerate(coeff):
            # paper a_j: our signed term has local (-1)^j already
            term=series_term(source,n+j,ctx)
            if j%2:term=b.neg(term,d)
            numerator=b.add(numerator,b.mul(ctx.number(c),term,d),d)
        tail=b.div(numerator,ctx.number(den),d)
        value=b.add(prefix,tail,d)
        if not b.is_finite(value,d):
            raise ArithmeticError('Non-finite CVZ value')
        result=state.with_estimate(value)
        result.extra.update(partials=partials,math_status='full_order',algorithm_family='CVZ',coefficients_source='CVZ_2000')
        return result


@register('accelerators','cvz_chebyshev')
class CVZChebyshev(_CVZ):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12', 'url': 'https://doi.org/10.1080/10586458.2000.10504632', 'locator': 'Algorithm 1', 'relation': 'literature_family', 'implementation_note': 'CVZ accelerated alternating-series transformation.'}
    name=display_name='cvz_chebyshev'
    flavor='one'

@register('accelerators','cvz_2a')
class CVZ2A(_CVZ):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12', 'url': 'https://doi.org/10.1080/10586458.2000.10504632', 'locator': 'Algorithm 2A', 'relation': 'literature_family', 'implementation_note': 'CVZ alternating-series transformation.'}
    name=display_name='cvz_2a'
    flavor='A'

@register('accelerators','cvz_2b')
class CVZ2B(_CVZ):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Cohen, Rodriguez Villegas & Zagier, Convergence Acceleration of Alternating Series, Experimental Mathematics 9 (2000), 3-12', 'url': 'https://doi.org/10.1080/10586458.2000.10504632', 'locator': 'Algorithm 2B', 'relation': 'literature_family', 'implementation_note': 'CVZ alternating-series transformation.'}
    name=display_name='cvz_2b'
    flavor='B'
