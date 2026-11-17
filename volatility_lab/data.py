"""Synthetic fixtures and an optional Yahoo Finance adapter."""
from datetime import datetime, timezone
from math import log, sqrt
from .core import price
from .limits import MAX_QUOTES

def demo(name='Balanced'):
    """Deterministic synthetic European quotes, NOT historical/live prices."""
    level,skew,curve={'Balanced':(.24,-.12,.65),'Steep skew':(.30,-.35,.80),'Short-term stress':(.25,-.17,.60)}[name]
    spot,rate,q=100.,.04,.01
    rows=[]
    for days in (14,30,60,90,180,270,365):
        t=days/365
        for strike in range(70,136,5):
            x=log(strike/spot)
            sigma=level+skew*x+curve*x*x+(.12/(1+12*t) if name=='Short-term stress' else .025*sqrt(t))
            for kind in ('call','put'):
                p=price(spot,strike,t,rate,sigma,q,kind)
                width=max(.01,p*.025)
                rows.append(dict(strike=strike,days=days,bid=max(0,p-width),ask=p+width,kind=kind,open_interest=500,known_iv=sigma))
    # Deliberately bad quotes demonstrate the quality audit.
    rows.extend([dict(strike=100,days=45,bid=6,ask=5,kind='call',open_interest=100),
                 dict(strike=100,days=45,bid=0,ask=4,kind='call',open_interest=100),
                 dict(strike=100,days=45,bid=1,ask=8,kind='put',open_interest=100)])
    return dict(symbol='DEMO',scenario=name,spot=spot,rate=rate,yield_rate=q,source='Synthetic European options; not market data',rows=rows)

def fetch_yahoo(symbol,max_expiries=8):
    import yfinance as yf
    ticker=yf.Ticker(symbol)
    hist=ticker.history(period='5d',auto_adjust=False)
    if hist.empty: raise ValueError('No underlying prices returned for this ticker.')
    spot=float(hist['Close'].dropna().iloc[-1])
    now=datetime.now(timezone.utc)
    expiries=ticker.options[:max_expiries]
    if not expiries: raise ValueError('No listed option expiries returned.')
    rows=[]
    errors=[]
    for expiry in expiries:
        try:
            chain=ticker.option_chain(expiry)
            # Approximate expiry at 16:00 US/Eastern, honoring DST.
            from zoneinfo import ZoneInfo
            end=datetime.strptime(expiry,'%Y-%m-%d').replace(hour=16,tzinfo=ZoneInfo('America/New_York'))
            days=(end-now).total_seconds()/86400
            if days<=0: continue
            for kind,frame in [('call',chain.calls),('put',chain.puts)]:
                for _,row in frame.iterrows():
                    if len(rows)>=MAX_QUOTES:
                        raise ValueError('Quote limit reached (20,000); request fewer expiries.')
                    rows.append(dict(strike=float(row['strike']),days=days,bid=float(row['bid']),ask=float(row['ask']),kind=kind,
                        open_interest=float(row.get('openInterest',0)),expiry=expiry,last_trade=str(row.get('lastTradeDate',''))))
        except Exception as exc:
            errors.append(f'{expiry}: {type(exc).__name__}: {exc}')
    if not rows: raise ValueError('Provider returned no usable chains. '+ '; '.join(errors))
    return dict(symbol=symbol,spot=spot,rows=rows,source='Yahoo Finance via yfinance',
        fetched_at=now.isoformat(),spot_timestamp=str(hist.index[-1]),errors=errors)
