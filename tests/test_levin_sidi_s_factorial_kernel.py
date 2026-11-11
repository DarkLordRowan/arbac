"""Independent exact-model oracle for the implemented factorial quotient.

This checks a mathematical kernel property. It does NOT establish historical
attribution or equivalence to every construction called Sidi's S-transform.
"""
from fractions import Fraction as F
from math import comb

import mpmath as mp
import pytest

import arbacc.accelerators  # noqa: F401: register all accelerators
from arbacc.core import AlgoState, Context, get
from arbacc.precision import get_backend


def rising(x, length):
    result = F(1)
    for j in range(length):
        result *= x + j
    return result


def exact_model_sequence(k, beta, length, target=F(7, 5)):
    """Create s_n obeying s_n = target + omega_n * sum(c_j/(n+beta)_j).

    omega_0=s_0, omega_n=s_n-s_(n-1) for n>=1, matching the
    source-kind=sequence / remainder='t' convention in Arbac.
    """
    coeffs = [F((-1)**j, 10*(j+1)) for j in range(k)]

    def f(n):
        return sum((coeffs[j] / rising(beta+n, j) for j in range(k)), F(0))

    seq = [target / (1-f(0))]
    for n in range(1, length):
        seq.append((target - f(n)*seq[-1]) / (1-f(n)))
    for n, s in enumerate(seq):
        omega = s if n == 0 else s - seq[n-1]
        assert s - target == f(n)*omega
    return seq, target


class ExactSequence:
    kind = 'sequence'
    def __init__(self, values, context):
        with mp.workdps(130):
            self.values = [context.number(mp.nstr(
                mp.mpf(v.numerator) / v.denominator, 115
            )) for v in values]
        self.length = 0

    def get(self, n):
        self.extend_to(n)
        return self.values[n]

    def extend_to(self, n):
        if not 0 <= n < len(self.values):
            raise IndexError(n)
        self.length = max(self.length, n+1)

    def __len__(self):
        return self.length


@pytest.mark.parametrize('beta', [F(3, 2), F(2)])
@pytest.mark.parametrize('k', [1, 2, 3, 4])
@pytest.mark.parametrize('n', [0, 1, 2])
def test_factorial_kernel_exact_recovery(beta, k, n):
    values, target = exact_model_sequence(k, beta, n+k+5)
    ctx = Context(backend=get_backend('mpmath'), dps=100)
    source = ExactSequence(values, ctx)
    method = get('accelerators', 'levin_sidi_s')({
        'order': k, 'beta': str(beta.numerator) if beta.denominator == 1 else '1.5',
        'remainder': 't', 'evaluation': 'direct'
    })
    state = method.step(source, AlgoState(iteration=n), ctx)
    assert abs(state.estimate - ctx.number('1.4')) < ctx.number('1e-83')
    # Verify the input count is not falsely understated.
    assert len(source) >= n + k + 1


def test_fraction_kernel_annihilation_independently():
    k, n, beta = 3, 1, F(2)
    values, target = exact_model_sequence(k, beta, 12)
    weights = []
    for j in range(k+1):
        index = n+j
        omega = values[index] - values[index-1]
        weights.append(F((-1)**j * comb(k,j)) * rising(beta+index,k-1) / omega)
    assert sum(weights) != 0
    assert sum((weights[j] * values[n+j] for j in range(k+1)), F(0)) == target * sum(weights)
