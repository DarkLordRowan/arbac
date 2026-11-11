"""Sidi's polynomial d^(m) transformation by the DEFINING linear system.

A. Sidi, Practical Extrapolation Methods (2003), Definition 6.2.2, Eq. (6.2.3):
 A_R = d + sum_{k=1}^m R^k Delta^k A_{R-1}
                       * sum_{i=0}^{n_k-1} beta_{ki}/(R+alpha)^i.
For R=R_j,...,R_{j+N}, N=sum n_k, solve N+1 linear equations for d.

This is a high-precision DIRECT O(N^3) reference, not the more efficient
recursive Ford-Sidi W^(m) algorithm. The paper may report different stability
for W^(m); do not mislabel the direct solver as W^(m).

Index convention: input partials are A_1, A_2,...; A_0=0 in Sidi's
normalization. Input partials s[0],s[1],... correspond to A_1,A_2,... .
At start n=0, R starts at 1. Each column is sampled at R=n+ell+1.
"""
from math import comb
from arbacc.core.accelerator import AcceleratorBase
from arbacc.core.registry import register
from arbacc.accelerators.direct import _partials


def _orders(params, k, m):
    explicit = str(params.get('orders', '')).strip()
    if explicit:
        try:
            values = [int(item.strip()) for item in explicit.split(',')]
        except ValueError as error:
            raise ValueError('orders must be comma-separated nonnegative integers') from error
        if len(values) != m or any(x < 0 for x in values):
            raise ValueError('orders requires m nonnegative integers')
        if sum(values) != k:
            raise ValueError('sum(orders) must equal order')
        return values
    return [k//m + (1 if j < k%m else 0) for j in range(m)]


def _solve(matrix, rhs, ctx):
    """Gauss-Jordan with backend arithmetic, partial row pivoting by magnitude.

    Uncertain/zero pivot is treated as failure. No silent fallback to s[n+k].
    """
    b, d = ctx.backend, ctx.dps
    size = len(rhs)
    work = [row[:] + [rhs[j]] for j, row in enumerate(matrix)]
    zero = ctx.number(0)
    for col in range(size):
        pivot = col
        max_val = b.abs_val(work[col][col], d)
        for row in range(col+1, size):
            v = b.abs_val(work[row][col], d)
            if b.sign(b.sub(v, max_val, d), d) > 0:
                pivot, max_val = row, v
        if b.sign(work[pivot][col], d) == 0:
            raise ArithmeticError(f'Sidi d^(m) singular/uncertain pivot at column {col}')
        if pivot != col:
            work[col], work[pivot] = work[pivot], work[col]
        divisor = work[col][col]
        for j in range(col, size+1):
            work[col][j] = b.div(work[col][j], divisor, d)
        for i in range(size):
            if i == col:
                continue
            factor = work[i][col]
            if b.sign(factor, d) == 0:
                continue
            for j in range(col, size+1):
                work[i][j] = b.sub(work[i][j], b.mul(factor,work[col][j],d),d)
            work[i][col] = zero
    answer = work[0][-1]
    if not b.is_finite(answer, d):
        raise ArithmeticError('Nonfinite Sidi d^(m) estimate')
    return answer


@register('accelerators', 'sidi_d_m')
class SidiDM(AcceleratorBase):

    # Bibliographic provenance, not a claim of numerical equivalence.
    LITERATURE = {'citation': 'Sidi, Practical Extrapolation Methods: Theory and Applications (2003)', 'url': 'https://doi.org/10.1017/CBO9780511546815', 'locator': 'section 6.2', 'relation': 'literature_family', 'implementation_note': 'Direct d^(m) defining linear system, not optimized W^(m).'}
    name = display_name = 'sidi_d_m'
    PARAM_SPEC = {
        'order': {'type':'int','default':2,'min':0,'short':'N'},
        'm': {'type':'int','default':2,'min':1,'short':'m'},
        'alpha': {'type':'str','default':'0','short':'alpha'},
        'orders': {'type':'str','default':'','short':'orders'},
    }

    def __init__(self, params=None):
        super().__init__(params)
        self.order = self.params.get('order',2)
        self.m = self.params.get('m',2)
        if type(self.order) is not int or self.order < 0:
            raise ValueError('order must be a nonnegative integer')
        if type(self.m) is not int or self.m < 1:
            raise ValueError('m must be a positive integer')
        self.group_orders = _orders(self.params, self.order, self.m)
        self.active = max((j+1 for j,count in enumerate(self.group_orders) if count),default=0)

    def required_input(self,state):
        return state.iteration + self.order + max(1,self.active)

    def step(self,source,state,ctx):
        b,d,n,N = ctx.backend,ctx.dps,state.iteration,self.order
        alpha = ctx.number(self.params.get('alpha','0'))
        if not b.is_finite(alpha,d):
            raise ValueError('alpha must be finite')
        partials = _partials(source,state,ctx,self.required_input(state))
        if not N:
            result = state.with_estimate(partials[n])
            result.extra['partials'] = partials
            result.extra['math_status'] = 'identity_order_zero'
            return result
        matrix=[];rhs=[]
        # Samples indexed by Sidi's positive R, where A_0 = 0.
        for ell in range(N+1):
            R=n+ell+1
            r=ctx.number(R)
            shift=b.add(r,alpha,d)
            if b.sign(shift,d)==0:
                raise ArithmeticError('Sidi d^(m): singular R+alpha')
            inverse = b.div(ctx.number(1),shift,d)
            row=[ctx.number(1)]
            r_power=ctx.number(1)
            for degree in range(1,self.m+1):
                r_power = b.mul(r_power,r,d)
                count=self.group_orders[degree-1]
                if not count:
                    continue
                # Delta^k A_(R-1) = sum_{j=0}^k (-1)^{k-j} C(k,j) A_(R-1+j).
                # A_0=0; A_q=partials[q-1] for q>=1.
                difference=ctx.number(0)
                for j in range(degree+1):
                    q=R-1+j
                    value=partials[q-1] if q else ctx.number(0)
                    coefficient=(-1)**(degree-j)*comb(degree,j)
                    difference=b.add(difference,b.mul(ctx.number(coefficient),value,d),d)
                basis=b.mul(r_power,difference,d)
                weight=ctx.number(1)
                for _ in range(count):
                    row.append(b.mul(basis,weight,d))
                    weight=b.mul(weight,inverse,d)
            matrix.append(row)
            rhs.append(partials[R-1])
        if any(len(row)!=N+1 for row in matrix):
            raise RuntimeError('Sidi d^(m) basis dimension mismatch')
        estimate=_solve(matrix,rhs,ctx)
        result=state.with_estimate(estimate)
        result.extra['partials']=partials
        result.extra['math_status']='full_order'
        result.extra['group_orders']=self.group_orders[:]
        return result
