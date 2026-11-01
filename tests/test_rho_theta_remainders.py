"""Rational kernels, exact fractions and independent interpolation tests.

Weniger (1989): https://arxiv.org/pdf/math/0306302, Sections 6.2, 7.3, 9.5, 10.1.
"""
from fractions import Fraction
from functools import lru_cache
import os
import subprocess

import pytest
from arbacc.core import get
from arbacc.core.accelerator import AlgoState
from tests.test_mathematical_oracles import Terms, mp
from tests.test_extended_series import ext_ctx, relative_close


def rho_interpolation(values,n,k,shift="1",power=1):
    if k==0:
        return values[n]
    matrix=[]
    rhs=[]
    for j in range(2*k+1):
        x=(mp.mpf(n+j)+mp.mpf(shift))**power
        value=values[n+j]
        matrix.append([x**i for i in range(k,-1,-1)] + [-value*x**i for i in range(k-1,-1,-1)])
        rhs.append(value*x**k)
    return mp.lu_solve(mp.matrix(matrix),mp.matrix(rhs))[0]


def theta_exact(values,n,k):
    @lru_cache(None)
    def even(level,index):
        if level==0:
            return values[index]
        right=odd(level,index+2)-odd(level,index+1)
        second=right-(odd(level,index+1)-odd(level,index))
        return even(level-1,index+1)+(even(level-1,index+2)-even(level-1,index+1))*right/second
    @lru_cache(None)
    def odd(level,index):
        previous=Fraction(0) if level==1 else odd(level-1,index+1)
        return previous+1/(even(level-1,index+1)-even(level-1,index))
    return even(k,n)


@pytest.mark.parametrize('order',[0,1,2,3])
def test_rho_against_independent_rational_interpolation(order,ext_ctx):
    values=[mp.log(n+2)+mp.mpf(1)/(n+1) for n in range(14)]
    algo=get('accelerators','wynn_rho')({'order':order})
    source=Terms(values,ext_ctx)
    state=AlgoState()
    for n in range(3):
        need=algo.required_input(state)
        state=algo.step(source,state,ext_ctx)
        assert max(source.accesses)==need-1
        relative_close(ext_ctx,state.estimate,rho_interpolation(values,n,order),digits=55)


@pytest.mark.parametrize('order',[1,2])
def test_rho_exact_rational_kernel(order,ext_ctx):
    if order==1:
        values=[7+mp.mpf(3)/(n+2) for n in range(10)]
    else:
        values=[(7*mp.mpf(n+1)**2+3*(n+1)+5)/(mp.mpf(n+1)**2+2*(n+1)+9) for n in range(10)]
    algo=get('accelerators','wynn_rho')({'order':order})
    result=algo.step(Terms(values,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,result.estimate,mp.mpf(7))


@pytest.mark.parametrize('order',[0,1,2])
def test_theta_against_exact_fraction_table(order,ext_ctx):
    values=[Fraction((-1)**n,n+1)+Fraction(2,n+2) for n in range(12)]
    decimal=[mp.mpf(x.numerator)/x.denominator for x in values]
    algo=get('accelerators','brezinski_theta')({'order':order})
    source=Terms(decimal,ext_ctx)
    state=AlgoState()
    for n in range(3):
        need=algo.required_input(state)
        state=algo.step(source,state,ext_ctx)
        assert max(source.accesses)==need-1
        expected=theta_exact(values,n,order)
        relative_close(ext_ctx,state.estimate,mp.mpf(expected.numerator)/expected.denominator)


@pytest.mark.parametrize('name',['levin','weniger','drummond'])
@pytest.mark.parametrize('remainder',['next','t','u','v','v_shift'])
@pytest.mark.parametrize('beta',['1','2.5'])
def test_remainder_variants_finite_formula(name,remainder,beta,ext_ctx):
    terms=[(-mp.mpf(1))**j/(j+1) for j in range(20)]
    sums=[mp.fsum(terms[:j+1]) for j in range(18)]
    algo=get('accelerators',name)({'order':4,'remainder':remainder,'beta':beta})
    source=Terms(sums,ext_ctx)
    state=AlgoState()
    for n in range(3):
        need=algo.required_input(state)
        state=algo.step(source,state,ext_ctx)
        assert max(source.accesses)==need-1
        weights=[]
        for j in range(5):
            i=n+j
            if remainder=='next': omega=terms[i+1]
            elif remainder=='t': omega=terms[i]
            elif remainder=='u': omega=(mp.mpf(beta)+i)*terms[i]
            else:
                i+=int(remainder=='v_shift')
                omega=terms[i]*terms[i+1]/(terms[i+1]-terms[i])
            factor=mp.power(mp.mpf(beta)+n+j,3) if name=='levin' else (mp.rf(mp.mpf(beta)+n+j,3) if name=='weniger' else 1)
            weights.append((-1)**j*mp.binomial(4,j)*factor/omega)
        expected=mp.fsum(weights[j]*sums[n+j] for j in range(5))/mp.fsum(weights)
        relative_close(ext_ctx,state.estimate,expected)


@pytest.mark.parametrize('name',['drummond','wynn_rho','brezinski_theta'])
def test_new_algorithms_constant_and_order_zero(name,ext_ctx):
    values=[mp.mpf(3)]*20
    for order in [0,1,2]:
        algo=get('accelerators',name)({'order':order})
        state=AlgoState()
        source=Terms(values,ext_ctx)
        for _ in range(3):
            state=algo.step(source,state,ext_ctx)
            relative_close(ext_ctx,state.estimate,mp.mpf(3))


@pytest.mark.parametrize('name',['levin','weniger','drummond'])
@pytest.mark.parametrize('beta',['0','-1','nan','inf'])
def test_invalid_beta(name,beta,ext_ctx):
    algo=get('accelerators',name)({'beta':beta})
    with pytest.raises(ValueError):
        algo.step(Terms([mp.mpf(1)]*10,ext_ctx),AlgoState(),ext_ctx)


@pytest.mark.parametrize('name',['levin','weniger','drummond'])
def test_invalid_remainder(name):
    with pytest.raises(ValueError):
        get('accelerators',name)({'remainder':'not-a-remainder'})


@pytest.mark.parametrize('name',['drummond','wynn_rho','brezinski_theta'])
@pytest.mark.parametrize('order',[-1,1.5,True,'2'])
def test_new_algorithms_invalid_order(name,order):
    with pytest.raises(ValueError):
        get('accelerators',name)({'order':order})


def test_new_cpp_algorithms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:
        pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--algorithm-values'],text=True).splitlines()
    values=[(7*mp.mpf(n+1)**2+3*(n+1)+5)/(mp.mpf(n+1)**2+2*(n+1)+9) for n in range(20)]
    for line in lines:
        name,n,order,remainder,value=line.split('\t')
        algo=get('accelerators',name)({'order':int(order),'remainder':remainder})
        source=Terms(values,ext_ctx)
        state=AlgoState()
        for _ in range(int(n)+1):
            state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,mp.mpf(value),digits=8)
    assert len(lines)==42


@pytest.mark.parametrize("shift", ["0.5", "1", "3.25"])
@pytest.mark.parametrize("power", [1, 2, 3])
@pytest.mark.parametrize("order", [0, 1, 2, 3])
def test_rho_grid_rational_interpolation(shift, power, order, ext_ctx):
    values = [mp.log(n+2)+mp.mpf(1)/(n+1) for n in range(14)]
    algo = get("accelerators", "wynn_rho")({
        "order": order, "grid_shift": shift, "grid_power": power})
    source, state = Terms(values, ext_ctx), AlgoState()
    for n in range(3):
        state = algo.step(source, state, ext_ctx)
        relative_close(ext_ctx, state.estimate,
            rho_interpolation(values, n, order, shift, power), digits=50)


@pytest.mark.parametrize("power", [1, 2, 3])
def test_rho_grid_exact_kernel(power, ext_ctx):
    values = [7+mp.mpf(3)/(mp.mpf(n)+mp.mpf("0.5"))**power for n in range(5)]
    algo = get("accelerators", "wynn_rho")({
        "order": 1, "grid_shift": "0.5", "grid_power": power})
    result = algo.step(Terms(values, ext_ctx), AlgoState(), ext_ctx)
    relative_close(ext_ctx, result.estimate, mp.mpf(7))


@pytest.mark.parametrize("power", [True, 0, -1, 1.5])
def test_rho_grid_rejects_invalid_power(power):
    with pytest.raises(ValueError, match="grid_power"):
        get("accelerators", "wynn_rho")({"grid_power": power})


@pytest.mark.parametrize("shift", ["0", "-1", "nan", "inf"])
def test_rho_grid_rejects_invalid_shift(shift, ext_ctx):
    algo = get("accelerators", "wynn_rho")({"grid_shift": shift})
    with pytest.raises(ValueError, match="grid_shift"):
        algo.step(Terms([mp.mpf(n) for n in range(8)], ext_ctx), AlgoState(), ext_ctx)
