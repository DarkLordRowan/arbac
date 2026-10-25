"""Sequence semantics, exact recurrence poles, quadrature and independent integrals."""
from fractions import Fraction
import json
import os
from pathlib import Path
import subprocess

import mpmath
import pytest
from arbacc.core import Context,get,list_registered
from arbacc.core.accelerator import AlgoState
from arbacc.core.stream import extend_partials,series_term
from arbacc.precision import get_backend
from arbacc.runner import build_plan,execute_accel,run_accelerator
from arbacc.series.rump_sequences import RUMP_SPECS,UndefinedRecurrence
from tests.test_extended_series import ext_ctx,relative_close

mp=mpmath.mp.clone();mp.dps=110
FOURTH_NAMES={f'rump_seq{i}' for i in range(1,8)}|{
    'natural_series','integral1','minus_one_n_fact_n_in_n','minus_one_ned_in_n'}


def linearized_values(index,count,offset=Fraction(0)):
    u0,u1,a,outer,b,inner,c=RUMP_SPECS[index]
    y=[Fraction(1),u0+offset,(u0+offset)*u1]
    for _ in range(count):
        y.append(a*y[-1]+outer*b*y[-2]+outer*inner*c*y[-3])
    values=[]
    for n in range(count):
        if not y[n]: raise ZeroDivisionError('linearized denominator vanishes')
        values.append(y[n+1]/y[n])
    return values


@pytest.mark.parametrize('index',range(1,8))
@pytest.mark.parametrize('offset',['0','.01'])
def test_exact_rump_against_independent_linear_recurrence(index,offset,ext_ctx):
    series=get('series',f'rump_seq{index}')({'x':offset,'evaluation':'exact'})
    stream=series.build_stream(ext_ctx)
    count=7 if index in (1,2) and offset=='0' else 12
    expected=linearized_values(index,count,Fraction(offset))
    assert stream.kind=='sequence'
    for n,value in enumerate(expected):
        relative_close(ext_ctx,stream.get(n),mp.mpf(value.numerator)/value.denominator)
    size=len(stream)
    stream.get(2)
    assert len(stream)==size


@pytest.mark.parametrize('index,pole',[(1,7),(2,7),(4,17)])
def test_exact_rump_poles_and_missing_limit(index,pole,ext_ctx):
    series=get('series',f'rump_seq{index}')({'x':'0','evaluation':'exact'})
    stream=series.build_stream(ext_ctx)
    assert stream.get(pole-1)==ext_ctx.number(0)
    with pytest.raises(UndefinedRecurrence): stream.get(pole)
    assert len(stream)==pole
    assert series.analytic_sum(ext_ctx) is None
    assert series.reference_kind=='undefined_exact_recurrence'


@pytest.mark.parametrize('index,limit',[(3,6),(5,5),(6,36),(7,None)])
def test_true_rump_limits_and_perturbation_status(index,limit,ext_ctx):
    series=get('series',f'rump_seq{index}')({'x':'0','evaluation':'exact'})
    expected=mp.mpf(limit) if limit is not None else (-61-mp.sqrt(3657))/4
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),expected)
    assert get('series',f'rump_seq{index}')({'x':'.001'}).analytic_sum(ext_ctx) is None


def test_wrong_limit_is_an_intended_finite_precision_effect():
    ctx=Context(backend=get_backend('mpmath'),dps=25)
    exact=get('series','rump_seq5')({'evaluation':'exact'}).build_stream(ctx)
    rounded=get('series','rump_seq5')({'evaluation':'backend'}).build_stream(ctx)
    assert abs(float(exact.get(100))-5)<1e-12
    assert abs(float(rounded.get(100))-100)<1e-12
    high=get('series','rump_seq5')({'evaluation':'backend'}).build_stream(Context(backend=get_backend('mpmath'),dps=100))
    assert abs(float(high.get(35))-5)<1e-7


class Values:
    kind='sequence'
    def __init__(self,values,ctx):
        self.values=[ctx.number(mp.nstr(v,105)) for v in values]
        self.count=0
    def get(self,n):
        self.extend_to(n)
        return self.values[n]
    def extend_to(self,n):
        if n<0 or n>=len(self.values): raise IndexError(n)
        self.count=max(self.count,n+1)
    def __len__(self):return self.count


class Terms(Values):
    kind='terms'
    def __init__(self,values,ctx):
        increments=[values[0]]+[values[i]-values[i-1] for i in range(1,len(values))]
        super().__init__(increments,ctx)


@pytest.mark.parametrize('name',list_registered('accelerators')['accelerators'])
def test_every_accelerator_handles_sequences_and_terms_consistently(name,ext_ctx):
    values=[mp.fsum((-mp.mpf(1))**j/(j+1) for j in range(n+1)) for n in range(25)]
    sequence,terms=Values(values,ext_ctx),Terms(values,ext_ctx)
    algo=get('accelerators',name)({'order':2})
    seq_state,term_state=AlgoState(),AlgoState()
    for _ in range(4):
        seq_state=algo.step(sequence,seq_state,ext_ctx)
        term_state=algo.step(terms,term_state,ext_ctx)
        expected=mp.mpf(ext_ctx.backend.to_str(term_state.estimate,ext_ctx.dps))
        relative_close(ext_ctx,seq_state.estimate,expected,digits=55)


def test_raw_values_survive_cancellation_and_noise_wrappers(ext_ctx):
    values=[mp.mpf('1e150'),mp.mpf(1),mp.mpf('1.5'),mp.mpf('1.75')]
    source=Values(values,ext_ctx)
    none=get('noise','none')({}).wrap(source,ext_ctx)
    assert none.kind=='sequence'
    partials=extend_partials(none,[],ext_ctx,4)
    assert partials[1]==ext_ctx.number(1)
    result=get('accelerators','aitken_delta2')({}).step(none,AlgoState(iteration=1),ext_ctx)
    relative_close(ext_ctx,result.estimate,mp.mpf(2))
    sigma_zero=get('noise','gaussian')({'sigma':'0'},seed=42).wrap(Values(values,ext_ctx),ext_ctx)
    assert sigma_zero.kind=='sequence'
    assert sigma_zero.get(1)==ext_ctx.number(1)


def test_sequence_noise_is_applied_to_values_not_to_accumulated_terms(ext_ctx):
    source=Values([mp.mpf(1),mp.mpf(2),mp.mpf(3)],ext_ctx)
    noise=get('noise','gaussian')({'sigma':'.01'},seed=4)
    wrapped=noise.wrap(source,ext_ctx)
    samples=extend_partials(wrapped,[],ext_ctx,3)
    for n in range(3):
        assert ext_ctx.backend.digits_of(samples[n],noise.transform(n,source.get(n),ext_ctx),ext_ctx.dps)>=70
    relative_close(ext_ctx,series_term(wrapped,2,ext_ctx),
                   mp.mpf(ext_ctx.backend.to_str(samples[2],ext_ctx.dps))-mp.mpf(ext_ctx.backend.to_str(samples[1],ext_ctx.dps)))


@pytest.mark.parametrize('name,factorial',[
    ('minus_one_n_fact_n_in_n',True),('minus_one_ned_in_n',False)])
def test_rapid_constant_reference_against_independent_quadrature(name,factorial,ext_ctx):
    reference=(mp.quad(lambda t:mp.log(t)/(1-t*mp.log(t))**2,[0,mp.mpf('.5'),1]) if factorial
               else -mp.quad(lambda t:mp.power(t,t),[0,mp.mpf('.5'),1]))
    series=get('series',name)({'x':'.2'})
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),mp.mpf('.2')*reference)
    for n in [0,1,3,20]:
        k=n+1
        expected=mp.mpf('.2')*(-1)**k*(mp.factorial(k) if factorial else 1)/mp.power(k,k)
        relative_close(ext_ctx,series.generate(n,ext_ctx),expected)
    zero=get('series',name)({'x':'0'})
    assert zero.analytic_sum(ext_ctx)==ext_ctx.number(0)


@pytest.mark.parametrize('steps',[1,4,8])
def test_quadrature_sequence_includes_every_panel(steps,ext_ctx):
    series=get('series','integral1')({'steps':steps})
    stream=series.build_stream(ext_ctx)
    for n in range(5):
        panels=steps*(n+1)
        def q(x):return 4*x*mp.log(x)/(1+x*x) if x else mp.mpf(0)
        expected=mp.fsum((q(mp.mpf(j)/panels)+q(mp.mpf(j+1)/panels))/(2*panels) for j in range(panels))
        relative_close(ext_ctx,stream.get(n),expected)
    reference=mp.quad(lambda t:mp.log(t)/(1+t),[0,1])
    relative_close(ext_ctx,series.analytic_sum(ext_ctx),reference)
    fine=series.generate(15,ext_ctx)
    assert abs(mp.mpf(ext_ctx.backend.to_str(fine,ext_ctx.dps))-reference)<abs(mp.mpf(ext_ctx.backend.to_str(stream.get(0),ext_ctx.dps))-reference)


@pytest.mark.parametrize('steps',[0,-1,True,1.5])
def test_invalid_quadrature_steps(steps):
    with pytest.raises(ValueError):get('series','integral1')({'steps':steps})


def test_quadrature_panel_limit(ext_ctx):
    stream=get('series','integral1')({'steps':8,'max_panels':16}).build_stream(ext_ctx)
    stream.get(1)
    with pytest.raises(ValueError):stream.get(2)
    assert len(stream)==2


def test_natural_series_has_no_ordinary_sum(ext_ctx):
    series=get('series','natural_series')({})
    stream=series.build_stream(ext_ctx)
    partials=extend_partials(stream,[],ext_ctx,100)
    assert partials[-1]==ext_ctx.number(4950)
    assert series.exact_sum(ext_ctx) is None
    relative_close(ext_ctx,series.regularized_value(ext_ctx),-mp.mpf(1)/12)


def test_materialization_error_retains_accelerator_history(ext_ctx):
    stream=get('series','rump_seq1')({'evaluation':'exact'}).build_stream(ext_ctx)
    result=run_accelerator(source=stream,accelerator=get('accelerators','aitken_delta2')({}),
       stopping_criteria=[],stopping_mode='any',online_envelopes=[],ctx=ext_ctx,n_max=20)
    assert result.status=='failed'
    assert result.iterations
    assert result.n_used==7
    assert 'UndefinedRecurrence' in result.stopped_by


@pytest.mark.parametrize('name',['rump_seq5','natural_series','integral1'])
def test_special_sources_integrate_with_runner_and_storage(name,tmp_path):
    config={'precision':{'backend':'mpmath','dps':40},
       'series':[{'type':name,'params':{'evaluation':'exact','steps':4}}],
       'accelerators':[{'type':'aitken_delta2','params':{},'n_max':7}]}
    plan=build_plan(config)
    assert not plan['errors']
    result=execute_accel(plan['accel'][0],tmp_path)
    assert result['status']=='ok',result
    saved=json.loads((Path(result['accel_dir'])/'result.json').read_text())
    assert saved['meta']['source_kind']==('terms' if name=='natural_series' else 'sequence')
    assert (saved['exact_sum'] is None)==(name=='natural_series')
    from arbacc.runner.execute import _load_accelerated_result
    ctx=Context(backend=get_backend('mpmath'),dps=40)
    parent=Path(result['accel_dir'])
    loaded=_load_accelerated_result(parent/'result.json',parent,ctx)
    assert loaded.meta['source_kind']==saved['meta']['source_kind']
    assert loaded.meta['reference_kind']==saved['meta']['reference_kind']
    assert (loaded.exact_sum is None)==(name=='natural_series')
    if loaded.exact_sum is not None:
        assert loaded.exact_sum==ctx.number(saved['exact_sum'])
    # Earlier result files omitted exact_sum; retain compatibility.
    saved.pop('exact_sum')
    (parent/'result.json').write_text(json.dumps(saved))
    assert _load_accelerated_result(parent/'result.json',parent,ctx).exact_sum is None


def test_raw_plot_uses_sequence_values():
    from gui.view_mode.data_loader import raw_partial_sums
    task={'precision':{'backend':'mpmath','dps':40},'series':{'type':'rump_seq5','params':{'evaluation':'exact'}},
          'noise':{'type':'none'},'accelerator':{'n_max':4}}
    xs,values=raw_partial_sums(task,max_n=4)
    assert xs==[1,2,3,4]
    assert mp.mpf(values[1])==mp.mpf('4.25')


@pytest.mark.parametrize('name',sorted(FOURTH_NAMES))
def test_fourth_sources_negative_indices(name,ext_ctx):
    with pytest.raises(IndexError):get('series',name)({}).generate(-1,ext_ctx)


def test_fourth_sources_cpp_samples(ext_ctx):
    binary=os.environ.get('SHANKS_CPP_CATALOGUE')
    if not binary:pytest.skip('Set SHANKS_CPP_CATALOGUE to compiled catalogue_probe')
    for name in sorted(FOURTH_NAMES):
        x='0' if name.startswith('rump_seq') else '.2'
        count=5 if name.startswith('rump_seq') else 8
        reference,observed,*samples=map(float,subprocess.check_output([binary,name,x,str(count)],text=True).split())
        series=get('series',name)({'x':x,'steps':32,'evaluation':'exact'})
        for n,value in enumerate(samples):
            # C++ uses binary64; cancellation in Rump recurrences amplifies rounding.
            relative_close(ext_ctx,series.generate(n,ext_ctx),mp.mpf(value),digits=7 if name.startswith('rump_seq') else 12)
        expected=series.analytic_sum(ext_ctx)
        if expected is None:
            assert mp.isnan(reference)
        else:
            relative_close(ext_ctx,expected,mp.mpf(reference),digits=12)
        if name=='integral1':relative_close(ext_ctx,series.generate(count-1,ext_ctx),mp.mpf(observed),digits=12)
