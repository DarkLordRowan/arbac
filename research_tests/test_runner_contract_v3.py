"""Isolated integration test for the verified Magister runner API contract.

Uses fake arbacc plugins so this test can execute without user's local source.
It does not substitute for testing the real Arbac build on Windows.
"""
from dataclasses import dataclass
from types import ModuleType, SimpleNamespace
import sys

from arbac_research.runner import _worker_one


@dataclass(frozen=True)
class Ctx:
    backend: object
    dps: int
    rounding: str = 'nearest'


class Backend:
    name='fake'
    def to_str(self,x,dps):return str(x)
    def add(self,a,b,dps):return a+b
    def sub(self,a,b,dps):return a-b
    def mul(self,a,b,dps):return a*b
    def div(self,a,b,dps):return a/b


class Source:
    def __init__(self):self.raw=[1.01,1.001,1.0001];self.extended=0
    def extend_to(self,n):self.extended=max(self.extended,n+1)
    def get(self,n):return self.raw[n]
    def __len__(self):return self.extended


class Series:
    def __init__(self,params,exact_sum=None):pass
    def build_stream(self,ctx):return Source()
    def exact_sum(self,ctx):return 1.0


class Noise:
    def __init__(self,params,seed=0):pass
    def wrap(self,src,ctx):return src


class Accel:
    name='mock';params={}
    def __init__(self,params):pass
    def required_input(self,state):return state.iteration+1
    def step(self,src,state,ctx):
        # The recorded backend add call is inside step only.
        v=ctx.backend.add(src.get(state.iteration),0,ctx.dps)
        return SimpleNamespace(iteration=state.iteration+1,estimate=v)


def fake_run_accelerator(source,accelerator,stopping_criteria,stopping_mode,
                         online_envelopes,ctx,n_max):
    state=SimpleNamespace(iteration=0)
    records=[]
    for _ in range(2):
        required=accelerator.required_input(state)
        source.extend_to(required-1)
        state=accelerator.step(source,state,ctx)
        records.append(SimpleNamespace(n_used=required,k=state.iteration-1,
                                       estimate=state.estimate))
    return SimpleNamespace(iterations=records,status='ok',error=None,
                           stopped_by='n_max(2)',n_used=2)


def register_fake_modules(monkeypatch):
    modules={}
    def mod(name, **attrs):
        m=ModuleType(name)
        for k,v in attrs.items():setattr(m,k,v)
        monkeypatch.setitem(sys.modules,name,m)
        modules[name]=m
        return m
    for name in ('arbacc','arbacc.core','arbacc.runner'):
        mod(name)
    mod('arbacc.core.context',Context=Ctx)
    mod('arbacc.core.registry',get=lambda category,name:
        {'series':Series,'noise':Noise,'accelerators':Accel}[category])
    mod('arbacc.precision',get_backend=lambda name:Backend())
    mod('arbacc.runner.run_accel',run_accelerator=fake_run_accelerator)
    mod('arbacc.core.stream',partial_value=lambda src,n,prev,ctx:src.get(n))


def test_worker_can_write_profile_and_events_without_mutating_values(monkeypatch):
    register_fake_modules(monkeypatch)
    task={'task_id':'faketask',
          'ids':{'series_id':'s','noise_id':'clean','accel_id':'a'},
          'precision':{'backend':'fake','dps':50},
          'series':{'type':'series','params':{}},
          'noise':{'type':'none','params':{},'seed':0},
          'accelerator':{'type':'fake','params':{},'n_max':2,'stopping':[]},
          'research_profile_backend_ops':True}
    rows_profile=_worker_one(task)
    assert len([r for r in rows_profile if r['row_type']=='baseline'])==2
    acc=[r for r in rows_profile if r['row_type']=='accel']
    assert [r['op_add'] for r in acc]==[1,1]
    assert [r['value'] for r in acc]==['1.01','1.001']
    assert any(r['row_type']=='event' and r['event_type']=='runner_stop' for r in rows_profile)
    task['research_profile_backend_ops']=False
    rows_plain=_worker_one(task)
    assert [r['value'] for r in rows_plain if r['row_type']=='accel']==[r['value'] for r in acc]
    assert all(r['op_add'] is None for r in rows_plain if r['row_type']=='accel')
