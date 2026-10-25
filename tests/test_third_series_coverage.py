"""Coverage and C++ cross-checks for every series in the third porting batch."""
import os
import subprocess
import pytest
from arbacc.core import get
from tests.test_extended_series import ext_ctx, relative_close, mp
from tests.test_rational_catalogue import RATIONAL_NAMES
from tests.test_more_series import SPECIAL_NAMES, MORE_ELEMENTARY_NAMES
from tests.test_fourier_catalogue import FOURIER_NAMES

THIRD_NAMES=RATIONAL_NAMES|SPECIAL_NAMES|MORE_ELEMENTARY_NAMES|FOURIER_NAMES


def params_for(name):
    x='3' if name.startswith('riemann_zeta_func_xmin') else ('7.5' if name=='ten_minus_x' else
       ('1.1' if name in ('x_min_sqrt_x','xsquareplus3_div_xsquareplus2multix_minus_1') else '.2'))
    return {'x':x,'alpha':'.5'}


@pytest.mark.parametrize('name',sorted(THIRD_NAMES))
def test_third_batch_negative_indices(name,ext_ctx):
    with pytest.raises(IndexError): get('series',name)(params_for(name)).generate(-1,ext_ctx)


@pytest.mark.parametrize('name,params',[
    ('bessel_first_kind',{'x':'-.2','alpha':'.5'}),
    ('bessel_first_kind',{'x':'.2','alpha':'-1'}),
    ('incomplete_Gamma_func',{'x':'.2','alpha':'0'}),
    ('incomplete_Gamma_func',{'x':'-.2','alpha':'.5'}),
    ('lambert_W_func',{'x':'.4'}),('k_x',{'x':'1'}),('e_x',{'x':'-1'}),
    ('legendre1',{'x':'1'}),('ln_sinx_minus_ln_x',{'x':'4'}),
    ('ln_cosx',{'x':'2'}),('ln_x_plus_one_x_minus_one_halfed',{'x':'2'}),
    ('riemann_zeta_func_xmin1_div_Riemann_zeta_func_x',{'x':'2'}),
    ('x_min_sqrt_x',{'x':'0'}),('xsquareplus3_div_xsquareplus2multix_minus_1',{'x':'2'}),
    ('cos3xmin1_div_xsquare',{'x':'0'}),('one_div_two_minus_x_multi_three_plus_x',{'x':'2'}),
])
def test_third_batch_domains(name,params,ext_ctx):
    with pytest.raises(ValueError): get('series',name)(params).analytic_sum(ext_ctx)


def test_third_batch_cpp_coefficients(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_CATALOGUE')
    if not binary: pytest.skip('Set SHANKS_CPP_CATALOGUE to the compiled catalogue_probe')
    rows=0
    for name in sorted(THIRD_NAMES):
        params=params_for(name)
        values=subprocess.check_output([binary,name,params['x'],'8'],text=True).split()
        assert len(values)==10,name
        series=get('series',name)(params)
        for n,value in enumerate(values[2:]):
            relative_close(ext_ctx,series.generate(n,ext_ctx),mp.mpf(value),digits=12)
            rows+=1
    assert rows==50*8
