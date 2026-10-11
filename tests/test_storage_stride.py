"""
Тесты сжатия через STRIDE.
"""

from __future__ import annotations
import pytest

from arbacc.core import Context, get
from arbacc.precision import get_backend
from arbacc.runner.run_accel import run_accelerator
from arbacc.runner.save_result import save_accelerated_result
from arbacc.storage import load_iterations


@pytest.fixture
def ctx50():
    return Context(backend=get_backend("mpmath"), dps=50)


def test_stride_reduces_iterations(ctx50, tmp_path, monkeypatch):
    """При STRIDE=10 в файле ~10% итераций."""
    import arbacc.settings as settings
    monkeypatch.setattr(settings, "STORAGE_ITER_STRIDE", 10)

    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    stream = ZetaCls(params={"s": 3}).build_stream(ctx50)
    result = run_accelerator(
        source=stream,
        accelerator=AitkenCls(params={}),
        stopping_criteria=[MaxIterCls(params={"n": 100})],
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx50,
        n_max=500,
    )
    assert len(result.iterations) == 100

    save_accelerated_result(
        output_root=tmp_path,
        series_id="zeta_s3",
        noise_id="none",
        accel_id="aitken_delta2_dps50",
        result=result,
        ctx=ctx50,
        input_payload={"x": 1},
    )

    iters = load_iterations(
        tmp_path / "accel" / "zeta_s3" / "none" / "aitken_delta2_dps50" / "iterations"
    )
    # 100 / 10 = 10, +1 если последняя не попала (100-я — это k=99, в stride 10 попадает k=90, значит добавится k=99)
    assert 10 <= len(iters) <= 12, f"got {len(iters)}"
    # Первая и последняя на месте.
    assert iters[0]["k"] == 0
    assert iters[-1]["k"] == 99


def test_stride_1_keeps_all(ctx50, tmp_path, monkeypatch):
    """При STRIDE=1 сохраняются все итерации."""
    import arbacc.settings as settings
    monkeypatch.setattr(settings, "STORAGE_ITER_STRIDE", 1)

    ZetaCls = get("series", "zeta")
    AitkenCls = get("accelerators", "aitken_delta2")
    MaxIterCls = get("stopping", "max_iter")

    stream = ZetaCls(params={"s": 3}).build_stream(ctx50)
    result = run_accelerator(
        source=stream,
        accelerator=AitkenCls(params={}),
        stopping_criteria=[MaxIterCls(params={"n": 30})],
        stopping_mode="any",
        online_envelopes=[],
        ctx=ctx50,
        n_max=500,
    )

    save_accelerated_result(
        output_root=tmp_path,
        series_id="z", noise_id="n", accel_id="a",
        result=result, ctx=ctx50, input_payload={"x": 1},
    )
    iters = load_iterations(
        tmp_path / "accel" / "z" / "n" / "a" / "iterations"
    )
    assert len(iters) == 30