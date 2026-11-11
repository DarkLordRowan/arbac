"""Conservative rank guard for Shanks' determinant formula.

No new transform is defined here: the algebraic Shanks numerator/denominator
remain in direct.py. The guard only assesses the annihilation system rank.

A rank decision based on finite precision is diagnostic, not a proof of exact
singularity. Flag 'lower_order' whenever the requested rank is unresolved.
"""


def _sign_cmp(a, b, ctx):
    ops, dps = ctx.backend, ctx.dps
    return ops.sign(ops.sub(a, b, dps), dps)


def _well_resolved_rank(matrix, ctx):
    """True only if scaled elimination resolves every pivot at working dps.

    Row equilibration handles very small exponential differences without
    incorrectly declaring them zero from absolute magnitude alone.
    A conservative half-precision threshold rejects near-rank deficiencies.
    """
    b, d = ctx.backend, ctx.dps
    if not matrix or any(len(row) != len(matrix) for row in matrix):
        return False
    n = len(matrix)
    zero = ctx.number(0)
    threshold = ctx.number('1e-' + str(max(12, d // 2)))
    a = []
    for row in matrix:
        scale = zero
        for value in row:
            if not b.is_finite(value, d):
                return False
            mag = b.abs_val(value, d)
            if _sign_cmp(mag, scale, ctx) > 0:
                scale = mag
        if b.sign(scale, d) <= 0:
            return False
        a.append([b.div(v, scale, d) for v in row])
    for col in range(n):
        best = col
        for i in range(col + 1, n):
            if _sign_cmp(b.abs_val(a[i][col], d), b.abs_val(a[best][col], d), ctx) > 0:
                best = i
        pivot_abs = b.abs_val(a[best][col], d)
        if not b.is_finite(pivot_abs, d) or _sign_cmp(pivot_abs, threshold, ctx) <= 0:
            return False
        if best != col:
            a[best], a[col] = a[col], a[best]
        pivot = a[col][col]
        if b.sign(pivot, d) == 0:
            return False
        for i in range(col + 1, n):
            factor = b.div(a[i][col], pivot, d)
            for j in range(col + 1, n):
                a[i][j] = b.sub(a[i][j], b.mul(factor, a[col][j], d), d)
            a[i][col] = zero
    return True


def shanks_guarded(s, n, order, ctx, determinant):
    """Return (estimate, achieved_order, status, failure_reason).

    Estimate is the *unchanged determinant ratio* at resolved order; if that
    order is not well conditioned, try lower orders. If none qualifies,
    return the final available raw sample explicitly tagged as fallback.
    """
    b, d = ctx.backend, ctx.dps
    if order == 0:
        return s[n], 0, 'identity_order_zero', ''
    failure = 'requested_order_numerically_rank_deficient'
    for k in range(order, 0, -1):
        common = [
            [b.sub(s[n + j + r], s[n + j], d) for j in range(k + 1)]
            for r in range(1, k + 1)
        ]
        matrix = [[ctx.number(1)] * (k + 1)] + common
        if not _well_resolved_rank(matrix, ctx):
            continue
        den = determinant(matrix, ctx)
        if den is None or b.sign(den, d) == 0:
            continue
        num = determinant([s[n:n + k + 1]] + common, ctx)
        if num is None:
            continue
        estimate = b.div(num, den, d)
        if not b.is_finite(estimate, d):
            continue
        if k == order:
            return estimate, k, 'full_order', ''
        return estimate, k, 'lower_order_singular', failure
    return s[n + 2 * order], 0, 'singular_fallback_raw', failure
