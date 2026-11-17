"""European Black–Scholes–Merton pricing and auditable IV inversion.
Rates and volatilities are decimals; maturity is ACT/365 years.
No dependency on the web UI or market data provider.
"""
from math import erf, exp, isfinite, log, sqrt, pi

def _validate(s, k, t, r, q):
    if not all(isfinite(float(x)) for x in (s,k,t,r,q)) or min(s,k,t) <= 0:
        raise ValueError('Spot, strike and maturity must be positive and all inputs finite.')

def cdf(x):
    return 0.5 * (1 + erf(x / sqrt(2)))

def bounds(s, k, t, r, q=0.0, kind='call'):
    _validate(s,k,t,r,q)
    if kind not in ('call','put'): raise ValueError('kind must be call or put')
    a,b = s*exp(-q*t), k*exp(-r*t)
    return (max(a-b,0),a) if kind=='call' else (max(b-a,0),b)

def price(s, k, t, r, sigma, q=0.0, kind='call'):
    low,_ = bounds(s,k,t,r,q,kind)
    if not isfinite(sigma) or sigma < 0: raise ValueError('Volatility must be finite and nonnegative.')
    if sigma == 0: return low
    d1=(log(s/k)+(r-q+sigma*sigma/2)*t)/(sigma*sqrt(t))
    d2=d1-sigma*sqrt(t)
    a,b=s*exp(-q*t),k*exp(-r*t)
    return a*cdf(d1)-b*cdf(d2) if kind=='call' else b*cdf(-d2)-a*cdf(-d1)

def vega(s,k,t,r,sigma,q=0.0):
    _validate(s,k,t,r,q)
    if sigma<=0 or not isfinite(sigma): raise ValueError('Volatility must be positive.')
    d1=(log(s/k)+(r-q+sigma*sigma/2)*t)/(sigma*sqrt(t))
    return s*exp(-q*t)*exp(-d1*d1/2)/sqrt(2*pi)*sqrt(t)

def implied_vol(p,s,k,t,r,q=0.0,kind='call',tol=1e-8,max_iter=160):
    """Bracketed bisection, capped at 500% vol. Refuse boundaries/invalid prices.
    A price close to intrinsic has an ill-conditioned IV; return a reason,
    rather than silently reporting 0% or the solver bound.
    """
    low,high=bounds(s,k,t,r,q,kind)
    if not isfinite(p): raise ValueError('Non-finite price')
    if p <= low+tol or p >= high-tol: raise ValueError('Price outside strict European bounds or at boundary')
    a,b=1e-6,5.0
    if price(s,k,t,r,b,q,kind)<p: raise ValueError('IV exceeds 500% solver cap')
    for _ in range(max_iter):
        mid=(a+b)/2
        err=price(s,k,t,r,mid,q,kind)-p
        if abs(err)<=tol: return mid
        if err>0: b=mid
        else: a=mid
    raise ValueError('IV solver did not converge')

def analyze(rows,spot,rate,yield_rate,max_spread=0.30,min_oi=0):
    """Retain each quote with accepted/rejected status and an explicit reason.
    Input columns: strike, days, bid, ask, kind, open_interest (optional).
    No last-trade fallback; bid/ask midpoint only. No extrapolation.
    """
    result=[]
    for original in rows:
        row=dict(original)
        try:
            k,d,b,a=[float(row[n]) for n in ('strike','days','bid','ask')]
            oi=float(row.get('open_interest',0) or 0)
            kind=row.get('kind','call')
            if not all(isfinite(x) for x in (k,d,b,a,oi)): raise ValueError('Missing/non-finite quote')
            if k<=0 or d<=0: raise ValueError('Invalid strike or expired quote')
            if b<=0 or a<=0: raise ValueError('Zero/negative bid or ask')
            if a<b: raise ValueError('Crossed bid/ask')
            mid=(a+b)/2
            spread=(a-b)/mid
            if spread>max_spread: raise ValueError('Spread exceeds threshold')
            if oi<min_oi: raise ValueError('Open interest below threshold')
            iv=implied_vol(mid,spot,k,d/365,rate,yield_rate,kind)
            if vega(spot,k,d/365,rate,iv,yield_rate)<0.01:
                raise ValueError('Vega too small for stable IV (below 0.01)')
            row.update(mid=mid,relative_spread=spread,iv=iv,moneyness=k/spot,
                       repricing_error=abs(price(spot,k,d/365,rate,iv,yield_rate,kind)-mid),
                       status='accepted',reason='')
        except (ValueError,TypeError,KeyError,OverflowError) as exc:
            row.update(status='rejected',reason=str(exc),iv=None)
        result.append(row)
    return result
