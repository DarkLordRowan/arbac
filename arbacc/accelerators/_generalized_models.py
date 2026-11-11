"""Shared direct collocation solver for explicit remainder models.

Barycentric and linear-system implementations have independent tests.
We never claim a result at requested order if the system is singular.
"""
from arbacc.core.stream import extend_partials
from arbacc.accelerators.direct import Levin


def pivot_tolerance(ctx,value='auto'):
    tol=ctx.number(f'1e-{max(12,ctx.dps//2)}') if str(value)=='auto' else ctx.number(str(value))
    b,d=ctx.backend,ctx.dps
    if not b.is_finite(tol,d) or b.sign(tol,d)<0:raise ValueError('invalid pivot_tol')
    return tol


def solve_linear(matrix,y,ctx,pivot_tol='auto'):
    b,d=ctx.backend,ctx.dps
    n=len(y)
    if n==0 or len(matrix)!=n or any(len(row)!=n for row in matrix):
        raise ValueError('square model matrix required')
    tol=pivot_tolerance(ctx,pivot_tol)
    work=[row[:]+[v] for row,v in zip(matrix,y)]
    one=ctx.number(1); zero=ctx.number(0)
    for col in range(n):
        pivot=col
        best=b.abs_val(work[col][col],d)
        for i in range(col+1,n):
            mag=b.abs_val(work[i][col],d)
            if b.sign(b.sub(mag,best,d),d)>0:pivot,best=i,mag
        if b.sign(best,d)==0:raise ArithmeticError(f'singular/uncertain model pivot column {col}')
        scale=best
        # Row scaling based on all remaining coefficients avoids accepting
        # tiny pivots produced by severe cancellation.
        for i in range(col,n):
            for j in range(col,n):
                mag=b.abs_val(work[i][j],d)
                if b.sign(b.sub(mag,scale,d),d)>0:scale=mag
        if b.sign(tol,d) and b.sign(b.sub(best,b.mul(tol,scale,d),d),d)<=0:
            raise ArithmeticError(f'ill-conditioned model pivot column {col}')
        if pivot!=col:work[pivot],work[col]=work[col],work[pivot]
        divisor=work[col][col]
        for j in range(col,n+1):work[col][j]=b.div(work[col][j],divisor,d)
        for i in range(n):
            if i==col:continue
            factor=work[i][col]
            if b.sign(factor,d)==0:continue
            for j in range(col,n+1):work[i][j]=b.sub(work[i][j],b.mul(factor,work[col][j],d),d)
            work[i][col]=zero
    solution=[work[i][-1] for i in range(n)]
    if not all(b.is_finite(v,d) for v in solution):raise ArithmeticError('nonfinite model estimate')
    return solution


def base_levin(params):
    return Levin({'order':params.get('order',2),
                  'beta':params.get('beta','1'),
                  'remainder':params.get('remainder','next')})


def build_levin_model(source,state,ctx,params,column_fn):
    base=base_levin(params)
    n=state.iteration;k=params.get('order',2)
    partials=extend_partials(source,state.extra.get('partials',[]),ctx,base.required_input(state))
    if not k:return partials[n],partials
    b,d=ctx.backend,ctx.dps
    beta=base.beta(ctx)
    rows=[]
    for j in range(k+1):
        idx=n+j
        inv=base.inverse_remainder(source,idx,ctx)
        if inv is None or b.sign(inv,d)==0:raise ArithmeticError('missing/zero remainder estimate')
        omega=b.div(ctx.number(1),inv,d)
        x=b.add(ctx.number(idx),beta,d)
        if b.sign(x,d)<=0:raise ArithmeticError('invalid n+beta grid')
        rows.append([ctx.number(1)]+[b.mul(omega,column_fn(x,r,ctx),d) for r in range(k)])
    return solve_linear(rows,partials[n:n+k+1],ctx,params.get('pivot_tol','auto'))[0],partials
