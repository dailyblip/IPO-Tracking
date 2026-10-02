"""Synthetic live-run orchestration: no network, contact or financial claims."""
from datetime import date, datetime, timezone
from email.message import Message
import io
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'scripts'))
import actions_commercial_discovery as m

REQUEST = dict(version='sec-discovery-request/1', request_id='synthetic-discovery',
               start='2026-09-25', end='2026-09-28', capture_limit=4, engine_baseline_commit='a'*40)
INDEX = (b'CIK|Company Name|Form Type|Date Filed|File Name\n'
         b'1|Synthetic Company|S-1|20260925|edgar/data/1/0000000001-26-000001.txt\n')


class DiscoveryRunnerTests(unittest.TestCase):
    def test_only_bounded_authorized_dates_and_exact_targets(self):
        now = datetime(2026,9,29,3,tzinfo=timezone.utc)
        self.assertEqual(m.validate_request(REQUEST, now), (date(2026,9,25),date(2026,9,28)))
        bad = [dict(REQUEST, start='2026-09-20'), dict(REQUEST, end='2026-09-29'),
               dict(REQUEST, start='2025-12-31', end='2026-01-01'), dict(REQUEST, capture_limit=True),
               dict(REQUEST, capture_limit=5), dict(REQUEST, url='https://evil.invalid'),
               dict(REQUEST, request_id='../bad'), dict(REQUEST, engine_baseline_commit='latest')]
        for value in bad:
            with self.subTest(value=value), self.assertRaises(ValueError):
                m.validate_request(value, now)
        self.assertEqual(list(m.index_urls(date(2026,9,25),date(2026,9,28))), [
            'https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260925.idx',
            'https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260928.idx'])

    def test_index_response_cannot_be_arbitrary_or_access_denial(self):
        headers = Message(); headers['Content-Type']='text/plain'
        class Response(io.BytesIO):
            status = 200
        response = Response(b'Access denied'); response.headers=headers
        opener = SimpleNamespace(open=lambda *args, **kwargs: response)
        archive = SimpleNamespace(request_count=0,total_bytes=0,last_request=0,agent='synthetic',opener=opener)
        with self.assertRaisesRegex(ValueError,'header'):
            m.get_index(archive, next(m.index_urls(date(2026,9,25),date(2026,9,25))))
        for url in ('https://evil.invalid/master.idx',
                    'https://www.sec.gov/Archives/edgar/daily-index/2026/QTR4/master.20260925.idx',
                    'https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260925.idx?contact=bad'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                m.get_index(archive,url)

    def test_names_discovered_without_selectors_and_failed_capture_remains_unreviewed(self):
        saved = {}
        def retain(directory, recipient, output):
            saved.update({p.name:p.read_text() for p in directory.glob('*.json')})
        def index(archive, url):
            if '20260928' in url:
                raise ValueError('synthetic unavailable index')
            return INDEX, dict(url=url,sha256=m.sha(INDEX),bytes=len(INDEX),retrieved_at='2026-09-29T03:00:00+00:00')
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'BoundedArchive',return_value=SimpleNamespace(directory=Path(tmp))), \
                patch.object(m,'get_index',side_effect=index), patch.object(m,'load_history',side_effect=ValueError('unavailable')), \
                patch.object(m,'seal',side_effect=retain), patch('sys.stdout',new_callable=io.StringIO) as log:
            self.assertEqual(m.run(REQUEST,Path('public.pem'),Path(tmp)/'out'),1)
            queue=json.loads(saved['discovery-queue.json'])
            self.assertEqual(len(queue['entries']),1)
            entry=queue['entries'][0]
            self.assertEqual(entry['cik'],'0000000001')
            self.assertEqual(entry['status'],'capture_pending')
            self.assertEqual(entry['capture_attempts'],1)
            self.assertEqual(entry['eligibility'],'unreviewed')
            self.assertIsNone(entry['registration_file_number'])
            self.assertEqual(queue['coverage']['missing_weekdays'],['2026-09-28'])
            self.assertFalse(queue['publication_allowed'])
            self.assertNotIn('Synthetic Company',log.getvalue())
            self.assertNotIn('unavailable',log.getvalue())
            manifest=json.loads(saved['manifest.json'])
            self.assertIn('discovery-input.json',manifest['files'])
            self.assertIn('discovery-queue.json',manifest['files'])

    def test_missing_all_indexes_does_not_pass_discovery(self):
        saved={}
        with tempfile.TemporaryDirectory() as tmp, patch.object(m,'BoundedArchive'), \
                patch.object(m,'get_index',side_effect=ValueError('denied')), \
                patch.object(m,'seal',side_effect=lambda d,*_:saved.update(queue=json.loads((d/'discovery-queue.json').read_text()))), \
                patch('sys.stdout',new_callable=io.StringIO):
            self.assertEqual(m.run(REQUEST,Path('public.pem'),Path(tmp)),1)
            self.assertEqual(saved['queue']['entries'],[])
            self.assertEqual(saved['queue']['coverage']['status'],'incomplete')
            self.assertFalse(saved['queue']['coverage']['complete_ipo_census'])


if __name__ == '__main__':
    unittest.main()
