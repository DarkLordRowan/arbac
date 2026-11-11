"""Independent checks of CVZ 2000, Brezinski E, CNCT + representative Homeier pJ.

These tests compare actual Arbac classes to exact rational/polynomial
oracles and analytic limits; no test compares Python against itself.
"""
from fractions import Fraction as F
import pytest
import mpmath

import arbacc.accelerators  # required for dynamic plugin registrations
from arbacc.core import AlgoState, Context, get
from arbacc.precision import get_backend
from arbacc.accelerators.cvz_2000 import cvz_integer_weights
from arbacc.accelerators.cnct_weniger import CNCTWeniger

ref=mpmath.mp.clone();ref.dps=140

class Values:
    kind='sequence'
    def __init__(self, seq, ctx):
        self.data=[ctx.number(ref.nstr(to_mpf(x),115)) for x in seq]
        self.visited=0
    def get(self,n):
        self.extend_to(n);return self.data[n]
    def extend_to(self,n):
        if n<0 or n>=len(self.data):raise IndexError(n)
        self.visited=max(self.visited,n+1)
    def __len__(self):return self.visited

class Terms(Values):
    kind='terms'
    def __init__(self,values,ctx):
        super().__init__([values[0]]+[values[j]-values[j-1] for j in range(1,len(values))],ctx)

class SparsePositive:
    kind='terms'
    def __init__(self,p,ctx):self.p=ctx.number(p);self.ctx=ctx;self.indices=[]
    def term_at(self,n):
        self.indices.append(n)
        b,d=self.ctx.backend,self.ctx.dps
        return b.div(self.ctx.number(1),b.pow(self.ctx.number(n+1),self.p,d),d)
    def get(self,n):
        raise AssertionError('CNCT MUST NOT use contiguous get() for huge sparse indices')


def to_mpf(x):
    if isinstance(x,F):return ref.mpf(x.numerator)/x.denominator
    return ref.mpf(x)

def context(dps=90):return Context(backend=get_backend('mpmath'),dps=dps)

def got(result,ctx):return ref.mpf(ctx.backend.to_str(result.estimate,ctx.dps))

def close(actual,expected,tol='1e-55'):
    assert abs(actual-to_mpf(expected))<=ref.mpf(tol)*max(1,abs(to_mpf(expected)))


@pytest.mark.parametrize('kind,expected',[
    ('cvz_chebyshev',[(2,3)]),
    ('cvz_2a',[(2,3)]),
    ('cvz_2b',[(2,3)]),
])
def test_cvz_n1_published(kind,expected):
    ctx=context()
    result=get('accelerators',kind)({'order':1}).step(Values([F(7,3)],ctx),AlgoState(),ctx)
    close(got(result,ctx),F(7,3)*F(*expected[0]))
    assert result.extra['math_status']=='full_order'


def test_cvz_one_exact_published_coefficients():
    # Cohen et al., page 4, EXACT rational weights for N=1..4.
    expected={
        1:([2],3),2:([16,-8],17),
        3:([98,-80,32],99),4:([576,-544,384,-128],577),
    }
    for n,(nums,den) in expected.items():
        got_coeff,got_d=cvz_integer_weights(n,'one')
        assert [F(a,got_d) for a in got_coeff]==[F(a,den) for a in nums]


def test_cvz_second_exact_published_coefficients():
    # Cohen et al., page 7: both 2A and 2B coincide through N=4.
    expected={
        1:([2],3),2:([16,-8],17),
        3:([110,-90,36],111),
        4:([2288,-2168,1536,-512],2291),
    }
    for flavor in ('A','B'):
        for n,(nums,den) in expected.items():
            coeff,base=cvz_integer_weights(n,flavor)
            assert [F(c,base) for c in coeff]==[F(c,den) for c in nums]


@pytest.mark.parametrize('kind',['cvz_chebyshev','cvz_2a','cvz_2b'])
def test_cvz_real_ln2_and_terms_vs_partials(kind):
    ctx=context(95)
    terms=[(-1)**j*F(1,j+1) for j in range(35)]
    partials=[];s=F(0)
    for a in terms:s+=a;partials.append(s)
    for n in (0,2,5):
        params={'order':18}
        alg=get('accelerators',kind)(params)
        a=alg.step(Values(partials,ctx),AlgoState(iteration=n),ctx)
        b=alg.step(Terms(partials,ctx),AlgoState(iteration=n),ctx)
        close(got(a,ctx),got(b,ctx),'1e-65')
        assert abs(got(a,ctx)-ref.log(2))<ref.mpf('1e-9')
        assert a.extra['math_status']=='full_order'


def test_cvz_rejects_bad_order():
    for name in ('cvz_chebyshev','cvz_2a','cvz_2b'):
        with pytest.raises(ValueError):get('accelerators',name)({'order':0})


def test_e_known_power_and_geometric_kernel_exact():
    ctx=context(100);S=F(13,7)
    values=[S+F(3,n+2)+F(2,1)*F(7,10)**n for n in range(25)]
    for n in [0,1,3,6]:
        alg=get('accelerators','brezinski_e')({'order':2,'basis':'pow:1,geom:0.7','beta':'2'})
        result=alg.step(Values(values,ctx),AlgoState(iteration=n),ctx)
        close(got(result,ctx),S,'1e-60')
        assert result.extra['assistance']=='known_error_basis'


def test_e_known_mixed_power_log_kernel():
    ctx=context(100);S=ref.mpf('1.231237')
    values=[S+3/ref.mpf(n+2)**2+ref.mpf('2.5')/ref.log(n+2) for n in range(20)]
    alg=get('accelerators','brezinski_e')({'order':2,'basis':'pow:2,log:1','beta':'2'})
    result=alg.step(Values(values,ctx),AlgoState(),ctx)
    close(got(result,ctx),S,'1e-60')


def test_e_singular_basis_detected():
    ctx=context()
    alg=get('accelerators','brezinski_e')({'order':2,'basis':'pow:1,pow:1'})
    with pytest.raises(ArithmeticError):
        alg.step(Values([F(7,n+2) for n in range(9)],ctx),AlgoState(),ctx)


def test_e_rejects_invalid_params():
    for p in ({'order':2,'basis':'pow:1'}, {'order':1,'basis':'invalid:1'}, {'order':1,'basis':'log:1','beta':'1'}):
        # Third case fails at step (log(1)==0), first two at creation.
        if p.get('beta')=='1':
            ctx=context()
            with pytest.raises(ValueError):
                get('accelerators','brezinski_e')(p).step(Values([F(3)]*4,ctx),AlgoState(),ctx)
        else:
            with pytest.raises(ValueError):get('accelerators','brezinski_e')(p)


def test_cnct_random_access_zeta2():
    ctx=context(90)
    source=SparsePositive('2',ctx)
    alg=CNCTWeniger({
        'order':6,'condensation_tol':'1e-37','max_condensation_steps':256,
    })
    result=alg.step(source,AlgoState(),ctx)
    assert result.extra['math_status']=='full_order_condensation_truncated'
    assert result.extra['condensation_rigorous'] is False
    assert result.extra['raw_source_calls']==len(source.indices)
    assert max(source.indices)==result.extra['max_raw_source_index']
    # A_j are evaluated numerically, so this is an empirical tolerance,
    # not a theorem concerning all monotone positive series.
    assert abs(got(result,ctx)-ref.pi**2/6)<ref.mpf('1e-9')


def test_cnct_requires_sparse_source():
    ctx=context()
    with pytest.raises(TypeError):
        CNCTWeniger({'order':2}).step(Values([F(1,j+1) for j in range(30)],ctx),AlgoState(),ctx)


def test_pj_recurrence_independent_rational_reference():
    # Independent exact-rational generalized-difference J from Homeier (2000)
    # Eqs. (94), (105); used earlier as an independent oracle.
    ctx=context(110)
    s=[F((-1)**j,j+1)+F(2,j+2) for j in range(30)]
    a=[s[0]]+[s[i]-s[i-1] for i in range(1,len(s))]
    for p in (1,2,3,5):
        for k in (1,2,3,4):
            for n in (0,2):
                beta=F(5,2)
                nums=[s[n+j]/a[n+j+1] for j in range(k+1)]
                den=[1/a[n+j+1] for j in range(k+1)]
                for level in range(k):
                    factors=[F((n+j),1)+beta+(p-1)*level for j in range(len(nums)-1)]
                    nums=[(nums[j+1]-nums[j])*factors[j]*(factors[j]+1) for j in range(len(nums)-1)]
                    den=[(den[j+1]-den[j])*factors[j]*(factors[j]+1) for j in range(len(den)-1)]
                exact=nums[0]/den[0]
                algo=get('accelerators','homeier_pj')({'order':k,'p':p,'beta':'2.5','remainder':'next'})
                got_value=got(algo.step(Values(s,ctx),AlgoState(iteration=n),ctx),ctx)
                close(got_value,exact,'1e-70')


def test_e_near_singular_window_rejected():
    ctx=context(100)
    S=F(13,7)
    # On n=0..2, 1/(n+2), 0.5**n and the constant column
    # are accidentally linearly dependent. This must be diagnosed.
    values=[S+F(3,n+2)+F(2)*F(1,2**n) for n in range(20)]
    method=get('accelerators','brezinski_e')({'order':2,'basis':'pow:1,geom:0.5','beta':'2'})
    with pytest.raises(ArithmeticError):
        method.step(Values(values,ctx),AlgoState(),ctx)


def test_sidi_d_m_direct_vs_e_recursive_exact_model():
    ctx=context(110)
    S=F(17,5);c0=F(1,23);c1=F(1,19)
    # Construct a sequence *exactly* in the Sidi d^(2) model kernel:
    # A_R = S + c0*R*Delta A_(R-1) + c1*R^2*Delta^2 A_(R-1).
    a=[F(0),F(7,3)]
    for R in range(1,13):
        new=(a[R]-S-c0*R*(a[R]-a[R-1]))/(c1*R*R)+2*a[R]-a[R-1]
        a.append(new)
    values=[to_mpf(x) for x in a[1:]]
    params={'order':2,'m':2,'alpha':'0','orders':'1,1'}
    for n in (0,1,2):
        old=get('accelerators','sidi_d_m')(params).step(Values(values,ctx),AlgoState(iteration=n),ctx)
        new=get('accelerators','sidi_d_m_e_recursive')(params).step(Values(values,ctx),AlgoState(iteration=n),ctx)
        close(got(old,ctx),S,'1e-65')
        close(got(new,ctx),S,'1e-65')
        close(got(new,ctx),got(old,ctx),'1e-65')
