"""Independent rational linear-system, determinant and recursive oracles."""
from fractions import Fraction as F
from functools import lru_cache
import os
import subprocess
import pytest
from arbacc.core import get,AlgoState
from tests.test_special_sources import Values,Terms
from tests.test_extended_series import ext_ctx,relative_close,mp

NAMES=['iterated_aitken','wynn_epsilon_fixed','levin_sidi_m']


def solve(matrix,rhs):
    a=[row[:]+[value] for row,value in zip(matrix,rhs)]
    for col in range(len(a)):
        pivot=next(i for i in range(col,len(a)) if a[i][col])
        a[col],a[pivot]=a[pivot],a[col]
        divisor=a[col][col]
        a[col]=[x/divisor for x in a[col]]
        for i in range(len(a)):
            if i!=col:
                factor=a[i][col]
                a[i]=[x-factor*y for x,y in zip(a[i],a[col])]
    return [row[-1] for row in a]


def rising(x,r):
    result=F(1)
    for i in range(r):result*=x+i
    return result


def number(x):return mp.mpf(x.numerator)/x.denominator


@pytest.mark.parametrize('remainder',['next','t','u','v','v_shift'])
@pytest.mark.parametrize('gamma',['4.5','7','100.5'])
@pytest.mark.parametrize('order',[1,2,3,4])
def test_m_against_model_linear_system(remainder,gamma,order,ext_ctx):
    values=[F((-1)**j,j+1)+F(2,j+2) for j in range(16)]
    terms=[values[0]]+[values[i]-values[i-1] for i in range(1,len(values))]
    g=F(gamma)
    algo=get('accelerators','levin_sidi_m')({'order':order,'gamma':gamma,'remainder':remainder})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in [0,1,2,7]:
        if state.iteration!=n:state=AlgoState(iteration=n)
        matrix=[]
        for i in range(n,n+order+1):
            offset=int(remainder in ('next','v_shift'))
            a=terms[i+offset]
            omega=(a*terms[i+offset+1]/(terms[i+offset+1]-a) if remainder in ('v','v_shift') else
                   (-(g+i)*a if remainder=='u' else a))
            matrix.append([F(1)]+[omega/rising(-g-i,r) for r in range(order)])
        reference=solve(matrix,values[n:n+order+1])[0]
        need=algo.required_input(state)
        source.extend_to(need-1)
        state=algo.step(source,state,ext_ctx)
        assert len(source)==need
        relative_close(ext_ctx,state.estimate,number(reference),digits=55)


@pytest.mark.parametrize('order',[0,1,2,3])
def test_iterated_aitken_recursive_fraction_oracle(order,ext_ctx):
    values=[F((-1)**j,j+1)+F(2,j+2) for j in range(20)]
    @lru_cache(None)
    def reference(k,n):
        if not k:return values[n]
        a,b,c=[reference(k-1,n+j) for j in range(3)]
        return a-(b-a)**2/(c-2*b+a)
    algo=get('accelerators','iterated_aitken')({'order':order});state=AlgoState()
    source=Values([number(v) for v in values],ext_ctx)
    for n in range(4):
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(reference(order,n)),digits=55)


@pytest.mark.parametrize('order',[0,1,2,3])
def test_fixed_epsilon_independent_linear_system(order,ext_ctx):
    # Shanks model: s_(n+i)=s+sum c_j*Delta s_(n+i+j).
    values=[F((-1)**j,j+1)+F(2,j+2) for j in range(20)]
    algo=get('accelerators','wynn_epsilon_fixed')({'order':order});state=AlgoState()
    source=Values([number(v) for v in values],ext_ctx)
    for n in range(4):
        matrix=[[F(1)]+[values[n+i+j+1]-values[n+i+j] for j in range(order)] for i in range(order+1)]
        expected=solve(matrix,values[n:n+order+1])[0]
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(expected),digits=55)


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('order',[0,1,2,3])
def test_new_transform_input_contract_terms_sequences_and_constants(name,order,ext_ctx):
    algo=get('accelerators',name)({'order':order})
    values=[mp.mpf(3)+mp.mpf('.4')**i for i in range(25)]
    raw,terms=Values(values,ext_ctx),Terms(values,ext_ctx)
    s,t=AlgoState(),AlgoState()
    for _ in range(4):
        need=algo.required_input(s)
        s=algo.step(raw,s,ext_ctx);t=algo.step(terms,t,ext_ctx)
        assert len(raw)==len(terms)==need
        relative_close(ext_ctx,s.estimate,t.estimate,digits=55)
    const=algo.step(Values([mp.mpf(5)]*25,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,const.estimate,mp.mpf(5))


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('order',[-1,True,1.5,'2'])
def test_invalid_new_transform_order(name,order):
    with pytest.raises(ValueError):get('accelerators',name)({'order':order})


@pytest.mark.parametrize('gamma',['0','-1','nan','inf','1.5'])
def test_invalid_m_gamma(gamma,ext_ctx):
    algo=get('accelerators','levin_sidi_m')({'order':4,'gamma':gamma})
    with pytest.raises(ValueError):algo.step(Values([mp.mpf(i) for i in range(10)],ext_ctx),AlgoState(),ext_ctx)


def test_m_high_order_geometric_kernel(ext_ctx):
    values=[mp.mpf(3)+mp.mpf('-.5')**i for i in range(45)]
    algo=get('accelerators','levin_sidi_m')({'order':40,'gamma':'41.5','remainder':'t'})
    result=algo.step(Values(values,ext_ctx),AlgoState(iteration=1),ext_ctx)
    relative_close(ext_ctx,result.estimate,mp.mpf(3),digits=50)


def test_fifth_cpp_transforms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--fifth-algorithm-values'],text=True).splitlines()
    values=[mp.fsum((-mp.mpf(1))**j/(j+1) for j in range(i+1)) for i in range(40)]
    for line in lines:
        name,n,k,remainder,gamma,value=line.split('\t')
        algo=get('accelerators',name)({'order':int(k),'remainder':remainder,'gamma':gamma})
        source=Values(values,ext_ctx);state=AlgoState()
        for _ in range(int(n)+1):state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,mp.mpf(value),digits=9)
    assert len(lines)==288


def test_iterated_aitken_and_shanks_are_distinct_at_order_two(ext_ctx):
    values=[number(F((-1)**j,j+1)+F(2,j+2)) for j in range(10)]
    estimates=[]
    for name in ['iterated_aitken','shanks']:
        estimates.append(get('accelerators',name)({'order':2}).step(Values(values,ext_ctx),AlgoState(),ext_ctx).estimate)
    b,d=ext_ctx.backend,ext_ctx.dps
    assert b.sign(b.sub(b.abs_val(b.sub(*estimates,d),d),ext_ctx.number('1e-5'),d),d)>0
