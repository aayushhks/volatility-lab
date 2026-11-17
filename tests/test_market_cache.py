import unittest
from volatility_lab.market_cache import MarketCache

class MarketCacheTests(unittest.TestCase):
    def test_reuse_expiry_and_isolation(self):
        now=[0]; calls=[]
        def fetch(*key):
            calls.append(key)
            return {'rows':[1]}
        cache=MarketCache(fetch,lambda:now[0])
        cache.get('spy',3)['rows'].append(2)
        self.assertEqual(cache.get('SPY',3)['rows'],[1])
        self.assertEqual(len(calls),1)
        now[0]=601
        cache.get('SPY',3)
        self.assertEqual(len(calls),2)

    def test_failure_pauses_other_tickers(self):
        now=[0];calls=[]
        def fetch(*key):
            calls.append(key)
            raise ValueError('Too Many Requests')
        cache=MarketCache(fetch,lambda:now[0])
        with self.assertRaises(ValueError): cache.get('SPY',3)
        with self.assertRaisesRegex(ValueError,'paused'): cache.get('QQQ',3)
        self.assertEqual(len(calls),1)
        now[0]=301
        with self.assertRaisesRegex(ValueError,'Too Many'): cache.get('QQQ',3)
        self.assertEqual(len(calls),2)
