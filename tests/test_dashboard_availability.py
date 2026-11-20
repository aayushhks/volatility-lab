"""UI regression checks with no provider network requests."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
except ImportError:
    st = None

from volatility_lab.data import demo
from volatility_lab.market_cache import MarketCache
from volatility_lab.snapshots import SnapshotStore

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipIf(st is None, 'Streamlit is not installed')
class DashboardAvailabilityTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        st.cache_resource.clear()
        self.addCleanup(st.cache_resource.clear)

    @staticmethod
    def unavailable(*args):
        raise ValueError('Too Many Requests')

    def run_app(self, cache):
        with patch('volatility_lab.market_cache.MarketCache', return_value=cache):
            app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
        self.assertEqual([error.message for error in app.exception], [])
        self.assertGreaterEqual(len(app.get('plotly_chart')), 3)
        return app

    def test_first_visit_without_market_data_still_has_labeled_charts(self):
        cache = MarketCache(self.unavailable, cache_dir=self.directory.name)
        app = self.run_app(cache)
        self.assertTrue(any('Offline example' in message.value for message in app.info))
        self.assertEqual(app.metric[0].value, '$100.00')
        self.assertEqual(len(app.error), 0)

    def test_saved_snapshot_stays_visible_during_provider_failure(self):
        # A synthetic fixture is labeled Yahoo only within this isolated test directory.
        fixture = demo()
        fixture.update(symbol='TEST', source='Yahoo Finance via yfinance',
                       fetched_at='2026-11-19T20:00:00+00:00', spot_timestamp='2026-11-19')
        cache = MarketCache(self.unavailable, cache_dir=self.directory.name)
        SnapshotStore(self.directory.name).save(('TEST', 3), fixture)
        with patch('volatility_lab.market_cache.MarketCache', return_value=cache):
            app = AppTest.from_file(str(ROOT / 'app.py'), default_timeout=20).run()
            app.text_input[0].set_value('TEST').run()
            self.assertEqual([error.message for error in app.exception], [])
            self.assertTrue(any('Saved market snapshot' in message.value for message in app.info))
            self.assertTrue(any('2026-11-19T20:00:00+00:00' in text.value for text in app.caption))
            self.assertGreaterEqual(len(app.get('plotly_chart')), 3)
            # Switching tickers must never pass another ticker's saved market data off as current.
            app.text_input[0].set_value('QQQ').run()
            self.assertTrue(any('Offline example' in message.value for message in app.info))

    def test_cold_start_archive_or_labeled_fallback_renders_without_network(self):
        cache = MarketCache(self.unavailable, cache_dir=self.directory.name,
                            archives=(ROOT / 'examples' / 'market',))
        snapshot = cache.peek('SPY', 3)
        app = self.run_app(cache)
        if snapshot is None:
            self.assertTrue(any('Offline example' in message.value for message in app.info))
        else:
            self.assertTrue(any('Saved market snapshot' in message.value for message in app.info))
            self.assertFalse(any('Offline example' in message.value for message in app.info))
            self.assertEqual(app.metric[0].value, f"${snapshot['spot']:.2f}")
