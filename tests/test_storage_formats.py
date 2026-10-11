"""Roundtrip всех форматов хранения: jsonl, jsonl.gz, parquet."""

from __future__ import annotations
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend
from arbacc.storage import (
    save_iterations, load_iterations,
    save_values, load_values,
)


@pytest.fixture
def ctx50():
    return Context(backend=get_backend("mpmath"), dps=50)


def _make_iter_rows(ctx, n=10):
    b = ctx.backend
    return [
        {
            "k": i,
            "estimate": b.to_str(ctx.number(f"1.{i:04d}"), ctx.dps),
            "n_used": i + 1,
            "_task_meta": {
                "task_id": "t1",
                "backend": "mpmath",
                "dps": 50,
                "series_id": "s",
                "noise_id": "n",
                "accel_id": "a",
            },
        }
        for i in range(n)
    ]


@pytest.mark.parametrize("fmt", ["jsonl", "jsonl.gz", "parquet"])
def test_iterations_roundtrip(fmt, tmp_path, ctx50):
    """save/load iterations для всех форматов."""
    if fmt == "parquet":
        pytest.importorskip("pyarrow")
    rows = _make_iter_rows(ctx50)
    save_iterations(tmp_path / "iters", rows, fmt=fmt)
    loaded = load_iterations(tmp_path / "iters")
    assert len(loaded) == len(rows)
    assert loaded[0]["k"] == 0
    assert loaded[-1]["n_used"] == len(rows)


@pytest.mark.parametrize("fmt", ["jsonl", "jsonl.gz", "parquet"])
def test_values_roundtrip(fmt, tmp_path, ctx50):
    """save/load values для всех форматов."""
    if fmt == "parquet":
        pytest.importorskip("pyarrow")
    rows = [
        {
            "k": i,
            "value": ctx50.backend.to_str(
                ctx50.number(f"0.{i:04d}"), ctx50.dps,
            ),
            "_task_meta": {"task_id": "t1"},
        }
        for i in range(5)
    ]
    save_values(tmp_path / "vals", rows, fmt=fmt)
    loaded = load_values(tmp_path / "vals")
    assert len(loaded) == 5