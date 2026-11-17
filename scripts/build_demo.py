"""Regenerate browser fixtures and the downloadable source archive."""
import csv,json,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from volatility_lab.core import analyze
from volatility_lab.data import demo
fixtures={}
for name in ('Balanced','Steep skew','Short-term stress'):
    d=demo(name);fixtures[name]=analyze(d['rows'],d['spot'],d['rate'],d['yield_rate'],max_spread=1)
(root/'dist/data.json').write_text(json.dumps(fixtures))
d=demo()
with (root/'examples/quotes.csv').open('w',newline='') as f:
    writer=csv.DictWriter(f,fieldnames=list(d['rows'][0]));writer.writeheader();writer.writerows(d['rows'])
(root/'examples/snapshot.json').write_text(json.dumps(dict(data=d,assumptions=dict(rate=.04,yield_rate=.01,max_spread=.3,min_oi=0)),indent=2))
# Exclude private hosting metadata, Git, runtime files and this zip itself.
files=['app.py','requirements.txt','README.md','LICENSE','.gitignore','.github/workflows/tests.yml','.streamlit/config.toml']
files += [str(p.relative_to(root)) for folder in ['volatility_lab','tests','scripts','examples'] for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts]
files += ['dist/'+x for x in ['index.html','style.css','app.js','data.json']]
with zipfile.ZipFile(root/'dist/volatility-lab-source.zip','w',zipfile.ZIP_DEFLATED) as z:
    for path in files: z.write(root/path,'volatility-lab/'+path)
print('Built demo fixtures, example CSV/snapshot, and source archive.')
