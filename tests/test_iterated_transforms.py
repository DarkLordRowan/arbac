"""Recursive exact-fraction oracles and cross-language weighted transforms."""
from fractions import Fraction
from functools import lru_cache
import os
import subprocess
import pytest
from arbacc.core import get
from arbacc.core.accelerator import AlgoState
from tests.test_mathematical_oracles import Terms,mp
from tests.test_extended_series import ext_ctx,relative_close


def iterated_reference(name,values,k,n):
    @lru_cache(None)
    def transform(level,index):
        if level==0: return values[index]
        if name=='overholt':
            left=(values[index+level]-values[index+level-1])**level
            right=(values[index+level+1]-values[index+level])**level
            return (left*transform(level-1,index+1)-right*transform(level-1,index))/(left-right)
        s0,s1,s2,s3=(transform(level-1,index+j) for j in range(4))
        d0,d1,d2=s1-s0,s2-s1,s3-s2
        return s1+d0*d1*(d1-d2)/(d0*d1-2*d0*d2+d1*d2)
    return transform(k,n)


@pytest.mark.parametrize('name',['overholt','lubkin_w'])
@pytest.mark.parametrize('order',[0,1,2,3])
def test_iterated_fraction_oracles(name,order,ext_ctx):
    values=[Fraction((-1)**j,j+1)+Fraction(2,j+2) for j in range(20)]
    source=Terms([mp.mpf(x.numerator)/x.denominator for x in values],ext_ctx)
    algo=get('accelerators',name)({'order':order}); state=AlgoState()
    for n in range(3):
        need=algo.required_input(state)
        state=algo.step(source,state,ext_ctx)
        assert max(source.accesses)==need-1
        expected=iterated_reference(name,values,order,n)
        relative_close(ext_ctx,state.estimate,mp.mpf(expected.numerator)/expected.denominator,digits=55)


@pytest.mark.parametrize('name',['overholt','lubkin_w'])
def test_iterated_geometric_kernel_and_constant(name,ext_ctx):
    for order in [1,2,3]:
        algo=get('accelerators',name)({'order':order})
        for values in [[mp.mpf(3)]*20,[3+mp.mpf('.5')**n for n in range(20)]]:
            state=algo.step(Terms(values,ext_ctx),AlgoState(),ext_ctx)
            relative_close(ext_ctx,state.estimate,mp.mpf(3))


@pytest.mark.parametrize('name',['overholt','lubkin_w'])
@pytest.mark.parametrize('order',[-1,True,1.5,'2'])
def test_iterated_invalid_orders(name,order):
    with pytest.raises(ValueError): get('accelerators',name)({'order':order})


def test_third_cpp_algorithms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary: pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    output=subprocess.check_output([binary,'--third-algorithm-values'],text=True)
    terms=[(-mp.mpf(1))**j/(j+1) for j in range(40)]
    sums=[mp.fsum(terms[:j+1]) for j in range(40)]
    for line in output.splitlines():
        name,n,order,remainder,beta,value=line.split('\t')
        algo=get('accelerators',name)({'order':int(order),'remainder':remainder,'beta':beta})
        source=Terms(sums,ext_ctx); state=AlgoState()
        for _ in range(int(n)+1): state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,mp.mpf(value),digits=9)
    assert len(output.splitlines())==273
