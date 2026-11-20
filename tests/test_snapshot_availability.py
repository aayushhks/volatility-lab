import json
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event
import unittest
from unittest.mock import patch

from volatility_lab.data import demo
from volatility_lab.market_cache import MarketCache
from volatility_lab.snapshots import SnapshotStore, snapshot_filename


def real_snapshot(symbol='SPY'):
    # Test fixture only: never exported or shipped as observed market data.
    return dict(symbol=symbol, spot=100.,
                source='Yahoo Finance via yfinance',
                fetched_at='2026-11-19T20:00:00+00:00', spot_timestamp='2026-11-19',
                rows=[dict(strike=100, days=30, bid=2., ask=2.1, kind='call')])


class SnapshotAvailabilityTests(unittest.TestCase):
    def test_stale_data_survives_failed_refresh_and_return_values_are_isolated(self):
        now = [0]
        calls = [0]
        def fetch(*key):
            calls[0] += 1
            if calls[0] > 1:
                raise ValueError('Too Many Requests')
            return real_snapshot()
        cache = MarketCache(fetch, clock=lambda: now[0])
        cache.get('SPY', 3)
        now[0] = 601
        with self.assertRaises(ValueError):
            cache.get('SPY', 3)
        view = cache.peek('spy', 3)
        self.assertEqual(view['spot'], 100)
        view['rows'].clear()
        self.assertEqual(len(cache.peek('SPY', 3)['rows']), 1)
        self.assertFalse(cache.status('SPY', 3)['fresh'])

    def test_process_restart_loads_persisted_quotes_as_stale(self):
        with TemporaryDirectory() as directory:
            first = MarketCache(lambda *_: real_snapshot(), cache_dir=directory)
            first.get('SPY', 3)
            second = MarketCache(lambda *_: self.fail('peek must not use network'),
                                 cache_dir=directory)
            self.assertEqual(second.peek('SPY', 3), real_snapshot())
            self.assertFalse(second.status('SPY', 3)['fresh'])
            self.assertIsNone(second.peek('QQQ', 3))
            self.assertIsNone(second.peek('SPY', 4))

    def test_committed_archive_survives_empty_local_disk(self):
        with TemporaryDirectory() as directory:
            archive = Path(directory) / 'archive'
            SnapshotStore(archive).save(('SPY', 3), real_snapshot())
            cache = MarketCache(lambda *_: None, cache_dir=Path(directory) / 'empty',
                                archives=(archive,))
            self.assertEqual(cache.peek('SPY', 3)['fetched_at'], real_snapshot()['fetched_at'])

    def test_background_fetch_does_not_block_snapshot_and_is_single_flight(self):
        entered, release, finished = Event(), Event(), Event()
        def fetch(*key):
            entered.set()
            release.wait(5)
            finished.set()
            return real_snapshot()
        cache = MarketCache(fetch)
        try:
            self.assertTrue(cache.request_refresh('SPY', 3))
            self.assertTrue(entered.wait(1))
            self.assertIsNone(cache.peek('SPY', 3))
            self.assertTrue(cache.status('SPY', 3)['refreshing'])
            self.assertFalse(cache.request_refresh('SPY', 3))
            self.assertFalse(cache.request_refresh('QQQ', 3))
        finally:
            release.set()
        self.assertTrue(finished.wait(1))

    def test_corrupt_or_mismatched_disk_does_not_crash_or_mislabel(self):
        with TemporaryDirectory() as directory:
            path = Path(directory) / snapshot_filename('SPY', 3)
            path.write_text('{broken')
            store = SnapshotStore(directory)
            self.assertIsNone(store.load(('SPY', 3)))
            store.save(('SPY', 3), real_snapshot())
            saved = json.loads(path.read_text())
            saved['data']['symbol'] = 'QQQ'
            path.write_text(json.dumps(saved))
            self.assertIsNone(store.load(('SPY', 3)))

    def test_failed_write_retains_previous_file(self):
        with TemporaryDirectory() as directory:
            store = SnapshotStore(directory)
            store.save(('SPY', 3), real_snapshot())
            with patch('volatility_lab.snapshots.os.replace', side_effect=OSError('full disk')):
                with self.assertRaises(OSError):
                    store.save(('SPY', 3), dict(real_snapshot(), spot=101.))
            self.assertEqual(store.load(('SPY', 3))['spot'], 100)
            self.assertFalse(list(Path(directory).glob('.snapshot-*')))

    def test_synthetic_data_is_never_saved_as_real_market_data(self):
        with TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                SnapshotStore(directory).save(('SPY', 3), demo())
            self.assertEqual(list(Path(directory).glob('*.json')), [])

    def test_read_only_disk_does_not_lose_fresh_data(self):
        cache = MarketCache(lambda *_: real_snapshot())
        with patch.object(cache.store, 'save', side_effect=OSError('read only')):
            self.assertEqual(cache.get('SPY', 3)['spot'], 100)
        self.assertEqual(cache.peek('SPY', 3)['spot'], 100)
        self.assertIsNotNone(cache.status('SPY', 3)['storage_error'])

    def test_storage_is_bounded_and_filenames_cannot_escape_directory(self):
        with TemporaryDirectory() as directory:
            store = SnapshotStore(directory)
            for i in range(10):
                symbol = f'T{i}'
                store.save((symbol, 3), real_snapshot(symbol))
            self.assertEqual(len(list(Path(directory).glob('*.json'))), 8)
            name = snapshot_filename('../../outside', 3)
            self.assertNotIn('/', name)

    def test_empty_response_does_not_replace_last_good_snapshot(self):
        now = [0]
        response = [real_snapshot()]
        cache = MarketCache(lambda *_: response[0], clock=lambda: now[0])
        cache.get('SPY', 3)
        now[0] = 601
        response[0] = {'rows': []}
        with self.assertRaises(ValueError):
            cache.get('SPY', 3)
        self.assertEqual(cache.peek('SPY', 3)['spot'], 100)

    def test_zero_quotes_do_not_replace_last_good_snapshot(self):
        now = [0]
        response = [real_snapshot()]
        with TemporaryDirectory() as directory:
            cache = MarketCache(lambda *_: response[0], clock=lambda: now[0],
                                cache_dir=directory)
            cache.get('SPY', 3)
            response[0] = real_snapshot()
            response[0]['rows'][0].update(bid=0., ask=0.)
            now[0] = 601
            with self.assertRaisesRegex(ValueError, 'no usable bid/ask'):
                cache.get('SPY', 3)
            self.assertEqual(cache.peek('SPY', 3)['rows'][0]['bid'], 2.)
            self.assertEqual(SnapshotStore(directory).load(('SPY', 3))['rows'][0]['bid'], 2.)

    def test_unusable_committed_snapshot_is_ignored(self):
        with TemporaryDirectory() as directory:
            store = SnapshotStore(directory)
            store.save(('SPY', 3), real_snapshot())
            path = Path(directory) / snapshot_filename('SPY', 3)
            saved = json.loads(path.read_text())
            saved['data']['rows'][0].update(bid=0., ask=0.)
            path.write_text(json.dumps(saved))
            self.assertIsNone(store.load(('SPY', 3)))


if __name__ == '__main__':
    unittest.main()
