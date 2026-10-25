"""Final families: rational definitions, independent special cases and GSL QELG."""
from fractions import Fraction as F
from functools import lru_cache
import os
import subprocess
import pytest
from arbacc.core import get,AlgoState
from arbacc.accelerators.final_catalogue import condensed_epsilon
from tests.test_special_sources import Values,Terms
from tests.test_additional_transforms import number
from tests.test_extended_series import ext_ctx,relative_close,mp
from tests.test_homeier import inputs,omega

NAMES=['chang_wynn','homeier_j','wynn_epsilon_adaptive']
NATIVE_EPS='2.220446049250313080847263336181640625e-16'


def generic_values(count=80):
    return [F((-1)**i,i+1)+F(2,i*i+3)+F(1,i**3+5) for i in range(count)]


def chang_reference(values,k,n):
    @lru_cache(None)
    def cell(column,index):
        if column==0:return values[index]
        if column==1:return 1/(values[index+1]-values[index])
        if column==2:
            a,b,c=[values[index+j+1]-values[index+j] for j in range(3)]
            # Initial T2 via independent first-order v transform (3.18).
            w0,w1=(b-a)/(a*b),(c-b)/(b*c)
            return (w0*values[index+1]-w1*values[index+2])/(w0-w1)
        level=column-1
        # F1 from the defining four-cell identity, not the explicit products.
        factor=(cell(2,index)-cell(0,index+1))*(cell(1,index+1)-cell(1,index))
        return cell(column-2,index+1)+(1-level+level*factor)/(cell(column-1,index+1)-cell(column-1,index))
    return cell(2*k,n)


@pytest.mark.parametrize('order',[0,1,2,3,4])
def test_chang_exact_rational_recursion(order,ext_ctx):
    values=generic_values();algo=get('accelerators','chang_wynn')({'order':order})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(4):
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(chang_reference(values,order,n)),digits=50)


@pytest.mark.parametrize('shift',[0,1,2,4])
@pytest.mark.parametrize('order',[0,1,2,3,4])
@pytest.mark.parametrize('remainder',['next','t','u','v','v_shift'])
def test_j_matches_independent_optimized_pj(shift,order,remainder,ext_ctx):
    values,_=inputs();source=Values([number(v) for v in values],ext_ctx)
    params={'order':order,'beta':'2.5','remainder':remainder,'safeguard':'0'}
    general=get('accelerators','homeier_j')({**params,'delta_mode':'pochhammer','delta_shift':str(shift)})
    optimized=get('accelerators','homeier_pj')({**params,'p':shift+1})
    a,b=AlgoState(),AlgoState()
    for n in range(3):
        a=general.step(source,a,ext_ctx);b=optimized.step(source,b,ext_ctx)
        relative_close(ext_ctx,a.estimate,b.estimate,digits=55)


@pytest.mark.parametrize('mode',['constant','power'])
@pytest.mark.parametrize('order',[0,1,2,3,4])
@pytest.mark.parametrize('remainder',['next','t','u','v','v_shift'])
def test_j_independent_recursive_linear_functional(mode,order,remainder,ext_ctx):
    values,terms=inputs();beta=F(5,2)
    @lru_cache(None)
    def weights(level,index):
        if level==0:return {index:F(1)}
        shift=F(index)+beta+2*(level-1)
        divisor=F(1) if mode=='constant' else 1/shift**3
        result={}
        for sign,child in [(-1,weights(level-1,index)),(1,weights(level-1,index+1))]:
            for i,w in child.items():result[i]=result.get(i,F(0))+sign*w/divisor
        return result
    algo=get('accelerators','homeier_j')({'order':order,'beta':'2.5','remainder':remainder,'delta_mode':mode,'delta_shift':'2','delta_power':3,'safeguard':'0'})
    source=Values([number(v) for v in values],ext_ctx);state=AlgoState()
    for n in range(3):
        factors={i:w/omega(terms,i,remainder,beta) for i,w in weights(order,n).items()}
        expected=sum(w*values[i] for i,w in factors.items())/sum(factors.values())
        state=algo.step(source,state,ext_ctx)
        relative_close(ext_ctx,state.estimate,number(expected),digits=55)


@pytest.mark.parametrize('name',NAMES)
@pytest.mark.parametrize('order',[0,1,2,3])
def test_final_family_source_contract_and_constants(name,order,ext_ctx):
    values=[number(v) for v in generic_values()]
    raw,terms=Values(values,ext_ctx),Terms(values,ext_ctx)
    algo=get('accelerators',name)({'order':order});a,b=AlgoState(),AlgoState()
    for _ in range(3):
        need=algo.required_input(a)
        a=algo.step(raw,a,ext_ctx);b=algo.step(terms,b,ext_ctx)
        assert len(raw)==len(terms)==need
        relative_close(ext_ctx,a.estimate,b.estimate,digits=50)
    constant=algo.step(Values([mp.mpf(5)]*80,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,constant.estimate,mp.mpf(5))


@pytest.mark.parametrize('name',['chang_wynn','wynn_epsilon_adaptive'])
@pytest.mark.parametrize('order',[1,2,3,6])
def test_final_nonlinear_geometric_kernel(name,order,ext_ctx):
    values=[mp.mpf(3)+mp.mpf('.5')**i for i in range(30)]
    algo=get('accelerators',name)({'order':order})
    result=algo.step(Values(values,ext_ctx),AlgoState(),ext_ctx)
    relative_close(ext_ctx,result.estimate,mp.mpf(3),digits=50)


def qelg_values(case,count):
    if case=='alternating':return [mp.fsum((-mp.mpf(1))**j/(j+1) for j in range(i+1)) for i in range(count)]
    if case=='random':
        state=17;values=[]
        for _ in range(count):
            state=(state*48271)%2147483647
            values.append(mp.mpf(state)/2147483647+3)
        return values
    if case=='plateau':return [mp.mpf(3) if i<5 else mp.mpf(1)+mp.mpf('.5')**(i-5) for i in range(count)]
    return [mp.mpf(3)+mp.mpf('.5')**i for i in range(count)]


@pytest.mark.parametrize('case',['alternating','random','plateau','geometric'])
@pytest.mark.parametrize('count',[3,7,17,61,121])
def test_adaptive_against_external_gsl_qelg(case,count,ext_ctx):
    binary=os.environ.get('SHANKS_QELG_REFERENCE')
    if not binary:pytest.skip('Build external GSL QELG reference using tools/build_qelg_reference.py')
    # Use the same binary64 input in the independent C reference and both backends.
    values=[mp.mpf(float(v)) for v in qelg_values(case,count)]
    output=subprocess.check_output([binary],input='\n'.join(str(float(v)) for v in values),text=True).splitlines()
    estimate,stats=condensed_epsilon([ext_ctx.number(mp.nstr(v,100)) for v in values],ext_ctx,ext_ctx.number('1e-4'),ext_ctx.number(NATIVE_EPS))
    relative_close(ext_ctx,estimate,mp.mpf(output[-1]),digits=8)
    assert stats['peak_length']<=50
    if case=='random' and count>=61:assert stats['capacity_trims']>0
    cpp=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if cpp:
        native=subprocess.check_output([cpp,'--adaptive-evaluate'],input='\n'.join(str(float(v)) for v in values),text=True)
        relative_close(ext_ctx,ext_ctx.number(native.strip()),mp.mpf(output[-1]),digits=8)
    if case=='plateau':assert stats['restarts']>0


@pytest.mark.parametrize('name,params',[
    *[(name,{'order':v}) for name in NAMES for v in [-1,True,1.5]],
    ('homeier_j',{'order':31}),('homeier_j',{'max_order':0}),('homeier_j',{'delta_power':0}),
    ('homeier_j',{'delta_mode':'wrong'}),
])
def test_invalid_final_integer_and_mode_params(name,params):
    with pytest.raises(ValueError):get('accelerators',name)(params)


@pytest.mark.parametrize('name,params',[
    *[('homeier_j',{'safeguard':v}) for v in ['-1','1','nan','inf']],
    *[('homeier_j',{'delta_shift':v}) for v in ['-1','nan','inf']],
    *[('wynn_epsilon_adaptive',{'irregularity_threshold':v}) for v in ['0','-1','nan','inf']],
    *[('wynn_epsilon_adaptive',{'tolerance':v}) for v in ['0','-1','1','nan','inf']],
])
def test_invalid_final_real_params(name,params,ext_ctx):
    with pytest.raises(ValueError):get('accelerators',name)(params).step(Values([mp.mpf(i) for i in range(80)],ext_ctx),AlgoState(),ext_ctx)


@pytest.mark.parametrize('name',NAMES)
def test_final_runner_and_storage(name,ext_ctx,tmp_path):
    from arbacc.runner import build_plan,execute_accel
    config={'precision':{'backend':ext_ctx.backend.name,'dps':50},'series':[{'type':'ln2','params':{'x':'1'}}],
        'accelerators':[{'type':name,'params':{'order':2},'n_max':12}]}
    plan=build_plan(config);assert not plan['errors']
    result=execute_accel(plan['accel'][0],tmp_path);assert result['status']=='ok',result


def test_eighth_cpp_values(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_REGRESSIONS')
    if not binary:pytest.skip('Set SHANKS_CPP_REGRESSIONS')
    lines=subprocess.check_output([binary,'--eighth-algorithm-values'],text=True).splitlines()
    values=qelg_values('alternating',150)
    for line in lines:
        name,n,k,remainder,beta,mode,shift,extra,value=line.split('\t')
        params={'order':int(k),'remainder':remainder,'beta':beta,'delta_mode':mode,'delta_shift':shift,'delta_power':3,
            'irregularity_threshold':extra,'tolerance':NATIVE_EPS,'safeguard':'0'}
        result=get('accelerators',name)(params).step(Values(values,ext_ctx),AlgoState(iteration=int(n)),ext_ctx)
        relative_close(ext_ctx,result.estimate,mp.mpf(value),digits=8)
    assert len(lines)==1132
