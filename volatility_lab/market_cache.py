"""Bounded snapshot cache with nonblocking refresh and last-good retention."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock, Thread
from time import monotonic

from .snapshots import SnapshotStore, validate_market_snapshot


class MarketCache:
    def __init__(self, fetch, clock=monotonic, cache_dir=None, archives=()):
        self.fetch, self.clock = fetch, clock
        self.cache = OrderedDict()
        self.lock = Lock()
        self.retry_at = 0
        self.store = SnapshotStore(cache_dir, archives)
        self.inflight = None
        self.generation = 0
        self.errors = OrderedDict()
        self.storage_error = None

    @staticmethod
    def _key(symbol, expiries):
        return symbol.strip().upper(), int(expiries)

    def _remember(self, key, data, saved):
        self.cache[key] = (saved, deepcopy(data))
        self.cache.move_to_end(key)
        while len(self.cache) > 8:
            self.cache.popitem(last=False)

    def peek(self, symbol, expiries):
        """Return the last good snapshot immediately, even after its refresh TTL."""
        key = self._key(symbol, expiries)
        with self.lock:
            if key in self.cache:
                self.cache.move_to_end(key)
                return deepcopy(self.cache[key][1])
            data = self.store.load(key)
            if data is not None:
                self._remember(key, data, float('-inf'))
                return deepcopy(data)
            return None

    def status(self, symbol, expiries):
        key = self._key(symbol, expiries)
        with self.lock:
            entry = self.cache.get(key)
            return dict(generation=self.generation, refreshing=self.inflight == key,
                        busy=self.inflight is not None,
                        fresh=entry is not None and self.clock() - entry[0] < 600,
                        error=self.errors.get(key),
                        retry_in=max(0, int(self.retry_at - self.clock()) + 1),
                        storage_error=self.storage_error)

    def _start(self, key, force=False):
        with self.lock:
            entry = self.cache.get(key)
            if not force and entry is not None and self.clock() - entry[0] < 600:
                return False
            if self.inflight is not None or self.clock() < self.retry_at:
                return False
            self.inflight = key
            self.retry_at = self.clock() + 30
            return True

    def _load(self, key):
        try:
            data = self.fetch(*key)
            if not isinstance(data, dict) or not data.get('rows'):
                raise ValueError('Provider returned no quote rows.')
            if data.get('source') == 'Yahoo Finance via yfinance':
                validate_market_snapshot(data, key[0])
            try:
                self.store.save(key, data)
                storage_error = None
            except (OSError, ValueError, TypeError, KeyError) as exc:
                storage_error = str(exc)
            with self.lock:
                self._remember(key, data, self.clock())
                self.errors.pop(key, None)
                self.storage_error = storage_error
                self.generation += 1
            return deepcopy(data)
        except Exception as exc:
            with self.lock:
                self.retry_at = self.clock() + 300
                self.errors[key] = str(exc)
                self.errors.move_to_end(key)
                while len(self.errors) > 8:
                    self.errors.popitem(last=False)
            raise
        finally:
            with self.lock:
                self.inflight = None

    def _refresh(self, key):
        try:
            self._load(key)
        except Exception:
            pass

    def request_refresh(self, symbol, expiries, force=False):
        key = self._key(symbol, expiries)
        if not self._start(key, force):
            return False
        Thread(target=self._refresh, args=(key,), daemon=True,
               name='yahoo-snapshot-refresh').start()
        return True

    def get(self, symbol, expiries):
        """Synchronous API for scripts; the dashboard uses peek/request_refresh."""
        key = self._key(symbol, expiries)
        with self.lock:
            entry = self.cache.get(key)
            if entry is not None and self.clock() - entry[0] < 600:
                self.cache.move_to_end(key)
                return deepcopy(entry[1])
        if not self._start(key):
            raise ValueError('Yahoo requests are paused or already refreshing. '
                             'The dashboard keeps showing its last available snapshot.')
        return self._load(key)

