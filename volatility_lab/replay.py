"""Replay an exported snapshot without the network.
python -m volatility_lab.replay snapshot.json --output audit.csv
"""
import argparse,csv,json
from .core import analyze

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('snapshot');parser.add_argument('--output',default='audit.csv')
    args=parser.parse_args()
    with open(args.snapshot) as f: snapshot=json.load(f)
    d,a=snapshot['data'],snapshot['assumptions']
    rows=analyze(d['rows'],d['spot'],a['rate'],a['yield_rate'],a['max_spread'],a['min_oi'])
    columns=sorted(set().union(*(row.keys() for row in rows)))
    with open(args.output,'w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=columns);writer.writeheader();writer.writerows(rows)
    print(f'{len(rows)} audited quotes written to {args.output}')
if __name__=='__main__': main()
