"""Independent oracles for the second porting batch.

Sources: https://dlmf.nist.gov/4.6, /4.24, /6.6, /7.6, /5.2.
Closed forms and finite sum identities are evaluated at 120 digits in a
separate mpmath context. The production implementations use either backend.
"""
from math import comb
import os
import subprocess

import mpmath
import pytest

from arbacc.core import Context, get
from arbacc.precision import get_backend, list_backends

mp = mpmath.mp.clone()
mp.dps = 120

EXTENSION_NAMES = {
    "bin", "m_fact_1mx_mp1_inverse", "four_arctan", "arcsin_x_minus_x",
    "half_asin_two_x", "two_arcsin_square_x_halfed", "cos_sqrt_x",
    "one_div_sqrt2_sin_xdivsqrt2", "mean_sinh_sin", "two_degree_x",
    "ln_1plussqrt1plusxsquare_minus_ln_2", "sqrt_oneminussqrtoneminusx_div_x",
    "erf", "exp_squared_erf", "si_x", "ci_x", "ln2", "two_ln2", "euler_mascheroni",
}

# (closed form, term formula). Formulae are intentionally independent from
# production recurrences, e.g. special-function Taylor differentiation below.
FAST = {
    "four_arctan": (lambda x: 4*mp.atan(x), lambda n,x: 4*(-1)**n*x**(2*n+1)/(2*n+1)),
    "arcsin_x_minus_x": (lambda x: mp.asin(x)-x,
                          lambda n,x: mp.binomial(2*n+2,n+1)*x**(2*n+3)/(4**(n+1)*(2*n+3))),
    "half_asin_two_x": (lambda x: mp.asin(2*x)/2,
                         lambda n,x: mp.binomial(2*n,n)*x**(2*n+1)/(2*n+1)),
    "two_arcsin_square_x_halfed": (lambda x: 2*mp.asin(x/2)**2,
                                  lambda n,x: x**(2*n+2)/((n+1)**2*mp.binomial(2*n+2,n+1))),
    "cos_sqrt_x": (lambda x: mp.cos(mp.sqrt(x)),
                    lambda n,x: (-1)**n*x**n/mp.factorial(2*n)),
    "one_div_sqrt2_sin_xdivsqrt2": (lambda x: mp.sin(x/mp.sqrt(2))/mp.sqrt(2),
                                    lambda n,x: (-1)**n*x**(2*n+1)/(2**(n+1)*mp.factorial(2*n+1))),
    "mean_sinh_sin": (lambda x: (mp.sinh(x)+mp.sin(x))/2,
                       lambda n,x: x**(4*n+1)/mp.factorial(4*n+1)),
    "two_degree_x": (lambda x: mp.power(2,x),
                      lambda n,x: (x*mp.log(2))**n/mp.factorial(n)),
    "ln_1plussqrt1plusxsquare_minus_ln_2": (lambda x: mp.log((1+mp.sqrt(1+x*x))/2),
         lambda n,x: (-1)**n*mp.binomial(2*n+2,n+1)*x**(2*n+2)/(2*(n+1)*4**(n+1))),
    "sqrt_oneminussqrtoneminusx_div_x": (lambda x: 1/mp.sqrt(1+mp.sqrt(1-x)),
         lambda n,x: mp.binomial(4*n,2*n)*x**n/(mp.sqrt(2)*16**n*(2*n+1))),
    "erf": (lambda x: mp.sqrt(mp.pi)*mp.erf(x)/2,
             lambda n,x: (-1)**n*x**(2*n+1)/(mp.factorial(n)*(2*n+1))),
    "exp_squared_erf": (lambda x: mp.exp(x*x)*mp.erf(x),
         lambda n,x: 2*4**n*mp.factorial(n)*x**(2*n+1)/(mp.sqrt(mp.pi)*mp.factorial(2*n+1))),
    "si_x": (mp.si, lambda n,x: (-1)**n*x**(2*n+1)/((2*n+1)*mp.factorial(2*n+1))),
    "ci_x": (mp.ci, lambda n,x: mp.euler if n==0 else (mp.log(x) if n==1 else
         (-1)**(n-1)*x**(2*n-2)/((2*n-2)*mp.factorial(2*n-2)))),
}


@pytest.fixture(params=list_backends())
def ext_ctx(request):
    return Context(backend=get_backend(request.param), dps=80)


def relative_close(ctx, actual, expected, digits=65):
    b, d = ctx.backend, ctx.dps
    reference = ctx.number(mp.nstr(expected, 115))
    scale = b.abs_val(reference, d)
    if b.sign(b.sub(scale,ctx.number(1),d),d)<0:
        scale = ctx.number(1)
    error = b.div(b.abs_diff(actual,reference,d),scale,d)
    assert b.sign(b.sub(ctx.number('1e-'+str(digits)),error,d),d)>0


@pytest.mark.parametrize('name',FAST)
@pytest.mark.parametrize('x',['0','0.1','-0.1'])
def test_extended_fast_terms_and_sums(name,x,ext_ctx):
    if (name=='ci_x' and mp.mpf(x)<=0) or (name=='cos_sqrt_x' and mp.mpf(x)<0):
        with pytest.raises(ValueError):
            get('series',name)({'x':x}).generate(0,ext_ctx)
        return
    series = get('series',name)({'x':x})
    function,term = FAST[name]
    for n in [0,1,2,3,7,19]:
        relative_close(ext_ctx,series.generate(n,ext_ctx),term(n,mp.mpf(x)))
    total = ext_ctx.number(0)
    for n in range(160):
        total = ext_ctx.backend.add(total,series.generate(n,ext_ctx),ext_ctx.dps)
    relative_close(ext_ctx,total,function(mp.mpf(x)))
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),function(mp.mpf(x)))


@pytest.mark.parametrize('alpha',['0','3','-0.5','0.5','2.25'])
@pytest.mark.parametrize('x',['0','0.1','-0.1'])
def test_general_binomial(alpha,x,ext_ctx):
    series = get('series','bin')({'x':x,'alpha':alpha})
    total = ext_ctx.number(0)
    for n in range(160):
        got = series.generate(n,ext_ctx)
        if n<10:
            relative_close(ext_ctx,got,mp.binomial(mp.mpf(alpha),n)*mp.mpf(x)**n)
        total = ext_ctx.backend.add(total,got,ext_ctx.dps)
    expected = mp.power(1+mp.mpf(x),mp.mpf(alpha))
    relative_close(ext_ctx,total,expected)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),expected)


@pytest.mark.parametrize('m',[0,2,13,100])
def test_geometric_derivatives_without_integer_overflow(m,ext_ctx):
    series = get('series','m_fact_1mx_mp1_inverse')({'x':'0.1','m':m})
    for n in [0,1,4,20]:
        relative_close(ext_ctx,series.generate(n,ext_ctx),mp.rf(n+1,m)*mp.mpf('0.1')**n)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.factorial(m)/mp.mpf('0.9')**(m+1))


@pytest.mark.parametrize('name',['ln2','two_ln2','euler_mascheroni'])
@pytest.mark.parametrize('x',['0','0.2','-0.2'])
def test_slow_series_finite_identities(name,x,ext_ctx):
    series = get('series',name)({'x':x})
    count = 128
    total = ext_ctx.number(0)
    for n in range(count):
        total = ext_ctx.backend.add(total,series.generate(n,ext_ctx),ext_ctx.dps)
    scale=mp.mpf(x)
    if name=='ln2':
        expected=scale*(mp.harmonic(count)-mp.harmonic(count//2))
        # Even N alternating harmonic sum is H_N - H_(N/2).
        limit=scale*mp.log(2)
    elif name=='two_ln2':
        expected=scale*(2*(mp.harmonic(2*count)-mp.harmonic(count))+mp.mpf(1)/(2*count+1)-mp.mpf(1)/(2*count+1)**2)
        limit=2*scale*mp.log(2)
    else:
        expected=scale*(mp.harmonic(count)-mp.log(count+1))
        limit=scale*mp.euler
    relative_close(ext_ctx,total,expected)
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),limit)


@pytest.mark.parametrize('name',sorted(EXTENSION_NAMES))
def test_negative_term_indices(name,ext_ctx):
    params={'x':'0.1','alpha':'0.5','m':2}
    with pytest.raises(IndexError):
        get('series',name)(params).generate(-1,ext_ctx)


@pytest.mark.parametrize('name,params',[
    ('bin',{'x':'1','alpha':'0.5'}), ('bin',{'x':'0.1','alpha':'nan'}),
    ('half_asin_two_x',{'x':'0.5'}), ('ci_x',{'x':'0'}),
    ('cos_sqrt_x',{'x':'-0.1'}), ('two_arcsin_square_x_halfed',{'x':'2'}),
    ('erf',{'x':'inf'}), ('exp_squared_erf',{'x':'nan'}),
])
def test_extension_domains(name,params,ext_ctx):
    with pytest.raises(ValueError):
        get('series',name)(params).analytic_sum(ext_ctx)


@pytest.mark.parametrize('m',[-1,1.5,True,'2'])
def test_derivative_order_validation(m):
    with pytest.raises(ValueError):
        get('series','m_fact_1mx_mp1_inverse')({'x':'.1','m':m})


def test_arcsin_square_larger_domain(ext_ctx):
    series=get('series','two_arcsin_square_x_halfed')({'x':'1.5'})
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),2*mp.asin(mp.mpf('.75'))**2)


def test_extension_cpp_terms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:
        pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--extension-terms'],text=True).splitlines()
    for line in lines:
        name,x,n,value=line.split('\t')
        params={'x':x,'alpha':'.5','m':2}
        got=get('series',name)(params).generate(int(n),ext_ctx)
        relative_close(ext_ctx,got,mp.mpf(value),digits=13)
    assert len(lines)==19*8

@pytest.mark.parametrize('dps',[40,100])
@pytest.mark.parametrize('operation',['pi','euler_constant','erf','si','ci'])
def test_special_backend_precision_is_independent(operation,dps,ext_ctx):
    ctx=Context(backend=ext_ctx.backend,dps=dps)
    function=getattr(ctx.backend,operation)
    expected={'pi':lambda:mp.pi,'euler_constant':lambda:mp.euler,
              'erf':lambda:mp.erf(mp.mpf('.2')),
              'si':lambda:mp.si(mp.mpf('.2')),
              'ci':lambda:mp.ci(mp.mpf('.2'))}[operation]()
    argument=ctx.number('.2')
    with mpmath.workdps(15):
        got=function(dps) if operation in ('pi','euler_constant') else function(argument,dps)
    relative_close(ctx,got,expected,digits=dps-8)
