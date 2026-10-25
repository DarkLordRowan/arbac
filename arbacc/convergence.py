"""Convergence diagnostics ported from the TypeScript convergenceUtils module.

Source: shanks-university/frontend/web/frontend/src/widgets/
AlgorithmSeriesConvergenceTable/model/convergenceUtils.ts (Magister).
These describe a finite trajectory; they do not prove convergence.
Unlike the browser version, values and deviations retain backend precision.
"""


def analyze_convergence(points, limit, ctx, *, tolerance="0",
                        max_sign_changes=0, max_violations=0):
    """Analyze {n, value:{re,im}, deviation?} points, sorted by n.

    A stored signed real deviation takes priority over rounded values.
    Missing/non-finite points are skipped, as in the TypeScript implementation.
    tolerance is an absolute tolerance in backend precision (zero by default).
    """
    b, d = ctx.backend, ctx.dps
    tol = ctx.number(tolerance)
    if not b.is_finite(tol,d) or b.sign(tol,d)<0:
        raise ValueError("tolerance must be finite and nonnegative")
    for count in (max_sign_changes,max_violations):
        if isinstance(count,bool) or not isinstance(count,int) or count<0:
            raise ValueError("violation allowances must be nonnegative integers")

    def finite(value):
        if value is None:
            return None
        number = ctx.number(value)
        return number if b.is_finite(number,d) else None

    def component(value, key):
        return finite(value.get(key,0)) if value else None

    errors, signs = [], []
    real_limit = component(limit,"re")
    imag_limit = component(limit,"im")
    for point in sorted(points,key=lambda p:p["n"]):
        deviation = finite(point.get("deviation"))
        error, difference = None, None
        if deviation is not None:
            error, difference = b.abs_val(deviation,d), deviation
        elif real_limit is not None and imag_limit is not None:
            value=point.get("value")
            re, im = component(value,"re"), component(value,"im")
            if re is not None and im is not None:
                difference=b.sub(re,real_limit,d)
                imaginary=b.sub(im,imag_limit,d)
                error=b.pow(b.add(b.mul(difference,difference,d),b.mul(imaginary,imaginary,d),d),ctx.number("0.5"),d)
        if error is not None:
            errors.append((point["n"],error))
        if difference is not None and b.sign(b.sub(b.abs_val(difference,d),tol,d),d)>0:
            signs.append((point["n"],b.sign(difference,d)))
    changes=[signs[i][0] for i in range(1,len(signs)) if signs[i][1]!=signs[i-1][1]]
    increases, decreases, equalities = [], [], 0
    for i in range(1,len(errors)):
        difference=b.sub(errors[i][1],errors[i-1][1],d)
        if b.sign(b.sub(b.abs_val(difference,d),tol,d),d)<=0:
            equalities+=1
        elif b.sign(difference,d)>0:
            increases.append(errors[i][0])
        else:
            decreases.append(errors[i][0])
    steps=max(0,len(errors)-1)
    if not steps:
        monotonicity="unknown"
    elif not increases and not decreases:
        monotonicity="constant_error"
    elif decreases and not increases:
        monotonicity="non_increasing_error" if equalities else "strict_decreasing_error"
    elif increases and not decreases:
        monotonicity="non_decreasing_error" if equalities else "strict_increasing_error"
    elif len(increases)<=max_violations:
        monotonicity="non_increasing_error"
    elif steps-len(increases)<=max_violations:
        monotonicity="non_decreasing_error"
    else:
        monotonicity="random_error"
    side="unknown" if not signs and not steps else ("one_sided" if len(changes)<=max_sign_changes else "two_sided")
    return {"side":side,"monotonicity":monotonicity,"steps_analyzed":steps,
            "sign_changes_count":len(changes),"violations_count":len(increases),
            "sign_change_ns":changes,"violations_ns":increases,"errors":errors}
