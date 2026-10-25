"""Fourier coefficients obtained by quadrature of independent closed functions.

This verifies normalization, harmonics, signs, and the chosen real branch.
Sources: NIST DLMF 1.8 and 24.8; coefficients are computed by their defining
integrals instead of copying the production coefficient formulae.
"""
from functools import lru_cache
import mpmath
import pytest
from arbacc.core import get
from tests.test_extended_series import ext_ctx, relative_close

mp=mpmath.mp.clone(); mp.dps=90
pi=mp.pi
# function, integration breakpoints, frequency unit, modes for term n.
FOURIER_CASES={
 'abs_sin_x_minus_2_div_pi':(lambda x:mp.sin(x)-2/pi,[0,pi],2,lambda n:[('cos',n+1)]),
 'half_minus_sinx_multi_pi_4':(lambda x:mp.mpf('.5')-pi*mp.sin(x)/4,[0,pi],2,lambda n:[('cos',n+1)]),
 'half_multi_ln_1div2multi1minuscosx':(lambda x:-mp.log(2*mp.sin(x/2)),[0,pi,2*pi],1,lambda n:[('cos',n+1)]),
 'minus_3_div_4_or_x_minus_3_div_4':(lambda x:max(x,0)-mp.mpf('.75'),[-3,0,3],pi/3,
                                  lambda n:[('cos',2*n+1),('sin',n+1)]),
 'minus_x_minus_pi_4_or_minus_pi_4':(lambda x:max(-x,0),[-pi,0,pi],1,
                                   lambda n:[('constant',0)] if n==0 else [('cos',n),('sin',n)]),
 'one_twelfth_3x2_pi2':(lambda x:(3*x*x-pi*pi)/12,[-pi,pi],1,lambda n:[('cos',n+1)]),
 'one_twelfth_x2_pi2':(lambda x:x*(x*x-pi*pi)/12,[-pi,pi],1,lambda n:[('sin',n+1)]),
 'pi_8_cosx_square_minus_1_div_3_cosx':(lambda x:pi*mp.cos(x)**2/8-mp.cos(x)/3,[-pi/2,pi/2],1,lambda n:[('cos',2*n+3)]),
 'pi_minus_3pi_4_and_pi_minus_x_minus_3pi_4':(lambda x:pi/4-max(x,0),[-pi,0,pi],1,
                                         lambda n:[('cos',n+1),('sin',n+1)]),
 'pi_minus_x_2':(lambda x:(pi-x)/2,[0,2*pi],1,lambda n:[('sin',n+1)]),
 'pi_x_minus_x_square_square_minus_three_pi_x_plus_two_pi_square':
      (lambda x:pi*x-x*x if x<=pi else x*x-3*pi*x+2*pi*pi,[0,pi,2*pi],1,lambda n:[('sin',2*n+1)]),
 'ten_minus_x':(lambda x:10-x,[5,15],pi/5,lambda n:[('sin',n+1)]),
 'x':(lambda x:x,[-pi,pi],1,lambda n:[('sin',n+1)]),
}
COTH_NAME='pi_x_multi_e_xpi_plus_e_minusxpi_divided_e_xpi_minus_e_minusxpi'
FOURIER_NAMES=set(FOURIER_CASES)|{COTH_NAME}


@lru_cache(None)
def integrated_coefficient(name,kind,index):
    function,points,frequency,_=FOURIER_CASES[name]
    period=points[-1]-points[0]
    if kind=='constant': return mp.quad(function,points)/period
    trig=mp.cos if kind=='cos' else mp.sin
    return mp.mpf(2)/period*mp.quad(lambda x:function(x)*trig(index*frequency*x),points)


@pytest.mark.parametrize('name',FOURIER_CASES)
def test_fourier_coefficients_from_defining_integrals(name,ext_ctx):
    function,_,frequency,modes=FOURIER_CASES[name]
    x=mp.mpf('7.5' if name=='ten_minus_x' else '.7')
    series=get('series',name)({'x':mp.nstr(x,90)})
    for n in [0,1,3]:
        expected=mp.mpf(0)
        for kind,index in modes(n):
            coefficient=integrated_coefficient(name,kind,index)
            expected+=coefficient*(1 if kind=='constant' else (mp.cos(index*frequency*x) if kind=='cos' else mp.sin(index*frequency*x)))
        relative_close(ext_ctx,series.generate(n,ext_ctx),expected,digits=60)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),function(x),digits=65)


@pytest.mark.parametrize('x',['-0.7','0','0.7'])
def test_coth_partial_fraction_series(x,ext_ctx):
    series=get('series',COTH_NAME)({'x':x}); z=mp.mpf(x)
    for n in [0,1,3,1000000]:
        relative_close(ext_ctx,series.generate(n,ext_ctx),2*z*z/(z*z+(n+1)**2))
    reference=mp.nsum(lambda k:2*z*z/(k*k+z*z),[1,mp.inf])
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),reference)


@pytest.mark.parametrize('name,x',[
    ('pi_minus_x_2','0'),('x','4'),('ten_minus_x','5'),('ten_minus_x','15'),
    ('minus_3_div_4_or_x_minus_3_div_4','3'),
    ('half_multi_ln_1div2multi1minuscosx','0'),
    ('one_twelfth_3x2_pi2','4'),('one_twelfth_x2_pi2','4'),
    ('pi_8_cosx_square_minus_1_div_3_cosx','2'),
])
def test_fourier_branch_boundaries(name,x,ext_ctx):
    with pytest.raises(ValueError): get('series',name)({'x':x}).analytic_sum(ext_ctx)
