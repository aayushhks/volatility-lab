"""Atomic JSON storage for real Yahoo snapshots; never relabel example data."""
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from datetime import datetime

from .limits import MAX_QUOTES
from .core import analyze

MAX_SNAPSHOT_BYTES = 8 * 1024 * 1024


def snapshot_filename(symbol, expiries):
    key = f'{symbol.strip().upper()}\0{int(expiries)}'.encode()
    return sha256(key).hexdigest() + '.json'


def _safe_numbers(value):
    if isinstance(value, float) and not isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: _safe_numbers(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_safe_numbers(item) for item in value]
    return value


def validate_market_snapshot(data, symbol):
    if not isinstance(data, dict) or data.get('symbol') != symbol:
        raise ValueError('Snapshot ticker does not match the requested ticker.')
    if data.get('source') != 'Yahoo Finance via yfinance':
        raise ValueError('Only real Yahoo snapshots can enter the market cache.')
    spot = data.get('spot')
    if isinstance(spot, bool) or not isinstance(spot, (float, int)) or not isfinite(spot) or spot <= 0:
        raise ValueError('Invalid snapshot spot.')
    captured = datetime.fromisoformat(data['fetched_at'])
    if captured.tzinfo is None:
        raise ValueError('Snapshot capture time must include its timezone.')
    rows = data.get('rows')
    if not isinstance(rows, list) or not 0 < len(rows) <= MAX_QUOTES:
        raise ValueError('Invalid snapshot quote count.')
    required = {'strike', 'days', 'bid', 'ask', 'kind'}
    if any(not isinstance(row, dict) or not required.issubset(row) for row in rows):
        raise ValueError('Incomplete snapshot quote rows.')
    # An HTTP success with all-zero or impossible prices must not evict usable data.
    # Use the dashboard's initial assumptions; all rows remain in the quote audit.
    if not any(row['status'] == 'accepted' for row in
               analyze(rows, spot, .04, .01, .30, 0)):
        raise ValueError('Yahoo returned no usable bid/ask quotes. Keeping the last good snapshot.')
    return data


class SnapshotStore:
    def __init__(self, directory=None, archives=()):
        self.directory = Path(directory) if directory is not None else None
        self.archives = tuple(Path(path) for path in archives)

    def save(self, key, data):
        if self.directory is None:
            return
        symbol, expiries = key
        clean = _safe_numbers(data)
        validate_market_snapshot(clean, symbol)
        payload = json.dumps({'schema_version': 1, 'symbol': symbol,
                              'expiries': expiries, 'data': clean}, allow_nan=False)
        if len(payload.encode()) > MAX_SNAPSHOT_BYTES:
            raise ValueError('Snapshot exceeds the storage limit.')
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / snapshot_filename(*key)
        temporary = None
        try:
            with NamedTemporaryFile(mode='w', encoding='utf-8', dir=self.directory,
                                    prefix='.snapshot-', delete=False) as handle:
                temporary = handle.name
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        files = sorted(self.directory.glob('*.json'), key=lambda path: path.stat().st_mtime,
                       reverse=True)
        for old in files[8:]:
            old.unlink(missing_ok=True)

    def load(self, key):
        directories = ((self.directory,) if self.directory is not None else ()) + self.archives
        candidates = []
        for directory in directories:
            path = directory / snapshot_filename(*key)
            try:
                with path.open('rb') as handle:
                    payload = handle.read(MAX_SNAPSHOT_BYTES + 1)
                if len(payload) > MAX_SNAPSHOT_BYTES:
                    continue
                saved = json.loads(payload)
                if saved.get('schema_version') != 1 or (saved.get('symbol'), saved.get('expiries')) != key:
                    continue
                data = validate_market_snapshot(saved['data'], key[0])
                candidates.append(data)
            except (OSError, ValueError, KeyError, TypeError, AttributeError, OverflowError):
                continue
        if not candidates:
            return None
        return max(candidates, key=lambda data: datetime.fromisoformat(data['fetched_at']))
