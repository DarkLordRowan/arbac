"""Independent exact-rational oracle for the *implemented* legacy S quotient.

The historical Arbac ID 'levin_sidi_s' implements a factorial/Weniger-style
quotient and is NOT certified here as Sidi's distinct published S algorithm.
The comparison with 'weniger' is an equivalence/alias test, not an independent
oracle; the Fraction calculation below supplies the independent check.
"""
from fractions import Fraction as Q
from math import comb
import mpmath as mp
import pytest

from arbacc.core import AlgoState, Context, get
from arbacc.precision import get_backend
import arbacc.accelerators  # register plugins


class Sequence:
    kind = 'sequence'
    def __init__(self, data, ctx):
        self._values = [ctx.number(str(mp.mpf(v.numerator) / v.denominator)) for v in data]
        self._read = 0
    def get(self, n):
        self.extend_to(n)
        return self._values[n]
    def extend_to(self, n):
        if n < 0 or n >= len(self._values):
            raise IndexError(n)
        self._read = max(self._read, n + 1)
    def __len__(self):
        return self._read


def independent_quotient(values, n, k, beta, remainder):
    # Exact rational factorial transform. a_0 = s_0, a_j = s_j - s_(j-1).
    def term(j):
        return values[j] if j == 0 else values[j] - values[j - 1]
    def inv_omega(j):
        off = int(remainder in ('next', 'v_shift'))
        a = term(j + off)
        if remainder in ('v', 'v_shift'):
            following = term(j + off + 1)
            return (following - a) / (a * following)
        if remainder == 'u':
            a *= j + beta
        return Q(1) / a
    def pochhammer(x, m):
        result = Q(1)
        for i in range(m):
            result *= x + i
        return result
    terms = [Q((-1) ** j * comb(k, j)) * pochhammer(n + j + beta, k - 1) * inv_omega(n + j)
             for j in range(k + 1)]
    den = sum(terms)
    assert den != 0
    return sum((terms[j] * values[n + j] for j in range(k + 1)), Q(0)) / den


@pytest.mark.parametrize('k', [1, 2, 3, 4])
@pytest.mark.parametrize('n', [0, 1, 2])
@pytest.mark.parametrize('eval_method', ['direct', 'finite_difference'])
@pytest.mark.parametrize('remainder', ['u', 't', 'next', 'v', 'v_shift'])
def test_levin_sidi_s_independent_fraction_oracle(k, n, eval_method, remainder):
    mp.mp.dps = 110
    backend = get_backend('mpmath')
    ctx = Context(backend=backend, dps=100)
    values = [Q(7, 3) + Q(4, 5) * Q(2, 3) ** j + Q(3, j + 5) for j in range(20)]
    beta = Q(3, 2)
    expected = independent_quotient(values, n, k, beta, remainder)
    source = Sequence(values, ctx)
    params = {'order': k, 'beta': '1.5', 'remainder': remainder, 'evaluation': eval_method}
    state = get('accelerators', 'levin_sidi_s')(params).step(source, AlgoState(iteration=n), ctx)
    result = mp.mpf(backend.to_str(state.estimate, ctx.dps))
    target = mp.mpf(expected.numerator) / expected.denominator
    assert abs(result - target) < mp.mpf('1e-85') * max(1, abs(target))


def test_levin_sidi_s_formula_is_weniger_alias_not_independent_algorithm():
    """A reminder to never double count this algorithm as a novel formula."""
    mp.mp.dps = 110
    ctx = Context(backend=get_backend('mpmath'), dps=100)
    values = [Q(1) + Q(1, 2) ** j + Q(2, j + 3) for j in range(20)]
    s = Sequence(values, ctx)
    args = {'order': 3, 'beta': '2', 'remainder': 'u'}
    a = get('accelerators', 'levin_sidi_s')({**args, 'evaluation': 'direct'}).step(s, AlgoState(), ctx)
    b = get('accelerators', 'weniger')(args).step(Sequence(values, ctx), AlgoState(), ctx)
    assert abs(a.estimate - b.estimate) < ctx.number('1e-90')
