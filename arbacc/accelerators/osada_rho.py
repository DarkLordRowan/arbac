"""Osada's generalized rho algorithm (1990), SIAM J. Numer. Anal. 27:178-189.

Eq. (3.1): rho[-1,n]=0, rho[0,n]=s[n],
 rho[j,n]=rho[j-2,n+1]+(j-1-alpha)/(rho[j-1,n+1]-rho[j-1,n]).
At alpha=-1 this is the classical rho recurrence with unit-spaced nodes.

Unlike some legacy transforms, singularity is explicitly reported, not replaced
by a lower-order estimate. Requires 2*k+1 values for rho[2*k,n].
"""
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import _partials


@register('accelerators', 'osada_generalized_rho')
class OsadaGeneralizedRho(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Osada, A convergence acceleration method for some logarithmically convergent sequences, SIAM J. Numer. Anal. 27 (1990), 178-189', 'url': 'https://doi.org/10.1137/0727012', 'locator': 'Eq. (3.1)', 'relation': 'literature_family', 'implementation_note': 'Generalized rho, including parameter specialization to classical rho.'}
    name = display_name = 'osada_generalized_rho'
    PARAM_SPEC = {
        'order': {'type': 'int', 'default': 2, 'min': 0, 'short': 'k'},
        'alpha': {'type': 'str', 'default': '-1', 'short': 'alpha'},
    }

    def __init__(self, params=None):
        super().__init__(params)
        self.order = self.params.get('order', 2)
        if type(self.order) is not int or self.order < 0:
            raise ValueError('order must be a nonnegative integer')

    def required_input(self, state):
        return state.iteration + 2 * self.order + 1

    def step(self, source, state, ctx):
        b, d, n, k = ctx.backend, ctx.dps, state.iteration, self.order
        alpha = ctx.number(self.params.get('alpha', '-1'))
        if not b.is_finite(alpha, d):
            raise ValueError('Osada alpha must be finite')
        count = self.required_input(state)
        s = _partials(source, state, ctx, count)
        previous = [ctx.number(0)] * (2*k + 2)
        current = s[n:n + 2*k + 1]
        for j in range(1, 2*k + 1):
            factor = b.sub(ctx.number(j-1), alpha, d)
            following = []
            for i in range(len(current)-1):
                delta = b.sub(current[i+1], current[i], d)
                if b.sign(delta, d) == 0:
                    raise ArithmeticError(f'Osada singular rho table: column={j}, row={i}')
                value = b.add(previous[i+1], b.div(factor, delta, d), d)
                if not b.is_finite(value, d):
                    raise ArithmeticError('Nonfinite Osada rho cell')
                following.append(value)
            previous, current = current, following
        result = state.with_estimate(current[0])
        result.extra['partials'] = s
        result.extra['math_status'] = 'full_order'
        return result
