"""Bounded, process-wide quote cache and provider backoff."""
from collections import OrderedDict
from copy import deepcopy
from threading import Lock
from time import monotonic

class MarketCache:
    def __init__(self, fetch, clock=monotonic):
        self.fetch, self.clock = fetch, clock
        self.cache = OrderedDict()
        self.lock = Lock()
        self.retry_at = 0

    def get(self, symbol, expiries):
        key = (symbol.strip().upper(), expiries)
        with self.lock:
            now = self.clock()
            if key in self.cache:
                saved, data = self.cache[key]
                if now - saved < 600:
                    self.cache.move_to_end(key)
                    return deepcopy(data)
                del self.cache[key]
            if now < self.retry_at:
                raise ValueError(f'Yahoo requests are paused. Try again in {int(self.retry_at-now)+1} seconds, or use CSV / Synthetic demo.')
            # Space uncached fetches across users as well as within a session.
            self.retry_at = now + 30
            try:
                data = self.fetch(*key)
            except Exception:
                self.retry_at = self.clock() + 300
                raise
            self.cache[key] = (self.clock(), deepcopy(data))
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
            return data
