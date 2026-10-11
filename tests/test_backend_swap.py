"""
Swap backend'ов: один и тот же конфиг на mpmath и arb даёт
согласованные estimate.
"""

from __future__ import annotations
from pathlib import Path

import pytest

from arbacc.precision import list_backends, get_backend
from arbacc.runner import build_plan, execute_accel
from arbacc.storage import load_iterations


@pytest.mark.backend
def test_same_config_mpmath_vs_arb(config_minimal, tmp_path):
    """Один и тот же конфиг на mpmath и arb даёт согласованные estimate."""
    if "arb" not in list_backends():
        pytest.skip("arb недоступен")

    results = {}
    for backend in ("mpmath", "arb"):
        cfg = dict(config_minimal)
        cfg["precision"] = {"backend": backend, "dps": 40}
        plan = build_plan(cfg)
        out = tmp_path / backend
        out.mkdir()
        r = execute_accel(plan["accel"][0], out)
        assert r["status"] == "ok", f"{backend}: {r.get('error')}"

        ids = plan["accel"][0]["ids"]
        rel = (
            Path("accel") / ids["series_id"] / ids["noise_id"]
            / ids["accel_id"]
        )
        iters = load_iterations(out / rel / "iterations")
        results[backend] = iters[-1]["estimate"]

    b = get_backend("mpmath")
    x = b.from_str(results["mpmath"], 40)
    y = b.from_str(results["arb"], 40)
    d = b.digits_of(x, y, 40)
    assert d >= 30, f"mpmath vs arb: только {d} совпадающих знаков"