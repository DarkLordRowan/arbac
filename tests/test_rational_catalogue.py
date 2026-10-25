"""Independent rational sums and high-index regressions (third batch)."""
from functools import lru_cache
from fractions import Fraction
import mpmath
import pytest
from arbacc.core import get
from tests.test_extended_series import ext_ctx, relative_close

mp=mpmath.mp.clone(); mp.dps=100

# Independent coefficient and closed-form oracles. k starts at 1.
RATIONAL_CASES={
 'eighth_pi_m_one_third':(lambda k:(-1)**(k-1)/((2*k-1)*(2*k+1)*(2*k+3)),mp.pi/8-mp.mpf(1)/3),
 'five_pi_twelve':(lambda k:5*(-1)**(k-1)/(3*(2*k-1)),5*mp.pi/12),
 'four_ln2_m_3':(lambda k:(-1)**k/(k*k*(k+1)**2),4*mp.log(2)-3),
 'ln13_min_ln7_div_7':(lambda k:(-1)**(k-1)*6**k/(7**(k+1)*k),mp.log(mp.mpf(13)/7)/7),
 'minus_one_quarter':(lambda k:(-1)**k/(k*(k+2)),-mp.mpf(1)/4),
 'minus_three_plus_ln3_three_devided_two_plus_two_ln2':(lambda k:1/(k*(36*k*k-1)),mp.log(4)+mp.mpf('1.5')*mp.log(3)-3),
 'one':(lambda k:1/(k*(k+1)),mp.mpf(1)),
 'one_third_pi_squared_m_nine':(lambda k:1/(k*k*(k+1)**2),(mp.pi**2-9)/3),
 'one_twelfth':(lambda k:1/((2*k-1)*(2*k+1)*(2*k+3)),mp.mpf(1)/12),
 'pi_3':(lambda k:1/(k*(2*k-1)*(4*k-3)),mp.pi/3),
 'pi_4':(lambda k:(-1)**(k-1)/(2*k-1),mp.pi/4),
 'pi_cubed_32':(lambda k:(-1)**(k-1)/(2*k-1)**3,mp.pi**3/32),
 'pi_four_minus_ln2_halfed':(lambda k:(-1)**(k-1)/((2*k-1)*(2*k)),mp.pi/4-mp.log(2)/2),
 'pi_six_min_half':(lambda k:(-1)**(k-1)/((6*k-1)*(6*k+1)),mp.pi/6-mp.mpf(1)/2),
 'pi_squared_6_minus_one':(lambda k:1/(k*k*(k+1)),mp.pi**2/6-1),
 'pi_squared_twelve':(lambda k:(-1)**(k-1)/(k*k),mp.pi**2/12),
 'three_minus_pi':(lambda k:(-1)**k/(k*(k+1)*(2*k+1)),3-mp.pi),
 'x_two':(lambda k:1/((2*k-1)*(2*k+1)),mp.mpf(1)/2),
 'x_two_throught_squares':(lambda k:(2*k*k-1)/(4*k**4+1),mp.mpf(1)/2),
}
RATIONAL_NAMES=set(RATIONAL_CASES)|{'pi'}


@lru_cache(None)
def independent_infinite_sum(name):
    coefficient,_=RATIONAL_CASES[name]
    # mpmath rational extrapolation is independent from the production closed form.
    return mp.nsum(coefficient,[1,mp.inf])


@pytest.mark.parametrize('name',RATIONAL_CASES)
@pytest.mark.parametrize('x',['0','0.2','-0.3'])
def test_scaled_rational_series(name,x,ext_ctx):
    term,limit=RATIONAL_CASES[name]
    assert abs(independent_infinite_sum(name)-limit)<mp.mpf('1e-80')
    series=get('series',name)({'x':x})
    for n in [0,1,7,150]:
        relative_close(ext_ctx,series.generate(n,ext_ctx),mp.mpf(x)*term(mp.mpf(n+1)))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.mpf(x)*limit)
    if name!='ln13_min_ln7_div_7':
        n=1000000
        relative_close(ext_ctx,series.generate(n,ext_ctx),mp.mpf(x)*term(mp.mpf(n+1)))


@pytest.mark.parametrize('x',['0','0.2','-0.3'])
def test_fast_pi_series(x,ext_ctx):
    series=get('series','pi')({'x':x})
    total=ext_ctx.number(0)
    for n in range(180):
        got=series.generate(n,ext_ctx)
        if n<8:
            relative_close(ext_ctx,got,mp.mpf(x)*mp.sqrt(12)*(-1)**n/(3**n*(2*n+1)))
        total=ext_ctx.backend.add(total,got,ext_ctx.dps)
    relative_close(ext_ctx,total,mp.mpf(x)*mp.pi)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.mpf(x)*mp.pi)


@pytest.mark.parametrize('name',['one','x_two','x_two_throught_squares'])
def test_telescoping_finite_rational_sums(name,ext_ctx):
    series=get('series',name)({'x':'1'})
    count=100
    total=ext_ctx.number(0)
    for n in range(count): total=ext_ctx.backend.add(total,series.generate(n,ext_ctx),ext_ctx.dps)
    if name=='one': expected=mp.mpf(count)/(count+1)
    elif name=='x_two': expected=(1-mp.mpf(1)/(2*count+1))/2
    else: expected=(1-mp.mpf(2*count+1)/(2*count*count+2*count+1))/2
    relative_close(ext_ctx,total,expected)

@pytest.mark.parametrize('name,params,n',[
    ('ln13_min_ln7_div_7',{'x':'1'},10000),
    ('inverse_sqrt_1m4x',{'x':'.2499'},10000),
])
def test_large_exact_integer_coefficients_do_not_use_decimal_strings(name,params,n,ext_ctx):
    series=get('series',name)(params)
    got=series.generate(n,ext_ctx)
    if name=='ln13_min_ln7_div_7':
        expected=(-1)**n*mp.power(mp.mpf(6)/7,n+1)/(7*(n+1))
    else:
        expected=mp.binomial(2*n,n)*mp.mpf('.2499')**n
    relative_close(ext_ctx,got,expected,digits=60)
