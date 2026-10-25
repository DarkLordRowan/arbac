"""Independent mathematical oracles, not just successful execution.

References: https://dlmf.nist.gov/3.9, /4.6, /4.19, /4.24, /4.38.
Run cross-language comparison with SHANKS_CPP_REGRESSIONS=/path/to/executable.
"""
import os
import subprocess
from fractions import Fraction

import mpmath
import pytest

from arbacc.core import Context, get, list_registered
from arbacc.core.accelerator import AlgoState
from arbacc.precision import get_backend, list_backends
from tests.test_extended_series import EXTENSION_NAMES
from tests.test_third_series_coverage import THIRD_NAMES
from tests.test_special_sources import FOURTH_NAMES

mp = mpmath.mp.clone()
mp.dps = 100

# Each entry supplies an independent closed form and exact rational coefficients.
CASES = {
    "exp": (mp.exp, [1, 1, Fraction(1,2), Fraction(1,6)], [0,1,2,3]),
    "sin": (mp.sin, [1, Fraction(-1,6), Fraction(1,120)], [1,3,5]),
    "cos": (mp.cos, [1, Fraction(-1,2), Fraction(1,24)], [0,2,4]),
    "sinh": (mp.sinh, [1, Fraction(1,6), Fraction(1,120)], [1,3,5]),
    "cosh": (mp.cosh, [1, Fraction(1,2), Fraction(1,24)], [0,2,4]),
    "ln1mx": (lambda x: -mp.log1p(-x), [1, Fraction(1,2), Fraction(1,3)], [1,2,3]),
    "log1p": (mp.log1p, [1, Fraction(-1,2), Fraction(1,3)], [1,2,3]),
    "arctan_x": (mp.atan, [1, Fraction(-1,3), Fraction(1,5)], [1,3,5]),
    "arctanh_x": (mp.atanh, [1, Fraction(1,3), Fraction(1,5)], [1,3,5]),
    "arcsin_x": (mp.asin, [1, Fraction(1,6), Fraction(3,40)], [1,3,5]),
    "arcsinh_x": (mp.asinh, [1, Fraction(-1,6), Fraction(3,40)], [1,3,5]),
    "sqrt_1plusx": (lambda x: mp.sqrt(1+x), [1, Fraction(1,2), Fraction(-1,8)], [0,1,2]),
    "inverse_sqrt_1m4x": (lambda x: 1/mp.sqrt(1-4*x), [1,2,6,20], [0,1,2,3]),
    "one_minus_sqrt_1minus4x_div_2x": (lambda x: 2/(1+mp.sqrt(1-4*x)), [1,1,2,5], [0,1,2,3]),
    "x_div_1minx": (lambda x: x/mp.sqrt(1-x), [1,Fraction(1,2),Fraction(3,8)], [1,2,3]),
    "x_div_1minx2": (lambda x: x/mp.sqrt(1-x*x), [1,Fraction(1,2),Fraction(3,8)], [1,3,5]),
    "x_1mx_squared": (lambda x: x/(1-x)**2, [1,2,3], [1,2,3]),
    "geometric": (lambda x: 1/(1-x), [1,1,1], [0,1,2]),
}


# Independent oracles under power substitution, preserving term indexing.
for new, base, power, sign in [
    ("sin_x2","sin",2,1), ("cos_x2","cos",2,1),
    ("sinh_x2","sinh",2,1), ("arcsin_x2","arcsin_x",2,1),
    ("arctanh_x2","arctanh_x",2,1), ("arctan_x2","arctan_x",2,1),
    ("arctan_x3","arctan_x",3,1), ("ln1px4","log1p",4,1),
    ("ln_1_plus_x3","log1p",3,1), ("ln1_m_x2","ln1mx",2,-1),
]:
    function, coefficients, exponents = CASES[base]
    CASES[new]=(lambda x,f=function,p=power,s=sign: s*f(x**p),
                [sign*c for c in coefficients],[power*e for e in exponents])
CASES["sqrt_1plusx_min_1_min_x_div_2"]=(
    lambda x: mp.sqrt(1+x)-1-x/2,
    [Fraction(-1,8),Fraction(1,16),Fraction(-5,128)], [2,3,4])


@pytest.fixture(params=list_backends())
def math_ctx(request):
    return Context(backend=get_backend(request.param), dps=70)


def close(ctx, actual, expected, digits=60):
    ref = ctx.number(mp.nstr(expected, 95))
    assert ctx.backend.digits_of(actual, ref, ctx.dps) >= digits


@pytest.mark.parametrize("name", CASES)
@pytest.mark.parametrize("x", ["0", "0.1", "-0.1"])
def test_series_coefficients_and_sum(name, x, math_ctx):
    ctx, b = math_ctx, math_ctx.backend
    function, coefficients, exponents = CASES[name]
    series = get("series", name)({"q" if name == "geometric" else "x": x})
    stream = series.build_stream(ctx)
    for i, (coefficient, exponent) in enumerate(zip(coefficients, exponents)):
        rational = Fraction(coefficient)
        expected = mp.mpf(rational.numerator) / rational.denominator * mp.mpf(x)**exponent
        close(ctx, stream.get(i), expected)
    total = ctx.number(0)
    for i in range(160):
        total = b.add(total, stream.get(i), ctx.dps)
    close(ctx, total, function(mp.mpf(x)), digits=55)
    close(ctx, series.analytic_sum(ctx), function(mp.mpf(x)))


@pytest.mark.parametrize("s", ["2", "3", "2.5"])
def test_zeta_independent(s, math_ctx):
    series = get("series", "zeta")({"s": s})
    for n in [0,1,7,100]:
        close(math_ctx, series.generate(n, math_ctx), mp.power(n+1, -mp.mpf(s)))
    close(math_ctx, series.analytic_sum(math_ctx), mp.zeta(mp.mpf(s)))


@pytest.mark.parametrize("name,param,value", [
    ("geometric","q","1"), ("geometric","q","-1"), ("geometric","q","2"),
    ("zeta","s","1"), ("zeta","s","0.5"), ("zeta","s","nan"),
    ("ln1mx","x","1"), ("arctanh_x","x","-1"),
    ("inverse_sqrt_1m4x","x","0.25"), ("exp","x","inf"),
])
def test_sum_domain(name, param, value, math_ctx):
    with pytest.raises(ValueError):
        get("series", name)({param: value}).analytic_sum(math_ctx)


class Terms:
    """A finite stream that records accesses and rejects undeclared input."""
    def __init__(self, partials, ctx):
        self.values = [ctx.number(mp.nstr(partials[0],95))]
        self.values += [ctx.number(mp.nstr(partials[i]-partials[i-1],95)) for i in range(1,len(partials))]
        self.accesses = []

    def get(self, n):
        self.accesses.append(n)
        return self.values[n]


def step(name, partials, ctx, params=None):
    algo, state = get("accelerators", name)(params or {}), AlgoState()
    source = Terms(partials, ctx)
    state = algo.step(source, state, ctx)
    assert max(source.accesses) < algo.required_input(AlgoState())
    return state.estimate


@pytest.mark.parametrize("name", ["aitken_delta2", "wynn_epsilon", "shanks", "levin", "weniger"])
def test_exact_geometric_kernel(name, math_ctx):
    # Aitken and Shanks annihilate a geometric error in one transform.
    # Use first order for determinant to avoid rank deficiency of higher orders.
    ctx = math_ctx
    partials = [mp.mpf(3)+mp.power(mp.mpf("0.5"),n) for n in range(15)]
    if name == "wynn_epsilon":
        algo = get("accelerators",name)({})
        source = Terms(partials, ctx)
        state = algo.step(source, AlgoState(), ctx)
        state = algo.step(source, state, ctx)
        assert len(state.extra["partials"]) == 3
        close(ctx, state.estimate, mp.mpf(3))
    else:
        close(ctx, step(name, partials, ctx, {"order":1}), mp.mpf(3))


def test_wynn_matches_independent_determinants(math_ctx):
    ctx, state = math_ctx, AlgoState()
    partials = [mp.fsum([(-mp.mpf(1))**j / (j+1)**2 for j in range(n+1)]) for n in range(11)]
    source, algo = Terms(partials, ctx), get("accelerators","wynn_epsilon")({})
    for order in range(6):
        declared = algo.required_input(state)
        state = algo.step(source,state,ctx)
        assert len(state.extra["partials"]) == declared
        assert max(source.accesses) == declared-1
        if order == 0:
            expected = partials[0]
        else:
            upper = mp.matrix([[partials[r+c] for c in range(order+1)] for r in range(order+1)])
            lower = mp.matrix([[partials[r+c+2]-2*partials[r+c+1]+partials[r+c]
                               for c in range(order)] for r in range(order)])
            expected = mp.det(upper)/mp.det(lower)
        close(ctx,state.estimate,expected,digits=45)


@pytest.mark.parametrize("name", ["aitken_delta2","wynn_epsilon","shanks","levin","weniger","richardson"])
def test_constant_sequence_no_crash(name, math_ctx):
    algo, state = get("accelerators",name)({}), AlgoState()
    source = Terms([mp.mpf(5)]*30, math_ctx)
    for _ in range(6):
        state = algo.step(source,state,math_ctx)
        close(math_ctx,state.estimate,mp.mpf(5))


def test_shanks_two_exponentials(math_ctx):
    partials = [mp.mpf(3)+mp.power(mp.mpf("0.5"),n)+2*mp.power(mp.mpf("-0.25"),n) for n in range(8)]
    close(math_ctx,step("shanks",partials,math_ctx,{"order":2}),mp.mpf(3))


def test_richardson_even_and_odd(math_ctx):
    partials = [7+3*mp.power(mp.mpf("0.25"),n) for n in range(8)]
    algo, source, state = get("accelerators","richardson")({}), Terms(partials,math_ctx), AlgoState()
    for n in range(7):
        state = algo.step(source,state,math_ctx)
        close(math_ctx,state.estimate,partials[0] if n==0 else mp.mpf(7))


@pytest.mark.parametrize("name", ["levin", "weniger"])
def test_remainder_transforms_independent_formula(name, math_ctx):
    # Compare with mpmath's independent, published implementation.
    ctx = math_ctx
    terms = [(-mp.mpf(1))**n/(n+1) for n in range(12)]
    partials = [mp.fsum(terms[:n+1]) for n in range(len(terms))]
    # Direct finite differences give an independent oracle for the next-term form.
    k=4
    weights=[]
    for j in range(k+1):
        factor=mp.power(j+1,k-1) if name=="levin" else mp.rf(j+1,k-1)
        weights.append((-1)**j*mp.binomial(k,j)*factor/terms[j+1])
    expected=mp.fsum(weights[j]*partials[j] for j in range(k+1))/mp.fsum(weights)
    got=step(name,partials,ctx,{"order":k})
    close(ctx,got,expected)
    assert abs(mp.mpf(ctx.backend.to_str(got,ctx.dps))-mp.log(2)) < abs(partials[k]-mp.log(2))


@pytest.mark.parametrize("name", ["shanks","levin","weniger"])
@pytest.mark.parametrize("order", [-1, 1.5, True, "2"])
def test_invalid_orders(name,order):
    with pytest.raises(ValueError):
        get("accelerators",name)({"order":order})


def test_all_synthetic_series_have_oracles():
    assert set(list_registered("series")["series"]) - {"from_file","zeta"} - EXTENSION_NAMES - THIRD_NAMES - FOURTH_NAMES == set(CASES)


def test_cpp_terms_against_python(ctx):
    binary = os.environ.get("SHANKS_CPP_REGRESSIONS")
    if not binary:
        pytest.skip("Set SHANKS_CPP_REGRESSIONS to compiled mathematical_regressions")
    output = subprocess.check_output([binary,"--terms"],text=True)
    rows=0
    for line in output.splitlines():
        name,x,n,value = line.split("\t")
        series = get("series",name)({"q" if name=="geometric" else "x":x})
        got=mp.mpf(ctx.backend.to_str(series.generate(int(n),ctx),ctx.dps))
        assert abs(got-mp.mpf(value)) < mp.mpf("1e-14"), (name,n)
        rows+=1
    assert rows == 28*8


@pytest.mark.parametrize("name", ["shanks","levin","weniger"])
def test_order_zero_consumes_one_term(name,math_ctx):
    algo=get("accelerators",name)({"order":0})
    assert algo.required_input(AlgoState())==1
    close(math_ctx,step(name,[mp.mpf(2)],math_ctx,{"order":0}),mp.mpf(2))


def test_all_accelerators_have_oracles():
    assert set(list_registered("accelerators")["accelerators"]) == {
        "aitken_delta2","wynn_epsilon","shanks","richardson","levin","weniger",
        "drummond","wynn_rho","brezinski_theta","overholt","lubkin_w","iterated_aitken","wynn_epsilon_fixed","levin_sidi_m","homeier_f","homeier_h","homeier_pj","anderson","ford_sidi","aitken_backtracking","chang_wynn","homeier_j","wynn_epsilon_adaptive"}
