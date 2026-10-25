"""Oracles use definitions different from the production recurrences."""
from fractions import Fraction as F
import os
import subprocess
import pytest
from arbacc.core import get,AlgoState
from arbacc.accelerators.homeier import HomeierH
from tests.test_special_sources import Values,Terms
from tests.test_additional_transforms import rising,number
from tests.test_extended_series import ext_ctx,relative_close,mp

NAMES=['homeier_f','homeier_h','homeier_pj']
REMAINDERS=['next','t','u','v','v_shift']


def inputs():
    values=[F((-1)**j,j+1)+F(2,j+2) for j in range(32)]
    terms=[values[0]]+[values[i]-values[i-1] for i in range(1,len(values))]
    return values,terms


def omega(terms,index,remainder,beta):
    i=index+int(remainder in ('next','v_shift'))
    a=terms[i]
    if remainder in ('v','v_shift'):return a*terms[i+1]/(terms[i+1]-a)
    return (index+beta)*a if remainder=='u' else a


@pytest.mark.parametrize('grid_power',[1,2])
@pytest.mark.parametrize('beta',['1','2.5'])
@pytest.mark.parametrize('order',[1,2,3,4])
@pytest.mark.parametrize('remainder',REMAINDERS)
def test_f_barycentric_divided_difference_oracle(grid_power,beta,order,remainder,ext_ctx):
    values,terms=inputs();beta=F(beta)
    params={'order':order,'remainder':remainder,'beta':str(beta),'grid_power':grid_power,'grid_scale':'.5','grid_shift':'4'}
    # Backend numeric strings use decimals rather than Fraction's 5/2 notation.
    params['beta']=str(float(beta))
    algo=get('accelerators','homeier_f')(params)
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(3):
        nodes=[F(4)+F(j**grid_power,2) for j in range(n,n+order+1)]
        weights=[]
        for j,x in enumerate(nodes):
            divisor=F(1)
            for i,y in enumerate(nodes):
                if i!=j:divisor*=x-y
            weights.append(rising(x,order-1)/divisor/omega(terms,n+j,remainder,beta))
        reference=sum(w*values[n+j] for j,w in enumerate(weights))/sum(weights)
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(reference),digits=55)


@pytest.mark.parametrize('p',[1,2,3,5])
@pytest.mark.parametrize('beta',['1','2.5'])
@pytest.mark.parametrize('order',[1,2,3,4])
@pytest.mark.parametrize('remainder',REMAINDERS)
def test_pj_original_generalized_difference_oracle(p,beta,order,remainder,ext_ctx):
    values,terms=inputs();b=F(beta)
    algo=get('accelerators','homeier_pj')({'order':order,'beta':beta,'p':p,'remainder':remainder})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(3):
        den=[1/omega(terms,i,remainder,b) for i in range(n,n+order+1)]
        num=[d*values[n+j] for j,d in enumerate(den)]
        # Original J definition (94),(105): Delta / delta, not optimized Psi.
        for k in range(order):
            def update(row):
                return [(row[j+1]-row[j])*rising(F(n+j)+b+(p-1)*k,2) for j in range(len(row)-1)]
            num,den=update(num),update(den)
        reference=num[0]/den[0]
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(reference),digits=55)


@pytest.mark.parametrize('alpha',['.7','1.2'])
@pytest.mark.parametrize('beta',['1','2.5'])
@pytest.mark.parametrize('order',[1,2,3])
@pytest.mark.parametrize('remainder',REMAINDERS)
def test_h_polynomial_annihilator_oracle(alpha,beta,order,remainder,ext_ctx):
    values,terms=inputs();b=F(beta)
    coefficients=[mp.mpf(1)]
    base=[mp.mpf(1),-2*mp.cos(mp.mpf(alpha)),mp.mpf(1)]
    for _ in range(order):
        following=[mp.mpf(0)]*(len(coefficients)+2)
        for i,c in enumerate(coefficients):
            for j,a in enumerate(base):following[i+j]+=c*a
        coefficients=following
    algo=get('accelerators','homeier_h')({'order':order,'beta':beta,'alpha':alpha,'remainder':remainder})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(3):
        weights=[c*mp.power(mp.mpf(n+j)+mp.mpf(beta),order-1)/number(omega(terms,n+j,remainder,b)) for j,c in enumerate(coefficients)]
        expected=mp.fsum(w*number(values[n+j]) for j,w in enumerate(weights))/mp.fsum(weights)
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,expected,digits=55)


@pytest.mark.parametrize('order',[1,2,3])
def test_h_exact_fourier_error_model(order,ext_ctx):
    class KnownRemainder(HomeierH):
        def inverse_remainder(self,source,index,ctx):return ctx.number(1)
    alpha,beta=mp.mpf('.7'),mp.mpf('2.5')
    values=[mp.mpf(3)+mp.fsum(mp.cos(alpha*i)/(i+beta)**r for r in range(order)) for i in range(20)]
    algo=KnownRemainder({'order':order,'alpha':'.7','beta':'2.5'})
    result=algo.step(Values(values,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,result.estimate,mp.mpf(3),digits=55)


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('order',[0,1,2,3])
def test_homeier_input_contract_and_constant(name,order,ext_ctx):
    values,_=inputs();source=Values([number(v) for v in values],ext_ctx)
    terms=Terms([number(v) for v in values],ext_ctx)
    algo=get('accelerators',name)({'order':order});a,b=AlgoState(),AlgoState()
    for _ in range(3):
        need=algo.required_input(a)
        source.extend_to(need-1);terms.extend_to(need-1)
        a=algo.step(source,a,ext_ctx);b=algo.step(terms,b,ext_ctx)
        assert len(source)==len(terms)==need
        relative_close(ext_ctx,a.estimate,b.estimate,digits=55)
    constant=algo.step(Values([mp.mpf(5)]*32,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,constant.estimate,mp.mpf(5))


@pytest.mark.parametrize('name,params',[
    *[(name,{'order':x}) for name in NAMES for x in [-1,True,1.5]],
    *[('homeier_pj',{'p':x}) for x in [0,-1,True,1.5]],
    *[('homeier_f',{'grid_power':x}) for x in [0,-1,True,1.5]],
])
def test_invalid_homeier_integer_params(name,params):
    with pytest.raises(ValueError):get('accelerators',name)(params)


@pytest.mark.parametrize('name,params',[
    *[(name,{'beta':x}) for name in NAMES for x in ['0','-1','nan','inf']],
    *[('homeier_h',{'alpha':x}) for x in ['0','nan','inf']],
    *[('homeier_f',{'grid_shift':x}) for x in ['1','0','nan','inf']],
    *[('homeier_f',{'grid_scale':x}) for x in ['0','-1','nan','inf']],
])
def test_invalid_homeier_real_params(name,params,ext_ctx):
    with pytest.raises(ValueError):get('accelerators',name)(params).step(Values([mp.mpf(i) for i in range(20)],ext_ctx),AlgoState(),ext_ctx)


def test_sixth_cpp_transforms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--sixth-algorithm-values'],text=True).splitlines()
    values=[mp.fsum((-mp.mpf(1))**j/(j+1) for j in range(i+1)) for i in range(45)]
    for line in lines:
        name,n,k,remainder,beta,extra,value=line.split('\t')
        params={'order':int(k),'remainder':remainder,'beta':beta}
        if name=='homeier_pj':params['p']=int(extra)
        if name=='homeier_h':params['alpha']=extra
        if name=='homeier_f':params.update(grid_power=int(extra),grid_scale='.5')
        algo=get('accelerators',name)(params)
        source=Values(values,ext_ctx);state=AlgoState(iteration=int(n))
        result=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,result.estimate,mp.mpf(value),digits=9)
    assert len(lines)==960


@pytest.mark.parametrize('name',NAMES)
def test_homeier_runner_configuration_and_storage(name,ext_ctx,tmp_path):
    import json
    from pathlib import Path
    from arbacc.runner import build_plan,execute_accel
    config={'precision':{'backend':ext_ctx.backend.name,'dps':50},
        'series':[{'type':'ln2','params':{'x':'1'}}],
        'accelerators':[{'type':name,'params':{'order':2},'n_max':12}]}
    plan=build_plan(config)
    assert not plan['errors']
    result=execute_accel(plan['accel'][0],tmp_path)
    assert result['status']=='ok',result
    saved=json.loads((Path(result['accel_dir'])/'result.json').read_text())
    assert saved['accelerator']==name
    assert saved['estimate'] is not None
    assert saved['exact_sum'] is not None


def test_h_default_frequency_retains_requested_precision(ext_ctx):
    from arbacc.core import Context
    ctx=Context(backend=ext_ctx.backend,dps=120)
    high=mp.clone();high.dps=150
    expected=high.sqrt(2)/2
    algo=get('accelerators','homeier_h')({})
    error=ctx.backend.abs_val(ctx.backend.sub(algo.cosine(ctx),ctx.number(high.nstr(expected,145)),ctx.dps),ctx.dps)
    assert ctx.backend.sign(ctx.backend.sub(ctx.number('1e-110'),error,ctx.dps),ctx.dps)>0
