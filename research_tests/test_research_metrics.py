import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1]))
import pytest
from arbac_research.metrics import gain, summarize_task, aggregate_summaries, number


def row(kind,m, val,**x):
    d=dict(task_id="one",row_type=kind,n_used=m,k=m,value=val,
           exact_sum="1",series_id="s",class_id="power",accel_id="a",
           backend="mpmath",dps=100,status="ok",elapsed_ms=10)
    d.update(x)
    return d


def test_gain_decimal_orders_exact():
    import mpmath as mp
    with mp.workdps(100):
        assert abs(gain(mp.mpf("1e-3"),mp.mpf("1e-8"))-5)<mp.mpf('1e-80')
        assert gain(mp.mpf("1e-8"),mp.mpf("1e-3"))<-4
        assert gain(mp.mpf("1"),mp.mpf("0"))==mp.inf
        assert gain(mp.mpf("0"),mp.mpf("0")) is None
        assert gain(mp.mpf("0"),mp.mpf("1"))==-mp.inf


def test_best_and_last_are_distinct_with_full_baseline():
    trace=[row("baseline",1,"1.1"),row("baseline",2,"1.01"),
           row("baseline",3,"1.001"),row("accel",2,"1.00000001"),
           row("accel",3,"1.0001")]
    r=summarize_task(trace,epsilon="1e-5")
    assert r["best_n"]==2 and r["last_n"]==3
    assert r["c1"]==1 and r["c5"]==1
    assert r["base_first_epsilon_n"] is None
    assert r["accel_first_epsilon_n"]==2
    assert abs(float(r["gain_best_orders"])-6)<1e-9
    assert abs(float(r["gain_last_orders"])-1)<1e-9  # base 1e-3 vs accel 1e-4 -> gain 1
    assert r["last_best_loss_orders"] is not None


def test_missing_baseline_does_not_fabricate_gain():
    trace=[row("accel",2,"1.000001")]
    r=summarize_task(trace)
    assert r["best_error"] is not None
    assert r["c1"] is None and r["c5"] is None
    assert r["gain_best_orders"] is None


def test_only_matching_m_used_is_compared():
    trace=[row("baseline",2,"1.0001"),row("baseline",3,"1.00000001"),
           row("accel",2,"1.000001")]
    r=summarize_task(trace)
    assert r["c1"]==1
    assert abs(float(r["gain_best_orders"])-2)<1e-8


def test_preserve_100_dps_and_independent_groups():
    trace=[row("baseline",2,"1.000000000000000000000000000000000000001"),
           row("accel",2,"1.0000000000000000000000000000000000000000000000000001")]
    r=summarize_task(trace)
    assert abs(float(r["gain_best_orders"])-13)<1e-8
    data=aggregate_summaries([r])
    assert data[0]["tasks"]==1
    assert data[0]["c1"]==1


def test_failure_keeps_correct_prefix():
    trace=[row("baseline",1,"1.1",status="failed",failure="ZeroDivisionError"),
           row("accel",1,"1.001",status="failed",failure="ZeroDivisionError")]
    r=summarize_task(trace)
    assert r["status"]=="failed" and r["c1"]==1
    assert aggregate_summaries([r])[0]["failed"]==1


def test_no_reference_error_not_zero():
    r=summarize_task([row("accel",1,"12",exact_sum=None)])
    assert r["best_error"] is None
    assert r["c1"] is None


def test_sign_changes_and_relative_error():
    trace=[row("baseline",1,"1.5"),row("baseline",2,"1.25"),
           row("accel",1,"1.1"),row("accel",2,"0.99")]
    r=summarize_task(trace)
    assert r["sign_changes"]==1
    assert r["relative_error_best"] is not None


def test_nonpositive_epsilon_fails():
    with pytest.raises(ValueError):
        summarize_task([row("accel",1,"1.01")],epsilon="0")


def test_group_dedup_configurations_per_sequence():
    base=[row("baseline",2,"1.1"),row("accel",2,"1.001",accel_id="method_order1")]
    b=[row("baseline",2,"1.1"),row("accel",2,"1.000001",accel_id="method_order2")]
    a0=summarize_task(base)
    a1=summarize_task(b)
    # Two configurations of ONE sequence = ONE result in 70-sequence coverage.
    a0["method_id"]=a1["method_id"]="method"
    grouped=aggregate_summaries([a0,a1])
    assert grouped[0]["tasks"]==2
    assert grouped[0]["cases"]==1
    assert grouped[0]["c1"]==1
    assert grouped[0]["c5"]==1
    assert grouped[0]["aggregation_policy"].endswith("ORACLE")
    per_task=aggregate_summaries([a0,a1],per_task=True)
    assert per_task[0]["tasks"]==2
    assert per_task[0]["cases"]==2
    assert per_task[0]["c1"]==2


def test_cpp_aggregate_gain_differs_from_budget_matched():
    trace=[row("baseline",2,"1.01"),row("baseline",3,"1.0000001"),
           row("accel",2,"1.000001")]
    r=summarize_task(trace)
    assert abs(float(r["gain_best_orders"])-4)<1e-8
    assert abs(float(r["cpp_orders_gain_vs_series_min"])+1)<1e-8


def test_complex_high_precision_preserved():
    import mpmath as mp
    with mp.workdps(100):
        x=number("(1.000000000000000000000000000000000000000001 + 2e-50j)")
        assert isinstance(x,mp.mpc)
        assert abs((x.real-1)-mp.mpf("1e-42")) < mp.mpf("1e-80")
        assert abs(x.imag-mp.mpf("2e-50")) < mp.mpf("1e-80")
