"""Homeier F, H and pJ transformations, all arithmetic in the selected backend.

Primary source: https://arxiv.org/pdf/math/0005209, Eqs. (98), (107), (148),
(155). Independent tests use divided differences, annihilating polynomials,
and the original generalized-difference J scheme, respectively.
"""
from arbacc.core.registry import register
from arbacc.accelerators.direct import Levin,_partials


class _Homeier(Levin):
    def span(self):return self.order

    def required_input(self,state):
        lookahead={'next':1,'t':0,'u':0,'v':1,'v_shift':2}[self.remainder]
        return state.iteration+self.span()+1+(lookahead if self.order else 0)

    def initial_scale(self,index,ctx):return ctx.number(1)

    def reduce(self,num,den,n,ctx):raise NotImplementedError

    def validate(self,ctx):self.beta(ctx)

    def step(self,source,state,ctx):
        self.validate(ctx)
        b,d,n=ctx.backend,ctx.dps,state.iteration
        s=_partials(source,state,ctx,n+self.span()+1)
        estimate=s[n+self.span()]
        if not self.order:estimate=s[n]
        else:
            num,den=[],[]
            for index in range(n,n+self.span()+1):
                inverse=self.inverse_remainder(source,index,ctx)
                if inverse is None:break
                weight=b.mul(inverse,self.initial_scale(index,ctx),d)
                den.append(weight);num.append(b.mul(weight,s[index],d))
            else:
                self.reduce(num,den,n,ctx)
                if b.sign(den[0],d) and b.is_finite(num[0],d) and b.is_finite(den[0],d):
                    estimate=b.div(num[0],den[0],d)
        result=state.with_estimate(estimate)
        result.extra['partials']=s
        return result


@register('accelerators','homeier_f')
class HomeierF(_Homeier):
    name=display_name='homeier_f'
    PARAM_SPEC={**Levin.PARAM_SPEC,
        'grid_shift':{'type':'str','default':'4','short':'shift'},
        'grid_scale':{'type':'str','default':'1','short':'scale'},
        'grid_power':{'type':'int','default':1,'min':1,'short':'power'}}

    def __init__(self,params=None):
        super().__init__(params)
        self.power=self.params.get('grid_power',1)
        if isinstance(self.power,bool) or not isinstance(self.power,int) or self.power<1:
            raise ValueError('grid_power must be a positive integer')

    def validate(self,ctx):
        super().validate(ctx)
        b,d=ctx.backend,ctx.dps
        shift=ctx.number(self.params.get('grid_shift','4'))
        scale=ctx.number(self.params.get('grid_scale','1'))
        if not b.is_finite(shift,d) or not b.is_finite(scale,d) or b.sign(b.sub(shift,ctx.number(1),d),d)<=0 or b.sign(scale,d)<=0:
            raise ValueError('F grid requires finite shift>1 and scale>0')

    def node(self,index,ctx):
        b,d=ctx.backend,ctx.dps
        return b.add(ctx.number(self.params.get('grid_shift','4')),
            b.mul(ctx.number(self.params.get('grid_scale','1')),b.pow(ctx.number(index),ctx.number(self.power),d),d),d)

    def initial_scale(self,index,ctx):
        return ctx.backend.div(ctx.number(1),ctx.backend.sub(self.node(index,ctx),ctx.number(1),ctx.dps),ctx.dps)

    def reduce(self,num,den,n,ctx):
        b,d=ctx.backend,ctx.dps
        nodes=[self.node(i,ctx) for i in range(n,n+self.order+1)]
        for level in range(1,self.order+1):
            for j in range(self.order-level+1):
                left=b.add(nodes[j+level],ctx.number(level-2),d)
                right=b.add(nodes[j],ctx.number(level-2),d)
                difference=b.sub(nodes[j+level],nodes[j],d)
                if b.sign(difference,d)<=0:raise ValueError('F grid nodes must be provably distinct and increasing')
                for row in (num,den):
                    row[j]=b.div(b.sub(b.mul(left,row[j+1],d),b.mul(right,row[j],d),d),difference,d)


@register('accelerators','homeier_h')
class HomeierH(_Homeier):
    name=display_name='homeier_h'
    PARAM_SPEC={**Levin.PARAM_SPEC,'alpha':{'type':'str','default':'pi/4','short':'a'}}

    def span(self):return 2*self.order

    def validate(self,ctx):
        super().validate(ctx)
        b,d=ctx.backend,ctx.dps
        alpha=self.angle(ctx)
        if not b.is_finite(alpha,d):raise ValueError('alpha must be finite')
        cosine=b.cos(alpha,d)
        if b.sign(b.sub(cosine,ctx.number(1),d),d)==0 or b.sign(b.add(cosine,ctx.number(1),d),d)==0:
            raise ValueError('cos(alpha) must differ from +1 and -1')

    def angle(self,ctx):
        value=self.params.get('alpha','pi/4')
        if value=='pi/4':return ctx.backend.div(ctx.backend.pi(ctx.dps),ctx.number(4),ctx.dps)
        return ctx.number(value)

    def cosine(self,ctx):
        return ctx.backend.cos(self.angle(ctx),ctx.dps)

    def initial_scale(self,index,ctx):
        b,d=ctx.backend,ctx.dps
        return b.div(ctx.number(1),b.add(ctx.number(index),self.beta(ctx),d),d)

    def reduce(self,num,den,n,ctx):
        b,d,beta=ctx.backend,ctx.dps,self.beta(ctx)
        twice=b.mul(ctx.number(2),self.cosine(ctx),d)
        for level in range(1,self.order+1):
            for j in range(2*(self.order-level)+1):
                left=b.add(ctx.number(n+j),beta,d)
                middle=b.add(ctx.number(n+j+2*level),beta,d)
                right=b.mul(twice,b.add(ctx.number(n+j+level),beta,d),d)
                for row in (num,den):
                    row[j]=b.sub(b.add(b.mul(left,row[j],d),b.mul(middle,row[j+2],d),d),b.mul(right,row[j+1],d),d)


@register('accelerators','homeier_pj')
class HomeierPJ(_Homeier):
    name=display_name='homeier_pj'
    PARAM_SPEC={**Levin.PARAM_SPEC,'p':{'type':'int','default':2,'min':1,'short':'p'}}

    def __init__(self,params=None):
        super().__init__(params)
        self.p=self.params.get('p',2)
        if isinstance(self.p,bool) or not isinstance(self.p,int) or self.p<1:
            raise ValueError('p must be a positive integer')

    def psi(self,index,level,ctx):
        b,d=ctx.backend,ctx.dps
        value=ctx.number(1)
        start=b.add(ctx.number(index+level-1),self.beta(ctx),d)
        for m in range(level):
            top=b.add(start,ctx.number((self.p-2)*m),d)
            bottom=b.add(top,ctx.number(2),d)
            value=b.mul(value,b.div(top,bottom,d),d)
        return value

    def reduce(self,num,den,n,ctx):
        b,d=ctx.backend,ctx.dps
        for level in range(1,self.order+1):
            for j in range(self.order-level+1):
                coefficient=self.psi(n+j,level-1,ctx)
                for row in (num,den):row[j]=b.sub(row[j+1],b.mul(coefficient,row[j],d),d)
