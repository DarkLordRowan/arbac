from arbacc.precision import get_backend
from arbacc.core import Context, register, AcceleratorBase, AlgoState, list_registered

# 1. Backend и Context
backend = get_backend("mpmath")
ctx = Context(backend=backend, dps=50)
x = ctx.number("1.2345678901234567890123456789")
print("Context:", ctx)
print("Number: ", backend.to_str(x, 50))

# 2. Реестр: регистрируем фиктивный акселератор
@register("accelerators", "dummy")
class Dummy(AcceleratorBase):
    def required_input(self, state):
        return 1
    def step(self, source, state, ctx):
        return state.with_estimate(source.get(0))

print("Registry:", list_registered())

# 3. digits_of
pi_approx = ctx.number("3.14159")
pi_exact  = ctx.number("3.14159265358979323846")
print("Digits gained:", backend.digits_of(pi_approx, pi_exact, 50))