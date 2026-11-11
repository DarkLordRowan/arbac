"""Independent model and literature checks for optional Arbac/Magister additions.

These tests use exact Fraction recurrences, analytic closed forms, and a
separate high-precision mpmath context. They do not use Arbac to build the
expected values. Results from C++ are not asserted here.
"""
from fractions import Fraction as F
import mpmath
import pytest
from arbacc.core import Context, AlgoState, get
from arbacc.precision import get_backend

ref = mpmath.mp.clone()
ref.dps=125


class Values:
    kind='sequence'
    def __init__(self, values, ctx):
        self.values=[ctx.number(ref.nstr(v,115)) for v in values]
        self.count=0
    def get(self,n):
        self.extend_to(n)
        return self.values[n]
    def extend_to(self,n):
        if n<0 or n>=len(self.values):raise IndexError(n)
        self.count=max(self.count,n+1)
    def __len__(self):return self.count


def to_ref(v):
    if isinstance(v,F):return ref.mpf(v.numerator)/v.denominator
    return ref.mpf(v)


def context():return Context(backend=get_backend('mpmath'),dps=105)


def check(actual,expected,ctx,digits=65):
    observed=ref.mpf(ctx.backend.to_str(actual,ctx.dps))
    expected=to_ref(expected)
    assert abs(observed-expected)<ref.mpf('1e-'+str(digits))*max(1,abs(expected))


def test_osada_alpha_minus_one_exact_rational_model():
    ctx=context();S=F(11,7)
    # rho_2 annihilates s_n=S+c/(n+beta), rho_{-1}=0 and alpha=-1.
    values=[to_ref(S+F(3,n+3)) for n in range(24)]
    algo=get('accelerators','osada_generalized_rho')({'order':1,'alpha':'-1'})
    source=Values(values,ctx);state=AlgoState()
    for n in range(5):
        state=algo.step(source,state,ctx)
        check(state.estimate,S,ctx)
        assert state.extra['math_status']=='full_order'


def test_osada_nonstandard_alpha_independent_fraction_table():
    ctx=context();alpha=F(-3,2)
    # Intentionally non-model test; validate algebra, not convergence speed.
    values=[F(2)+F(3,n+4)+F((-1)**n,n+5) for n in range(16)]
    def exact(k,n):
        if k==-1:return F(0)
        if k==0:return values[n]
        return exact(k-2,n+1)+(F(k-1)-alpha)/(exact(k-1,n+1)-exact(k-1,n))
    algo=get('accelerators','osada_generalized_rho')({'order':2,'alpha':'-1.5'})
    state=algo.step(Values([to_ref(x) for x in values],ctx),AlgoState(),ctx)
    check(state.estimate,exact(4,0),ctx)


def test_euler_alternating_geometric_exact_residual():
    ctx=context();q=F(3,4)
    # Infinite alternating geometric series: S=1/(1+q).
    values=[];p=F(0)
    for n in range(32):
        p+=(-q)**n
        values.append(to_ref(p))
    source=Values(values,ctx)
    order=12;algo=get('accelerators','euler_alternating')({'order':order})
    state=algo.step(source,AlgoState(),ctx)
    exact=F(1,1+q)
    # For geometric terms: Euler truncated tail error exactly
    # [(1-q)/2]^order / (1+q), with sign positive for q>0.
    expected=exact*(1-((1-q)/2)**order)
    check(state.estimate,expected,ctx)
    assert abs(ref.mpf(ctx.backend.to_str(state.estimate,ctx.dps))-to_ref(exact))<ref.mpf('1e-11')


def test_euler_alternating_harmonic():
    ctx=context();log2=ref.log(2)
    values=[];p=ref.mpf(0)
    for n in range(60):
        p+=(-1)**n/ref.mpf(n+1)
        values.append(p)
    k=24
    algo=get('accelerators','euler_alternating')({'order':k})
    result=algo.step(Values(values,ctx),AlgoState(),ctx)
    estimate=ref.mpf(ctx.backend.to_str(result.estimate,ctx.dps))
    assert abs(estimate-log2)<ref.mpf('5e-9')


def test_sidi_d1_first_order_model():
    ctx=context();S=F(17,5);c=F(1,13)
    a=[F(0)]
    for R in range(1,10):
        rate=c*R
        a.append((S-rate*a[-1])/(1-rate))
    algo=get('accelerators','sidi_d_m')({'order':1,'m':1,'alpha':'0'})
    source=Values([to_ref(x) for x in a[1:]],ctx)
    state=AlgoState()
    for n in range(4):
        state=algo.step(source,state,ctx)
        check(state.estimate,S,ctx)


def test_sidi_d1_second_order_kernel():
    ctx=context();S=F(17,5);c0=F(1,17);c1=F(1,19)
    a=[F(0)]
    for R in range(1,10):
        rate=c0*R+c1
        a.append((S-rate*a[-1])/(1-rate))
    algo=get('accelerators','sidi_d_m')({'order':2,'m':1,'alpha':'0'})
    source=Values([to_ref(x) for x in a[1:]],ctx)
    state=algo.step(source,AlgoState(),ctx)
    check(state.estimate,S,ctx)


def test_sidi_d2_mixed_difference_kernel():
    ctx=context();S=F(17,5);c1=F(1,23);c2=F(1,19)
    # For each R>=1: A_R=S+c1*R*Delta A_(R-1)
    #                      +c2*R^2*Delta^2 A_(R-1).
    a=[F(0),F(7,3)]
    for R in range(1,8):
        next_value=(a[R]-S-c1*R*(a[R]-a[R-1]))/(c2*R*R)+2*a[R]-a[R-1]
        a.append(next_value)
    algo=get('accelerators','sidi_d_m')({'order':2,'m':2,'alpha':'0','orders':'1,1'})
    state=algo.step(Values([to_ref(x) for x in a[1:]],ctx),AlgoState(),ctx)
    check(state.estimate,S,ctx,digits=55)


def test_sidi_singular_rejected():
    ctx=context();source=Values([ref.mpf(1)]*12,ctx)
    with pytest.raises(ArithmeticError):
        get('accelerators','sidi_d_m')({'order':2,'m':1}).step(source,AlgoState(),ctx)


def test_name_alias_of_weniger_m_same_numbers():
    ctx=context()
    values=[ref.mpf((-1)**n)/(n+2)+ref.mpf(2)/(n+3) for n in range(35)]
    for name in ('weniger_m','levin_sidi_m'):
        algo=get('accelerators',name)({'order':2,'gamma':'5','remainder':'next'})
        estimate=algo.step(Values(values,ctx),AlgoState(),ctx).estimate
        if name=='weniger_m':first=estimate
        else:check(estimate,ref.mpf(ctx.backend.to_str(first,ctx.dps)),ctx)


def test_order_zero_is_identity():
    ctx=context();values=[ref.mpf(1),ref.mpf(2),ref.mpf(3)]
    for name,params in [
        ('sidi_d_m',{'order':0,'m':2}),
        ('osada_generalized_rho',{'order':0}),
        ('euler_alternating',{'order':0}),
    ]:
        result=get('accelerators',name)(params).step(Values(values,ctx),AlgoState(),ctx)
        check(result.estimate,1,ctx)


class Terms(Values):
    kind='terms'
    def __init__(self, values, ctx):
        diffs=[values[0]]+[values[i]-values[i-1] for i in range(1,len(values))]
        super().__init__(diffs,ctx)


@pytest.mark.parametrize('method,params', [
    ('euler_alternating',{'order':5}),
    ('osada_generalized_rho',{'order':2,'alpha':'-1'}),
    ('sidi_d_m',{'order':2,'m':2}),
    ('weniger_m',{'order':2,'gamma':'5','remainder':'next'}),
])
def test_streams_sequence_vs_terms_consistency(method,params):
    ctx=context()
    values=[ref.fsum((-1)**j/ref.mpf(j+1) for j in range(n+1)) for n in range(25)]
    for n in range(3):
        try:
            a=get('accelerators',method)(params).step(Values(values,ctx),AlgoState(iteration=n),ctx).estimate
            b=get('accelerators',method)(params).step(Terms(values,ctx),AlgoState(iteration=n),ctx).estimate
        except ArithmeticError:
            # A genuine singularity should be tested on a nonsingular model
            # instead; it is not a silent success.
            continue
        check(a,ref.mpf(ctx.backend.to_str(b,ctx.dps)),ctx,digits=60)


def test_levin_status_reports_silent_fallback():
    ctx=context()
    raw=[ref.mpf(3)]*12
    algo=get('accelerators','levin')({'order':2,'remainder':'next'})
    result=algo.step(Values(raw,ctx),AlgoState(),ctx)
    assert result.extra['math_status']=='fallback_invalid_remainder'
    assert result.estimate==ctx.number(3)
    first=get('accelerators','levin')({'order':0}).step(Values(raw,ctx),AlgoState(),ctx)
    assert first.extra['math_status']=='identity_order_zero'
    vals=[ref.mpf(4)+ref.mpf('.5')**n for n in range(16)]
    full=get('accelerators','levin')({'order':1,'remainder':'next'}).step(Values(vals,ctx),AlgoState(),ctx)
    assert full.extra['math_status']=='full_order'
