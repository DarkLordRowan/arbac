"""
Попарное согласие backend'ов.

Для каждой пары (b1, b2) — сколько значащих цифр совпадает
на sin, cos, exp, log, sqrt, zeta(3), zeta(5), gamma(0.5).

Ожидаем: согласие ≥ dps − 5 для всех пар.
"""

from __future__ import annotations
import pytest

from arbacc.precision import list_backends, get_backend


FNS = [
    ("sin(0.6)",   lambda b, dps: b.sin(b.number("0.6", dps), dps)),
    ("cos(0.6)",   lambda b, dps: b.cos(b.number("0.6", dps), dps)),
    ("exp(0.6)",   lambda b, dps: b.exp(b.number("0.6", dps), dps)),
    ("log(2)",     lambda b, dps: b.log(b.number("2", dps), dps)),
    ("sqrt(2)",    lambda b, dps: b.pow(b.number("2", dps),
                                        b.number("0.5", dps), dps)),
    ("zeta(3)",    lambda b, dps: b.zeta(b.number("3", dps), dps)),
    ("zeta(5)",    lambda b, dps: b.zeta(b.number("5", dps), dps)),
    ("gamma(0.5)", lambda b, dps: b.gamma(b.number("0.5", dps), dps)),
]


def _all_pairs():
    """Все упорядоченные пары (b1, b2) из доступных backend'ов."""
    backends = list_backends()
    for i, b1 in enumerate(backends):
        for b2 in backends[i + 1:]:
            yield b1, b2


# Кешируем список пар на момент сбора тестов.
_PAIRS = list(_all_pairs())


@pytest.mark.backend
@pytest.mark.skipif(len(list_backends()) < 2,
                    reason="нужно ≥2 backend'а для сравнения")
@pytest.mark.parametrize("b1_name,b2_name", _PAIRS)
@pytest.mark.parametrize("dps", [20, 50])
def test_pairwise_agreement(b1_name, b2_name, dps):
    """Backend'ы согласны на всех базовых функциях."""
    b1 = get_backend(b1_name)
    b2 = get_backend(b2_name)

    for name, fn in FNS:
        v1 = fn(b1, dps)
        v2 = fn(b2, dps)
        d = b1.digits_of(v1, v2, dps)
        assert d >= dps - 5, (
            f"{b1_name} vs {b2_name} на {name} при dps={dps}: "
            f"только {d} знаков"
        )