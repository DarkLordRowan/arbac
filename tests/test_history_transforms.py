"""Independent ridge/minimum-norm LS and error-basis linear-system oracles."""
from fractions import Fraction as F
import os
import subprocess
import pytest
from arbacc.core import get,AlgoState
from tests.test_additional_transforms import solve,number
from tests.test_special_sources import Values,Terms
from tests.test_extended_series import ext_ctx,relative_close,mp
from tests.test_homeier import inputs,omega

NAMES=['anderson','ford_sidi','aitken_backtracking']


def anderson_oracle(values,n,m,beta,reg):
    if not n:return values[0]
    residual=values[n]-values[n-1]
    base=values[n-1]+beta*residual
    start=n-1-min(m,n-1)
    dx=[values[j+1]-values[j] for j in range(start,n-1)]
    df=[values[j+2]-2*values[j+1]+values[j] for j in range(start,n-1)]
    count=len(df)
    if not count or not any(df):return base
    if reg:
        matrix=[[df[i]*df[j]+(reg if i==j else 0) for j in range(count)] for i in range(count)]
        gamma=solve(matrix,[a*residual for a in df])
    else:
        # KKT system: minimum coefficient norm subject to df*gamma=residual.
        matrix=[[F(i==j) for j in range(count)]+[df[i]] for i in range(count)]
        matrix.append(df+[F(0)])
        gamma=solve(matrix,[F(0)]*count+[residual])[:-1]
    return base-sum((x+beta*f)*g for x,f,g in zip(dx,df,gamma))


@pytest.mark.parametrize('memory',[1,2,5])
@pytest.mark.parametrize('beta',['1','.4'])
@pytest.mark.parametrize('reg',['0','1e-8','.1'])
def test_anderson_independent_least_squares(memory,beta,reg,ext_ctx):
    values,_=inputs()
    algo=get('accelerators','anderson')({'memory':memory,'beta':beta,'regularization':reg})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(12):
        state=algo.step(source,state,ext_ctx)
        expected=anderson_oracle(values,n,memory,F(beta),F(reg))
        relative_close(ext_ctx,state.estimate,number(expected),digits=55)


@pytest.mark.parametrize('memory',[1,2,5])
@pytest.mark.parametrize('amplitude',[-1,1])
@pytest.mark.parametrize('ratio',['.5','-.5'])
def test_anderson_unregularized_affine_fixed_point(memory,amplitude,ratio,ext_ctx):
    values=[mp.mpf(3)+amplitude*mp.mpf(ratio)**i for i in range(15)]
    algo=get('accelerators','anderson')({'memory':memory,'regularization':'0'})
    source=Values(values,ext_ctx);state=AlgoState()
    for n in range(12):
        state=algo.step(source,state,ext_ctx)
        if n>=2:relative_close(ext_ctx,state.estimate,mp.mpf(3),digits=55)


@pytest.mark.parametrize('order',[0,1,2,3,4])
@pytest.mark.parametrize('beta',['1','2.5'])
@pytest.mark.parametrize('remainder',['next','t','u','v','v_shift'])
def test_ford_sidi_against_independent_error_model(order,beta,remainder,ext_ctx):
    values,terms=inputs();b=F(beta)
    algo=get('accelerators','ford_sidi')({'order':order,'beta':beta,'remainder':remainder})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(4):
        matrix=[[F(1)]+[omega(terms,i,remainder,b)/(b+i)**r for r in range(order)] for i in range(n,n+order+1)]
        expected=solve(matrix,values[n:n+order+1])[0]
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(expected),digits=55)


def test_backtracking_finds_previous_window_including_zero(ext_ctx):
    values=[mp.mpf(v) for v in [1,2,4,6,8,10]]
    algo=get('accelerators','aitken_backtracking')({});source=Values(values,ext_ctx)
    for n in range(4):
        result=algo.step(source,AlgoState(iteration=n),ext_ctx)
        # All triples after index zero have zero second difference.
        relative_close(ext_ctx,result.estimate,mp.mpf(0))


@pytest.mark.parametrize('name',NAMES)
def test_new_history_transform_stream_contract_and_rank_zero(name,ext_ctx):
    values,_=inputs();raw=Values([number(v) for v in values],ext_ctx);terms=Terms([number(v) for v in values],ext_ctx)
    algo=get('accelerators',name)({'order':3});s,t=AlgoState(),AlgoState()
    for _ in range(6):
        need=algo.required_input(s)
        s=algo.step(raw,s,ext_ctx);t=algo.step(terms,t,ext_ctx)
        assert len(raw)==len(terms)==need
        relative_close(ext_ctx,s.estimate,t.estimate,digits=55)
    constant=algo.step(Values([mp.mpf(5)]*20,ext_ctx),AlgoState(iteration=4),ext_ctx)
    relative_close(ext_ctx,constant.estimate,mp.mpf(5))
    if name=='anderson':
        for reg in ['0','1e-4']:
            aa=get('accelerators',name)({'regularization':reg,'beta':'.5'})
            result=aa.step(Values([mp.mpf(i) for i in range(15)],ext_ctx),AlgoState(iteration=8),ext_ctx)
            relative_close(ext_ctx,result.estimate,mp.mpf('7.5'))


@pytest.mark.parametrize('params',[
    *[{'memory':v} for v in [0,-1,True,1.5,'2']],
    *[{'beta':v} for v in ['0','-1','1.1','nan','inf']],
    *[{'regularization':v} for v in ['-1','nan','inf']]])
def test_anderson_invalid_params(params,ext_ctx):
    with pytest.raises(ValueError):get('accelerators','anderson')(params).step(Values([mp.mpf(i) for i in range(20)],ext_ctx),AlgoState(),ext_ctx)


def test_seventh_cpp_transforms(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--seventh-algorithm-values'],text=True).splitlines()
    values=[mp.fsum((-mp.mpf(1))**j/(j+1) for j in range(i+1)) for i in range(45)]
    for line in lines:
        name,n,order,remainder,beta,memory,reg,value=line.split('\t')
        params={'order':int(order),'remainder':remainder,'beta':beta,'memory':int(memory),'regularization':reg}
        algo=get('accelerators',name)(params)
        result=algo.step(Values(values,ext_ctx),AlgoState(iteration=int(n)),ext_ctx)
        relative_close(ext_ctx,result.estimate,mp.mpf(value),digits=9)
    assert len(lines)==432


@pytest.mark.parametrize('name',NAMES)
def test_history_transform_runner_and_storage(name,ext_ctx,tmp_path):
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
    assert saved['estimate'] is not None and saved['exact_sum'] is not None
