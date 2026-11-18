"""Reproduce the synthetic benchmark: python scripts/evaluate_surface.py."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from volatility_lab.core import analyze
from volatility_lab.data import demo
from volatility_lab.research import evaluate

reports=[]
for scenario in ['Balanced','Steep skew','Short-term stress']:
    raw=demo(scenario)
    rows=[r for r in analyze(raw['rows'],raw['spot'],raw['rate'],raw['yield_rate']) if r['kind']=='call']
    for seed in [7,42,2026]:
        result=evaluate(rows,raw['spot'],raw['rate'],raw['yield_rate'],seed)
        result.pop('predictions')
        reports.append(dict(scenario=scenario,**result))
print(json.dumps(reports,indent=2))
