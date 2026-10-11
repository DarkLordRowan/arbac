"""
Тесты точности хранилища: числа сохраняются и читаются в полной
точности backend'а — без потерь через float.
"""

from __future__ import annotations
import pytest

from arbacc.core import Context
from arbacc.precision import get_backend, list_backends
from arbacc.storage import save_iterations, load_iterations


@pytest.mark.parametrize("backend_name", list_backends())
@pytest.mark.parametrize("dps", [30, 100, 300])
def test_iterations_roundtrip_full_precision(
    backend_name, dps, tmp_path,
):
    """
    Число сохраняется и читается ровно таким же, как было —
    до последней значащей цифры при dps.
    """
    b = get_backend(backend_name)
    ctx = Context(backend=b, dps=dps)

    # Готовим число с dps+10 значащими цифрами — намеренно длиннее dps,
    # чтобы поймать обрезку.
    digits = "1234567890" * ((dps + 10) // 10 + 1)
    s_orig = "1." + digits[: dps + 10]
    x = ctx.number(s_orig)

    rows = [{
        "k": 0,
        "estimate": b.to_str(x, dps),
        "n_used": 1,
        "_task_meta": {
            "task_id": "t",
            "backend": backend_name,
            "dps": dps,
            "series_id": "s",
            "noise_id": "n",
            "accel_id": "a",
        },
    }]

    save_iterations(tmp_path / "iters", rows, fmt="parquet")
    loaded = load_iterations(tmp_path / "iters")

    assert len(loaded) == 1
    y = b.from_str(loaded[0]["estimate"], dps)

    # Совпадение до последней заявленной цифры.
    d = b.digits_of(x, y, dps)
    assert d >= dps - 1, f"{backend_name} dps={dps}: только {d} знаков"


def test_digits_gained_30_means_30(tmp_path):
    """
    Контрольная проверка: если итоговая точность заявлена как 30
    цифр — разность с эталоном действительно < 10^-29.
    """
    b = get_backend("mpmath")
    dps = 50
    ctx = Context(backend=b, dps=dps)

    # Эталон (точное значение) и приближение, отличающееся на 10^-30.
    exact = b.number("1." + "0" * 40, dps)
    approx_str = "1." + "0" * 29 + "1" + "0" * 10
    approx = ctx.number(approx_str)

    diff = b.sub(exact, approx, dps)
    abs_diff = b.abs_val(diff, dps)
    # 10^-30.
    threshold = b.pow(ctx.number(10), ctx.number(-30), dps)
    s = b.sign(b.sub(abs_diff, threshold, dps), dps)
    assert s < 0, f"diff должен быть < 1e-30, а он {b.to_str(abs_diff, dps)}"

    # И digits_of именно это покажет.
    d = b.digits_of(approx, exact, dps)
    assert 29 <= d <= 30, f"digits_of={d}, ожидали ~30"