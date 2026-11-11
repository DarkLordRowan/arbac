"""Regression tests of the independently recomputed research metrics."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import mpmath as mp
from arbac_research.metrics import METRICS_SCHEMA_VERSION, summarize_task, aggregate_summaries


def row(t, n, v, **kw):
    r = dict(task_id="t",row_type=t,n_used=n,k=n,value=v,exact_sum="1",
             series_id="case",class_id="power",noise_id="none",accel_id="a",
             method_id="method",backend="mpmath",dps=100,status="ok",elapsed_ms=3.5)
    r.update(kw)
    return r


def test_per_step_gains_and_loss_after_best():
    r=summarize_task([row("baseline",2,"1.01"),row("baseline",3,"1.001"),
        row("accel",2,"1.001"),row("accel",3,"1.00001"),row("accel",4,"1.0001",base_value="1.001")])
    assert r["metrics_schema_version"]==METRICS_SCHEMA_VERSION
    assert r["best_n"]==3 and r["last_n"]==4
    assert abs(float(r["gain_best_orders"])-2)<1e-15
    assert abs(float(r["gain_last_orders"])-1)<1e-15
    assert abs(float(r["step_gain_mean_orders"])-(1+2+1)/3)<1e-15
    assert abs(float(r["step_gain_median_orders"])-1)<1e-15
    assert r["n_steps_comparable"]==3
    assert r["n_steps_better"]==3
    assert r["step_better_share"]==1
    assert abs(float(r["last_best_loss_orders"])-1)<1e-15
    assert r["error_increases"]==1 and r["error_decreases"]==1
    assert r["error_monotonicity"]=="nonmonotonic"


def test_cpp_ratio_differs_from_own_relative_error():
    r=summarize_task([row("baseline",2,"1.001"),row("baseline",3,"1.000000001"),
                      row("accel",2,"1.00001")])
    assert abs(float(r["gain_best_orders"])-2)<1e-12
    assert abs(float(r["cpp_orders_gain_vs_series_min"])+4)<1e-12
    assert abs(float(r["cpp_relative_error_vs_series_min"])-10000)<1e-8
    assert abs(float(r["relative_error_best"])-1e-5)<1e-12


def test_epsilon_savings_and_threshold_success_not_equal_c1():
    r=summarize_task([row("baseline",1,"1.1"),row("baseline",2,"1.001"),
                      row("baseline",3,"1.00001"),row("accel",1,"1.01"),
                      row("accel",2,"1.00001")],epsilon="1e-4")
    assert r["base_first_epsilon_n"]==3
    assert r["accel_first_epsilon_n"]==2
    assert r["epsilon_saved_terms"]==1
    assert r["successful_acceleration"]==1
    assert r["epsilon_earlier"]==1

    late=summarize_task([row("baseline",1,"1.1"),row("baseline",2,"1.00001"),
                        row("baseline",3,"1.0001"),row("accel",3,"1.000001")],epsilon="1e-4")
    assert late["base_first_epsilon_n"]==2
    assert late["accel_first_epsilon_n"]==3
    assert late["c1"]==1
    assert late["successful_acceleration"]==0
    assert late["epsilon_saved_terms"]==-1


def test_success_without_baseline_reaching_epsilon():
    r=summarize_task([row("baseline",2,"1.01"),row("accel",2,"1.0001")],epsilon="1e-6")
    assert r["base_first_epsilon_n"] is None
    assert r["accel_first_epsilon_n"] is None
    assert r["successful_acceleration"]==1


def test_unknown_is_not_zero_and_unavailable_cpp_fields():
    r=summarize_task([row("accel",2,"1.00001",exact_sum=None)])
    assert r["reference_available"]==0
    assert r["c1"] is None
    assert r["gain_best_orders"] is None
    assert r["op_add"] is None and r["op_mul"] is None
    assert r["filter_trigger_n"] is None
    assert r["division_zero_recovered"] is None


def test_complex_sequence_has_no_real_one_sidedness():
    r=summarize_task([row("baseline",2,"1+0.1j",exact_sum="1"),
                      row("accel",2,"1+0.001j",exact_sum="1")])
    assert r["one_sided"] is None
    assert r["sign_changes"] is None
    assert r["c1"]==1


def test_nonincreasing_error_and_equal_steps():
    r=summarize_task([row("baseline",1,"1.4"),row("baseline",2,"1.2"),row("baseline",3,"1.1"),
                      row("accel",1,"1.1"),row("accel",2,"1.1"),row("accel",3,"1.01")])
    assert r["error_decreases"]==1 and r["error_equals"]==1
    assert r["error_monotonicity"]=="nonincreasing_error"
    assert r["one_sided"]==1


def test_failed_prefix_counted_but_no_phantom_recovery():
    r=summarize_task([row("baseline",1,"1.1",status="failed",failure="ZeroDivisionError"),
                      row("accel",1,"1.001",status="failed",failure="ZeroDivisionError")])
    assert r["failure_category"]=="division_zero"
    assert r["division_zero_failure"]==1
    assert r["division_zero_first_n"] is None
    assert r["division_zero_recovered"] is None
    assert r["n_accel_valid"]==1


def test_groups_counts_cases_not_configs_and_reports_time():
    a=summarize_task([row("baseline",2,"1.1",elapsed_ms=10),row("accel",2,"1.001",elapsed_ms=10)])
    b=summarize_task([row("baseline",2,"1.1",task_id="t2",accel_id="b",elapsed_ms=20),
                      row("accel",2,"1.000001",task_id="t2",accel_id="b",elapsed_ms=20)])
    groups=aggregate_summaries([a,b])
    assert groups[0]["cases"]==1
    assert groups[0]["tasks"]==2
    assert groups[0]["c1"]==1 and groups[0]["c5"]==1
    assert groups[0]["successful_acceleration_cases"]==1
    assert abs(float(groups[0]["median_gain_orders"])-5)<1e-10
    assert abs(float(groups[0]["median_elapsed_ms"])-15)<1e-10
    assert groups[0]["aggregation_policy"].endswith("ORACLE")


def test_infinite_gain_and_unknown_both_exact():
    r=summarize_task([row("baseline",1,"1.01"),row("accel",1,"1")])
    assert mp.isinf(mp.mpf(r["gain_best_orders"]))
    assert r["c5"]==1
    both=summarize_task([row("baseline",1,"1"),row("accel",1,"1")])
    assert both["gain_best_orders"] is None and both["c1"] is None


def test_gui_source_can_be_imported_without_instantiating_tk():
    from arbac_research.gui import METRIC_HELP, METRIC_GROUP_SECTIONS
    assert "cpp_orders_gain_vs_series_min" in METRIC_HELP
    assert "Робастность" in METRIC_GROUP_SECTIONS


def test_cpp_zero_error_convention_differs_from_mathematical_gain():
    from arbac_research.metrics import cpp_orders_gain, gain
    with mp.workdps(70):
        assert gain(mp.mpf('0.01'), mp.mpf('0')) == mp.inf
        assert abs(cpp_orders_gain(mp.mpf('0.01'),mp.mpf('0')) - 2)<mp.mpf('1e-60')
        assert cpp_orders_gain(mp.mpf('0'),mp.mpf('0'))==0
