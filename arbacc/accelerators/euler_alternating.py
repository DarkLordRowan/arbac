"""Euler transformation for alternating series; see Sidi (2003), section 15.2.

For terms a_n=(-1)^n b_n and s_{n-1}=sum_{j<n} a_j,
 s ~= s_{n-1} + sum_{k=0}^{K-1} 2^(-k-1) sum_{j=0}^k C(k,j) a_{n+j}.
The method is intended for regular alternating series, not arbitrary inputs.
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.core.stream import series_term
from arbacc.accelerators.direct import _partials


@register('accelerators', 'euler_alternating')
class EulerAlternating(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Sidi, Practical Extrapolation Methods (2003)', 'url': 'https://doi.org/10.1017/CBO9780511546815', 'locator': 'section 15.2 (Euler alternating-series transformation)', 'relation': 'literature_family', 'implementation_note': 'Alternating-series Euler transformation; restricted regularity assumptions.'}
    name = display_name = 'euler_alternating'
    PARAM_SPEC = {'order': {'type': 'int', 'default': 8, 'min': 0, 'short': 'k'}}

    def __init__(self, params=None):
        super().__init__(params)
        self.order = self.params.get('order', 8)
        if type(self.order) is not int or self.order < 0:
            raise ValueError('order must be a nonnegative integer')

    def required_input(self, state):
        return state.iteration + max(1, self.order)

    def step(self, source, state, ctx):
        b, d, n, k = ctx.backend, ctx.dps, state.iteration, self.order
        partials = _partials(source, state, ctx, self.required_input(state))
        if k == 0:
            estimate = partials[n]
        else:
            # Binomially weighted Euler tail. Pascal row and powers of 1/2 are
            # maintained in the selected backend (no binary64 conversion).
            terms = [series_term(source, n+i, ctx) for i in range(k)]
            half = b.div(ctx.number(1), ctx.number(2), d)
            weight = half
            euler_tail = ctx.number(0)
            coefficients = [1]
            for level in range(k):
                weighted = ctx.number(0)
                for j, c in enumerate(coefficients):
                    weighted = b.add(weighted, b.mul(ctx.number(c), terms[j], d), d)
                euler_tail = b.add(euler_tail, b.mul(weight, weighted, d), d)
                weight = b.mul(weight, half, d)
                coefficients = [1] + [coefficients[j-1]+coefficients[j] for j in range(1,len(coefficients))] + [1]
            prefix = partials[n-1] if n else ctx.number(0)
            estimate = b.add(prefix, euler_tail, d)
        if not b.is_finite(estimate,d):
            raise ArithmeticError('Nonfinite Euler estimate')
        result = state.with_estimate(estimate)
        result.extra['partials'] = partials
        result.extra['math_status'] = 'full_order'
        return result
