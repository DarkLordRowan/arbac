from arbac_research import verify


def test_verify_profile_numeric_equal_even_with_events(monkeypatch):
    a=[[dict(task_id='X',row_type='baseline',n_used=1,k=None,value='1.01',base_value=None),
        dict(task_id='X',row_type='accel',n_used=1,k=1,value='1.001',base_value='1.01')]]
    b=a[0]+[dict(task_id='X',row_type='event',n_used=1,event_type='runner_stop',event_message='n_max')]
    monkeypatch.setattr(verify,'iterate_tasks',lambda p: iter(a if p=='plain' else [b]))
    r=verify.verify_profile_equivalence('plain','profiled')
    assert r['ok'] and r['tasks_plain']==r['tasks_profiled']==1


def test_verify_profile_fails_numeric_change(monkeypatch):
    a=[[dict(task_id='X',row_type='accel',n_used=1,k=0,value='1.1')]]
    b=[[dict(task_id='X',row_type='accel',n_used=1,k=0,value='1.2')]]
    monkeypatch.setattr(verify,'iterate_tasks',lambda p: iter(a if p=='plain' else b))
    r=verify.verify_profile_equivalence('plain','profiled')
    assert not r['ok'] and r['different_numeric_traces']==['X']
