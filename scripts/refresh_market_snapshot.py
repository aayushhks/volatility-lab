"""Capture real Yahoo quotes for cold starts; never overwrite a good file on failure."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from volatility_lab.data import fetch_yahoo
from volatility_lab.snapshots import SnapshotStore


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--symbol', default='SPY')
    parser.add_argument('--expiries', type=int, default=3)
    parser.add_argument('--output', type=Path, default=ROOT / 'examples' / 'market')
    args = parser.parse_args()
    symbol = args.symbol.strip().upper()
    if not symbol or not 1 <= args.expiries <= 12:
        parser.error('Use a ticker and 1–12 expiries.')
    try:
        data = fetch_yahoo(symbol, args.expiries)
        SnapshotStore(args.output).save((symbol, args.expiries), data)
    except Exception as exc:
        print(f'Yahoo snapshot not refreshed: {exc}. Existing snapshots were left unchanged.')
        return
    print(f"Saved {symbol}: {len(data['rows'])} quotes, captured {data['fetched_at']}.")


if __name__ == '__main__':
    main()
