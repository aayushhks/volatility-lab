"""Cross-sectional holdout evaluation; never a forecast or trading backtest."""
from collections import defaultdict
from math import sqrt
from random import Random
from statistics import median
from .core import price


def evaluate(rows, spot, rate, yield_rate, seed=42):
    """Hold out interior strikes by expiry, keeping both endpoints in training.
    Input is one option side, already filtered by analyze(). Duplicate strikes
    stay together to avoid leakage. Predictions use training IVs only.
    """
    groups = defaultdict(lambda: defaultdict(list))
    for row in rows:
        if row.get('status') == 'accepted':
            groups[float(row['days'])][float(row['strike'])].append(row)
    rng = Random(seed)
    training, testing, curves = [], [], {}
    skipped = 0
    for days, strikes in sorted(groups.items()):
        keys = sorted(strikes)
        if len(keys) < 5:
            skipped += sum(map(len, strikes.values()))
            continue
        held = set(rng.sample(keys[1:-1], max(1, len(keys)//5)))
        curve = []
        for strike in keys:
            bucket = strikes[strike]
            if strike in held:
                testing.extend(bucket)
            else:
                training.extend(bucket)
                curve.append((strike, median(r['iv'] for r in bucket)))
        curves[days] = curve
    if not testing:
        raise ValueError('Need at least five distinct accepted strikes in one expiry for this option side.')
    global_iv = median(r['iv'] for r in training)
    predictions = []
    for row in testing:
        k, d = float(row['strike']), float(row['days'])
        curve = curves[d]
        left = max((p for p in curve if p[0] < k), key=lambda p:p[0])
        right = min((p for p in curve if p[0] > k), key=lambda p:p[0])
        linear = left[1] + (right[1]-left[1])*(k-left[0])/(right[0]-left[0])
        for method, iv in [('Global constant IV', global_iv),
                           ('Expiry constant IV', median(p[1] for p in curve)),
                           ('Linear smile interpolation', linear)]:
            predicted = price(spot,k,d/365,rate,iv,yield_rate,row['kind'])
            predictions.append(dict(method=method,strike=k,days=d,kind=row['kind'],
                observed_mid=row['mid'],predicted_price=predicted,predicted_iv=iv,
                observed_iv=row['iv'],price_error=predicted-row['mid'],
                iv_error_bp=(iv-row['iv'])*10000,
                within_spread=row['bid'] <= predicted <= row['ask']))
    summary=[]
    for method in dict.fromkeys(p['method'] for p in predictions):
        subset=[p for p in predictions if p['method']==method]
        n=len(subset)
        summary.append(dict(method=method,test_quotes=n,
            price_mae=sum(abs(p['price_error']) for p in subset)/n,
            price_rmse=sqrt(sum(p['price_error']**2 for p in subset)/n),
            iv_mae_bp=sum(abs(p['iv_error_bp']) for p in subset)/n,
            within_spread_pct=100*sum(p['within_spread'] for p in subset)/n))
    return dict(seed=seed,train_quotes=len(training),test_quotes=len(testing),
                skipped_quotes=skipped,summary=summary,predictions=predictions)
