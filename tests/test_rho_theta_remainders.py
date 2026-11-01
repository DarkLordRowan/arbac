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


@lru_cache(None)
def parameterized_rho_exact(values, column, index, mode, gamma, rho):
    if column == -1:
        return Fraction(0)
    if column == 0:
        return values[index]
    numerator = column-1-gamma if mode == "generalized" else -gamma+Fraction(column, 2)/rho+column%2
    return parameterized_rho_exact(values, column-2, index+1, mode, gamma, rho)+numerator/(
        parameterized_rho_exact(values, column-1, index+1, mode, gamma, rho)-
        parameterized_rho_exact(values, column-1, index, mode, gamma, rho))


@pytest.mark.parametrize("mode", ["generalized", "gamma_rho"])
@pytest.mark.parametrize("gamma", ["-0.5", "-1", "-2.5"])
@pytest.mark.parametrize("rho", ["0.5", "2"])
@pytest.mark.parametrize("order", [0, 1, 2, 3])
def test_parameterized_rho_exact_fraction_oracle(mode, gamma, rho, order, ext_ctx):
    values = tuple(Fraction(1, n+1)+Fraction((-1)**n, (n+2)**2) for n in range(13))
    decimal = [mp.mpf(v.numerator)/v.denominator for v in values]
    algo = get("accelerators", "wynn_rho")({"order": order, "numerator": mode, "gamma": gamma, "rho": rho})
    state, source = AlgoState(), Terms(decimal, ext_ctx)
    for n in range(3):
        state = algo.step(source, state, ext_ctx)
        expected = parameterized_rho_exact(values, 2*order, n, mode, Fraction(gamma), Fraction(rho))
        relative_close(ext_ctx, state.estimate, mp.mpf(expected.numerator)/expected.denominator, digits=50)


@pytest.mark.parametrize("gamma", ["-0.5", "-1", "-2.5"])
def test_osada_first_even_column_explicit_formula(gamma, ext_ctx):
    # Independent closed expression, Chang et al. (2019), Eq. (2.14).
    alpha = -mp.mpf(gamma)
    s = [7+mp.power(n+2, -alpha) for n in range(3)]
    expected = s[1]-(alpha+1)/alpha*(s[1]-s[0])*(s[2]-s[1])/(s[2]-2*s[1]+s[0])
    algo = get("accelerators", "wynn_rho")({"order": 1, "numerator": "generalized", "gamma": gamma})
    relative_close(ext_ctx, algo.step(Terms(s, ext_ctx), AlgoState(), ext_ctx).estimate, expected)


@pytest.mark.parametrize("params", [
    {"numerator": "missing"}, {"numerator": "generalized", "grid_power": 2},
    {"numerator": "gamma_rho", "grid_shift": "2"}])
def test_rho_rejects_ambiguous_modes(params):
    with pytest.raises(ValueError):
        get("accelerators", "wynn_rho")(params)


@pytest.mark.parametrize("params", [
    {"numerator": "generalized", "gamma": "nan"},
    {"numerator": "generalized", "gamma": "inf"},
    {"numerator": "gamma_rho", "rho": "0"},
    {"numerator": "gamma_rho", "rho": "nan"},
    {"numerator": "gamma_rho", "rho": "inf"}])
def test_rho_rejects_nonfinite_parameters(params, ext_ctx):
    with pytest.raises(ValueError):
        get("accelerators", "wynn_rho")(params).step(Terms([mp.mpf(n) for n in range(8)], ext_ctx), AlgoState(), ext_ctx)


def test_cpp_parameterized_rho_values(ext_ctx):
    executable = os.environ.get("SHANKS_CPP_REGRESSIONS")
    if not executable:
        pytest.skip("set SHANKS_CPP_REGRESSIONS")
    rows = subprocess.check_output([executable, "--rho-variant-values"], text=True).splitlines()
    assert len(rows) == 144
    for row in rows:
        mode, gamma, rho, order, n, value = row.split()
        values = [mp.mpf(1)/(j+1)+mp.mpf((-1)**j)/(j+2)**2 for j in range(14)]
        algo = get("accelerators", "wynn_rho")({"order": int(order), "numerator": mode, "gamma": gamma, "rho": rho})
        state = AlgoState()
        source = Terms(values, ext_ctx)
        for _ in range(int(n)+1):
            state = algo.step(source, state, ext_ctx)
        relative_close(ext_ctx, state.estimate, mp.mpf(value), digits=7)



@pytest.mark.parametrize("alpha", ["0.5", "1.5", "2.5"])
@pytest.mark.parametrize("order", [1, 2])
def test_osada_accelerates_nonintegral_power_model(alpha, order, ext_ctx):
    # Chang et al. (2019), Eq. (2.15): error O(n**(-alpha-2*k)).
    # This tests a consequence of the theorem, independent of table arithmetic.
    b, d = ext_ctx.backend, ext_ctx.dps
    alpha = mp.mpf(alpha)
    ratios = []
    for start in (8, 32, 128):
        values = [7+mp.power(j+2, -alpha) for j in range(start+2*order+1)]
        algo = get("accelerators", "wynn_rho")({"order": order, "numerator": "generalized", "gamma": str(-alpha)})
        state = AlgoState(iteration=start)
        result = algo.step(Terms(values, ext_ctx), state, ext_ctx)
        raw_error = ext_ctx.number(mp.nstr(values[start]-7, 95))
        error = b.abs_val(b.sub(result.estimate, ext_ctx.number(7), d), d)
        ratios.append(b.div(error, raw_error, d))
    for left, right in zip(ratios, ratios[1:]):
        assert b.sign(b.sub(left, b.mul(ext_ctx.number(4), right, d), d), d) > 0
