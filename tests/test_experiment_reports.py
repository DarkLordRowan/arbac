"""Report regression cases: sparse identity, missing references, tiny errors."""
import copy
import csv
import json

import pytest

from arbacc.analysis.experiment import (
    analyze_profiling, build_experiment_matrix, rank_algorithms, export_experiment_report,
)
from tests.test_extended_series import ext_ctx


def experiment():
    return {"seriesList": [{"id": "s", "limit": {"re": "0", "im": "0"}}],
            "accelList": [{"id": name} for name in ("a", "b", "c")],
            "seriesAccelList": [
                {"series_id": "s", "accel_id": "a", "computed": [
                    {"n": 3, "deviation": "1e-500"}, {"n": 1, "deviation": "2e-500"}]},
                {"series_id": "s", "accel_id": "b", "computed": [
                    {"n": 1, "deviation": "1e-490"}]},
                {"series_id": "s", "accel_id": "c", "computed": []}]}


def test_matrix_precision_and_ranking(ext_ctx):
    source = experiment()
    before = copy.deepcopy(source)
    matrix = build_experiment_matrix(source, ext_ctx, epsilon="1.5e-500")
    rows = rank_algorithms(matrix, ext_ctx)
    assert [(r["accel_id"], r["rank"]) for r in rows] == [("a", 1), ("b", 2), ("c", None)]
    assert rows[0]["reached_tolerance"] == 1
    assert rows[1]["reached_tolerance"] == 0
    cell = matrix["cells"]["s", "a"]
    assert cell["error"]["min_n"] == 3
    assert cell["error"]["first_tolerance_n"] == 3
    assert ext_ctx.backend.sign(cell["error"]["min"], ext_ctx.dps) == 1
    assert source == before


def test_unknown_errors_are_unranked_and_sparse(ext_ctx):
    source = experiment()
    source["seriesList"][0]["limit"] = None
    source["seriesAccelList"] = [{"series_id": "s", "accel_id": "a", "computed": [{"n": 0, "value": {"re": "3"}}]}]
    matrix = build_experiment_matrix(source, ext_ctx)
    assert len(matrix["cells"]) == 1
    assert all(r["rank"] is None for r in rank_algorithms(matrix, ext_ctx))
    assert matrix["cells"]["s", "a"]["error"]["count"] == 0


def test_dense_ranking_ties(ext_ctx):
    source = experiment()
    source["seriesAccelList"][1]["computed"] = source["seriesAccelList"][0]["computed"]
    assert [r["rank"] for r in rank_algorithms(build_experiment_matrix(source, ext_ctx), ext_ctx)] == [1, 1, None]


@pytest.mark.parametrize("kind", ["id", "pair", "reference"])
def test_rejects_ambiguous_experiments(kind, ext_ctx):
    source = experiment()
    if kind == "id":
        source["seriesList"] *= 2
    elif kind == "pair":
        source["seriesAccelList"] *= 2
    else:
        source["seriesAccelList"][0]["accel_id"] = "unknown"
    with pytest.raises(ValueError):
        build_experiment_matrix(source, ext_ctx)


def test_filters_keep_explicit_axes(ext_ctx):
    matrix = build_experiment_matrix(experiment(), ext_ctx, accel_ids={"b"})
    assert set(matrix["accelerators"]) == {"b"}
    assert set(matrix["cells"]) == {("s", "b")}


@pytest.mark.parametrize("epsilon", ["nan", "inf", "-1"])
def test_invalid_epsilon(epsilon, ext_ctx):
    with pytest.raises(ValueError):
        build_experiment_matrix(experiment(), ext_ctx, epsilon=epsilon)


def test_exports_preserve_tiny_errors(tmp_path, ext_ctx):
    matrix = build_experiment_matrix(experiment(), ext_ctx)
    for suffix in ("json", "csv"):
        path = tmp_path / ("report."+suffix)
        export_experiment_report(matrix, path, ext_ctx)
        if suffix == "json":
            data = json.loads(path.read_text())
            value = data["cells"][0]["error"]["min"]
            assert data["ranking"][0]["rank"] == 1
        else:
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            value = rows[0]["min"]
            assert len(rows) == 3
        assert ext_ctx.backend.sign(ext_ctx.number(value), ext_ctx.dps) > 0
    with pytest.raises(ValueError):
        export_experiment_report(matrix, tmp_path/"wrong.txt", ext_ctx)


def test_profiling_exact_counters_gaps_and_trend():
    large = 10**30
    points = [{"n": 3, "profiling": {"add": large+2, "mul": 2}},
              {"n": 0, "profiling": {"add": large, "mul": 1}},
              {"n": 1, "profiling": {"add": large+1, "mul": 1}},
              {"n": 2}, {"n": 4, "profiling": {"add": large+1, "mul": 1}}]
    report = analyze_profiling(points)
    assert report["steps_analyzed"] == 2
    assert report["trend_total"] == "decreasing_error"
    assert report["max_total_ops"] == large+4
    assert report["max_total_ops_n"] == 3
    assert report["decrease_ns_total"] == [4]
    assert report["decrease_ns_by_kind"] == {"add": [4], "mul": [4]}
    assert report["top_kinds"] == ["add", "mul"]


@pytest.mark.parametrize("totals, expected", [([], "unknown"), ([1], "unknown"),
    ([1, 1], "constant"), ([1, 2], "increasing"), ([1, 2, 2], "non_decreasing")])
def test_profiling_trends(totals, expected):
    assert analyze_profiling([{"n": n, "profiling": {"add": v}} for n, v in enumerate(totals)])["trend_total"] == expected


@pytest.mark.parametrize("value", [True, -1, 1.5, "2", float("nan")])
def test_profiling_rejects_invalid_counters(value):
    with pytest.raises(ValueError):
        analyze_profiling([{"n": 0, "profiling": {"add": value}}])



def test_report_cli(tmp_path):
    import subprocess
    import sys
    source, output = tmp_path/"experiment.json", tmp_path/"report.json"
    source.write_text(json.dumps(experiment()))
    command = [sys.executable, "-m", "arbacc.cli", "experiment-report", str(source), str(output), "--epsilon", "1e-501"]
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(output.read_text())["ranking"][0]["reached_tolerance"] == 0
    source.write_text('{"seriesList": [{"id": "s"}, {"id": "s"}]}')
    result = subprocess.run(command, capture_output=True, text=True)
    assert result.returncode == 1
    assert "duplicate" in result.stderr
