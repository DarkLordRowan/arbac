import pytest
from arbacc.convergence import analyze_convergence


def points(values):
    return [{"n":i,"deviation":v} for i,v in enumerate(values)]


@pytest.mark.parametrize("values,side,monotonicity", [
    ([".1",".01",".001"],"one_sided","strict_decreasing_error"),
    ([".1","-.01",".001"],"two_sided","strict_decreasing_error"),
    ([".1",".1"],"one_sided","constant_error"),
    ([".1",".1",".01"],"one_sided","non_increasing_error"),
    ([".1",".2"],"one_sided","strict_increasing_error"),
    ([".1",".2",".2"],"one_sided","non_decreasing_error"),
    ([".1",".2",".01"],"one_sided","random_error"),
    ([],"unknown","unknown"),
])
def test_convergence_classes(values,side,monotonicity,ctx):
    got=analyze_convergence(points(values),None,ctx)
    assert (got["side"],got["monotonicity"])==(side,monotonicity)


def test_small_stored_deviations_survive_rounding(ctx):
    data=[{"n":2,"value":{"re":"1"},"deviation":"1e-101"},
          {"n":1,"value":{"re":"1"},"deviation":"-1e-100"}]
    result=analyze_convergence(data,{"re":"1"},ctx)
    assert result["sign_change_ns"]==[2]
    assert result["monotonicity"]=="strict_decreasing_error"
    assert result["errors"][0][1]==ctx.number("1e-100")


def test_complex_error_and_invalid_points(ctx):
    data=[{"n":1,"value":{"re":"3","im":"4"}},
          {"n":2,"value":{"re":"nan"}},
          {"n":3,"value":{"re":"0","im":"1"}}]
    result=analyze_convergence(data,{"re":"0","im":"0"},ctx)
    assert result["errors"]==[(1,ctx.number(5)),(3,ctx.number(1))]
    assert result["steps_analyzed"]==1


def test_allowances(ctx):
    data=points(["1","-.1","-.2","-.01"])
    result=analyze_convergence(data,None,ctx,max_sign_changes=1,max_violations=1)
    assert result["side"]=="one_sided"
    assert result["monotonicity"]=="non_increasing_error"
    assert result["violations_ns"]==[2]


@pytest.mark.parametrize("kwargs",[{"tolerance":"-1"},{"tolerance":"nan"},{"max_violations":-1}])
def test_invalid_options(kwargs,ctx):
    with pytest.raises(ValueError):
        analyze_convergence([],None,ctx,**kwargs)
