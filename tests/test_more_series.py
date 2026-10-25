"""Special and transformed series: closed functions and independent coefficients."""
from math import gcd
import mpmath
import pytest
from arbacc.core import get
from tests.test_extended_series import ext_ctx, relative_close

mp=mpmath.mp.clone(); mp.dps=110
SPECIAL_NAMES={'bessel_first_kind','incomplete_Gamma_func','e_x','k_x','lambert_W_func',
 'legendre1','riemann_zeta_func_xmin1_div_Riemann_zeta_func_x'}
ELEMENTARY_CASES={
 'cos3xmin1_div_xsquare':(lambda x:mp.cos(3*x-1)/x**2,
                        lambda n,x:(-1)**n*(3*x-1)**(2*n)/(x*x*mp.factorial(2*n))),
 'exp_m_cos_x_sinsin_x':(lambda x:mp.exp(-mp.cos(x))*mp.sin(mp.sin(x)),
                       lambda n,x:(-1)**n*mp.sin((n+1)*x)/mp.factorial(n+1)),
 'ln_1plusx_div_1plusx2':(lambda x:mp.log1p(x)/(1+x*x),
                         lambda n,x:(-1)**n*x**(n+1)/((n+1)*(1+x*x))),
 'ln_cosx':(lambda x:mp.log(mp.cos(x)),lambda n,x:-mp.sin(x)**(2*n+2)/(2*(n+1))),
 'ln_x_plus_one_x_minus_one_halfed':(lambda x:mp.log(mp.cos(x)),lambda n,x:-mp.sin(x)**(2*n+2)/(2*(n+1))),
 'x_min_sqrt_x':(lambda x:x-mp.sqrt(x),lambda n,x:x-1 if n==0 else -mp.binomial(mp.mpf('.5'),n)*(x-1)**n),
 'xsquareplus3_div_xsquareplus2multix_minus_1':(lambda x:(x*x+3)/(x*x+2*x)-1,
                lambda n,x:mp.mpf('.5')*(-1)**n*(3-mp.mpf(7)/3**(n+1))*(x-1)**n),
 'one_div_two_minus_x_multi_three_plus_x':(lambda x:1/((2-x)*(3+x)),
                 lambda n,x:x**n/5*((-1)**n/mp.mpf(3)**(n+1)+mp.mpf(2)**(-n-1))),
}
MORE_ELEMENTARY_NAMES=set(ELEMENTARY_CASES)|{'ln_sinx_minus_ln_x'}


@pytest.mark.parametrize('name',ELEMENTARY_CASES)
def test_more_elementary_series(name,ext_ctx):
    x='1.1' if name in ('x_min_sqrt_x','xsquareplus3_div_xsquareplus2multix_minus_1') else '.2'
    function,term=ELEMENTARY_CASES[name]; numeric=mp.mpf(x)
    series=get('series',name)({'x':x})
    total=ext_ctx.number(0)
    for n in range(160):
        got=series.generate(n,ext_ctx)
        if n in (0,1,2,7,50): relative_close(ext_ctx,got,term(n,numeric))
        total=ext_ctx.backend.add(total,got,ext_ctx.dps)
    relative_close(ext_ctx,total,function(numeric))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),function(numeric))


@pytest.mark.parametrize('name',['bessel_first_kind','incomplete_Gamma_func'])
@pytest.mark.parametrize('alpha',['0.5','1','2.25'])
@pytest.mark.parametrize('x',['0','0.2','2'])
def test_bessel_gamma(name,alpha,x,ext_ctx):
    series=get('series',name)({'x':x,'alpha':alpha})
    a,z=mp.mpf(alpha),mp.mpf(x)
    total=ext_ctx.number(0)
    for n in range(160):
        got=series.generate(n,ext_ctx)
        if n in (0,1,2,9):
            expected=((-1)**n*(z/2)**(2*n+a)/(mp.factorial(n)*mp.gamma(n+a+1)) if name=='bessel_first_kind'
                      else (-1)**n*z**(n+a)/(mp.factorial(n)*(n+a)))
            relative_close(ext_ctx,got,expected)
        total=ext_ctx.backend.add(total,got,ext_ctx.dps)
    expected=mp.besselj(a,z) if name=='bessel_first_kind' else mp.gammainc(a,0,z)
    relative_close(ext_ctx,total,expected)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),expected)


@pytest.mark.parametrize('name',['k_x','e_x'])
@pytest.mark.parametrize('x',['0','0.2','-0.2'])
def test_elliptic_modulus_convention(name,x,ext_ctx):
    series=get('series',name)({'x':x}); z=mp.mpf(x)
    total=ext_ctx.number(0)
    for n in range(160):
        got=series.generate(n,ext_ctx)
        if n<5:
            coefficient=mp.rf(mp.mpf('.5'),n)*(mp.rf(mp.mpf('.5') if name=='k_x' else mp.mpf('-.5'),n))/mp.factorial(n)**2
            relative_close(ext_ctx,got,mp.pi/2*coefficient*z**(2*n))
        total=ext_ctx.backend.add(total,got,ext_ctx.dps)
    expected=mp.ellipk(z*z) if name=='k_x' else mp.ellipe(z*z)
    relative_close(ext_ctx,total,expected)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),expected)


@pytest.mark.parametrize('x',['0','0.1','-0.1'])
def test_lambert_series(x,ext_ctx):
    series=get('series','lambert_W_func')({'x':x}); z=mp.mpf(x)
    total=ext_ctx.number(0)
    for n in range(180):
        got=series.generate(n,ext_ctx)
        if n<5: relative_close(ext_ctx,got,(-n-1)**n*z**(n+1)/mp.factorial(n+1))
        total=ext_ctx.backend.add(total,got,ext_ctx.dps)
    relative_close(ext_ctx,total,mp.lambertw(z))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.lambertw(z))


@pytest.mark.parametrize('s',['2.5','3','6'])
def test_totient_dirichlet(s,ext_ctx):
    series=get('series','riemann_zeta_func_xmin1_div_Riemann_zeta_func_x')({'x':s})
    for n in [0,1,2,9,39,99,999]:
        k=n+1
        phi=sum(gcd(j,k)==1 for j in range(1,k+1))
        relative_close(ext_ctx,series.generate(n,ext_ctx),phi/mp.power(k,mp.mpf(s)))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.zeta(mp.mpf(s)-1)/mp.zeta(mp.mpf(s)))


@pytest.mark.parametrize('x',['0.2','-0.2'])
def test_legendre_exact_coefficients_and_tail(x,ext_ctx):
    series=get('series','legendre1')({'x':x}); z=mp.mpf(x)
    for n in [0,1,2,3,10]:
        # Explicit finite polynomial, not the backend Legendre implementation.
        polynomial=mp.fsum((-1)**j*mp.binomial(n,j)*mp.binomial(2*n-2*j,n)*z**(n-2*j)
                           for j in range(n//2+1))/2**n
        relative_close(ext_ctx,series.generate(n,ext_ctx),-polynomial/((2*n-1)*(2*n+3)))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.sqrt((1-z)/8))
    # |P_n(x)|<=1 on [-1,1], so the omitted rational tail is bounded explicitly.
    total=ext_ctx.number(0); count=200
    for n in range(count): total=ext_ctx.backend.add(total,series.generate(n,ext_ctx),ext_ctx.dps)
    actual=mp.mpf(ext_ctx.backend.to_str(total,ext_ctx.dps))
    bound=mp.mpf(1)/4*(mp.mpf(1)/(2*count-1)+mp.mpf(1)/(2*count+1))
    assert abs(actual-mp.sqrt((1-z)/8))<bound


@pytest.mark.parametrize('x',['0','0.2','-0.2'])
def test_log_sinc_product(x,ext_ctx):
    series=get('series','ln_sinx_minus_ln_x')({'x':x}); z=mp.mpf(x)
    for n in [0,1,4,20]:
        relative_close(ext_ctx,series.generate(n,ext_ctx),mp.log1p(-(z/(mp.pi*(n+1)))**2))
    expected=mp.log(mp.sin(z)/z) if z else mp.mpf(0)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),expected)
    total=mp.fsum(mp.log1p(-(z/(mp.pi*k))**2) for k in range(1,201))
    # |log(1-u)| <= u/(1-u), followed by sum_{k>N} 1/k^2 <= 1/N.
    bound=z*z/(mp.pi**2*200)/(1-(z/(mp.pi*201))**2)
    assert abs(total-expected)<=bound
