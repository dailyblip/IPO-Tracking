import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import commercial_discovery as m
from capture_sec_evidence import capture, Archive
from build_review_batch import build as build_review


HEADER = 'Description: Master Index\nCIK|Company Name|Form Type|Date Filed|Filename\n'
URL = 'https://www.sec.gov/Archives/edgar/full-index/2026/QTR3/master.idx'
DAILY = 'https://www.sec.gov/Archives/edgar/daily-index/2026/QTR3/master.20260928.idx'
STAMP = '2026-09-29T03:00:00+00:00'
COMMIT = 'a' * 40
ACC = '0000000001-26-000001'
CIK = '0000000001'


def line(cik=1, acc=ACC, form='S-1', filed='2026-09-28', company='Example Manufacturing'):
    return f'{cik}|{company}|{form}|{filed}|edgar/data/{cik}/{acc}.txt\n'


def fixture(rows=None, url=URL, retrieved=STAMP, start='2026-09-28', end='2026-09-28', as_of=STAMP):
    raw = (HEADER + (rows or line())).encode()
    artifact = dict(url=url, sha256=m.sha(raw), bytes=len(raw), retrieved_at=retrieved, path='index.idx')
    spec = dict(version='commercial-discovery-input/1', start=start, end=end,
                as_of=as_of, engine_baseline_commit=COMMIT, indexes=[artifact])
    return spec, {m.sha(raw): raw}


def captured_fixture(directory, entry):
    objects, requests = directory / 'objects', directory / 'requests'
    objects.mkdir(); requests.mkdir()

    def cache(url, raw, kind):
        checksum = m.sha(raw)
        meta = dict(url=url, content_sha256=checksum, bytes=len(raw),
                    content_type=kind, retrieved_at=STAMP)
        (objects / checksum).write_bytes(raw)
        (requests / (m.sha(url.encode()) + '.json')).write_text(json.dumps(meta))

    filing = dict(accessionNumber=ACC, filingDate='2026-09-28', form='S-1',
                  fileNumber='333-123456', primaryDocument='example.htm')
    submissions = dict(cik=1, filings=dict(recent={key: [value] for key, value in filing.items()}, files=[]))
    cache('https://data.sec.gov/submissions/CIK' + CIK + '.json', json.dumps(submissions).encode(), 'application/json')
    cache('https://www.sec.gov/Archives/edgar/data/1/000000000126000001/example.htm',
          b'<p>Example Manufacturing</p><p>This is the initial public offering.</p><p>We manufacture industrial machines.</p>', 'text/html')
    packet = capture(entry['intake']['records'][0], Archive(directory))
    packet['intake_record_id'] = 'unbound-workflow-discovery'
    packet['discovery_only'] = True
    review = dict(operating_company=True, intake_record_id=entry['intake']['records'][0]['id'],
                  company='Example Manufacturing', people=[],
                  fields={k: dict(first=i) for i, k in enumerate(('company', 'initial_offering', 'operating_business'))})
    return packet, review


class CommercialDiscoveryTests(unittest.TestCase):
    def test_hash_bound_discovery_never_promotes_facts(self):
        spec, artifacts = fixture()
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(queue, m.build_queue(spec, artifacts))
        self.assertFalse(queue['publication_allowed'])
        entry = queue['entries'][0]
        self.assertEqual(entry['status'], 'capture_pending')
        self.assertEqual(entry['eligibility'], 'unreviewed')
        self.assertEqual(entry['fact_refresh'], 'unverified')
        self.assertIsNone(entry['registration_file_number'])
        self.assertEqual(m.capture_request(queue)['filings'], [dict(cik=CIK, accession=ACC)])
        self.assertFalse(entry['intake']['published'])

    def test_daily_and_quarterly_duplicates_coalesce_with_provenance(self):
        spec, artifacts = fixture()
        daily, _ = fixture(url=DAILY)
        spec['indexes'] += daily['indexes']
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(len(queue['entries']), 1)
        self.assertEqual(len(queue['entries'][0]['observations']), 2)
        self.assertEqual(len(queue['index_sources']), 2)

    def test_incremental_replay_has_stable_intake_identity(self):
        spec, artifacts = fixture()
        first = m.build_queue(spec, artifacts)
        newer, more = fixture(rows=line() + line(2, '0000000002-26-000001'))
        second = m.build_queue(newer, more, first)
        self.assertEqual(len(second['entries']), 2)
        self.assertEqual(second['entries'][0]['intake'], first['entries'][0]['intake'])
        self.assertEqual(second['previous_checkpoint_sha256'], first['checkpoint_sha256'])

    def test_real_daily_header_compact_dates_and_identical_duplicate_rows(self):
        spec, artifacts = fixture()
        literal = line(filed='20260928')
        raw = ('CIK|Company Name|Form Type|Date Filed|File Name\n' + literal + literal).encode()
        daily = dict(url=DAILY, sha256=m.sha(raw), bytes=len(raw), retrieved_at=STAMP)
        spec['indexes'].append(daily); artifacts[m.sha(raw)] = raw
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(len(queue['entries']), 1)
        self.assertEqual(queue['entries'][0]['status'], 'capture_pending')
        self.assertEqual(queue['entries'][0]['filed'], '2026-09-28')
        self.assertEqual(len(queue['entries'][0]['observations']), 2)
        self.assertEqual(sum(s['identical_duplicate_rows'] for s in queue['index_sources']), 1)
        conflict = raw + line(filed='20260928', company='Conflicting issuer name').encode()
        changed = dict(daily, sha256=m.sha(conflict), bytes=len(conflict))
        spec['indexes'] = [changed]
        held = m.build_queue(spec, {m.sha(conflict): conflict})
        self.assertEqual(held['entries'][0]['hold_reasons'], ['conflicting_index_rows'])

    def test_bad_hash_length_headers_dates_and_paths_fail_closed(self):
        spec, artifacts = fixture()
        for field, value in [('sha256', '0' * 64), ('bytes', 1),
                             ('url', URL.replace('www.sec.gov', 'example.com')),
                             ('retrieved_at', '2026-09-30T00:00:00Z')]:
            bad = copy.deepcopy(spec); bad['indexes'][0][field] = value
            with self.subTest(field=field), self.assertRaises((ValueError, KeyError)):
                m.build_queue(bad, artifacts)
        for raw in [b'not an index', (HEADER + '1|malformed\n').encode(),
                    (HEADER + line(filed='2026-09-30')).encode()]:
            bad = copy.deepcopy(spec)
            bad['indexes'][0].update(url=DAILY, sha256=m.sha(raw), bytes=len(raw))
            with self.assertRaises(ValueError):
                m.build_queue(bad, {m.sha(raw): raw})
        with self.assertRaises(ValueError):
            m.local_path(Path('/tmp/safe'), '../elsewhere')

    def test_daily_dissemination_retains_late_released_actual_filing_dates(self):
        spec, artifacts = fixture(rows=line(filed='20260925'), url=DAILY)
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(queue['entries'][0]['filed'], '2026-09-25')
        self.assertEqual(queue['entries'][0]['status'], 'capture_pending')
        spec, artifacts = fixture(rows=line(filed='20251231'), url=DAILY)
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(queue['entries'][0]['status'], 'held')
        self.assertIn('earlier_filing_requires_2026_activity_review', queue['entries'][0]['hold_reasons'])

    def test_missing_days_and_current_day_are_incomplete_not_empty_success(self):
        spec, artifacts = fixture(url=DAILY, start='2026-09-25',
                                  retrieved='2026-09-29T12:00:00Z', as_of='2026-09-29T12:00:00Z')
        queue = m.build_queue(spec, artifacts)
        self.assertEqual(queue['coverage']['missing_weekdays'], ['2026-09-25'])
        self.assertEqual(queue['coverage']['status'], 'incomplete')
        self.assertFalse(queue['coverage']['complete_ipo_census'])
        current, objects = fixture(url=DAILY)
        self.assertEqual(m.build_queue(current, objects)['coverage']['missing_weekdays'], ['2026-09-28'])
        next_day, objects = fixture(url=DAILY, retrieved='2026-09-29T12:00:00Z', as_of='2026-09-29T12:00:00Z')
        self.assertEqual(m.build_queue(next_day, objects)['coverage']['missing_weekdays'], [])

    def test_joint_registrants_and_extended_forms_are_held_not_dropped(self):
        rows = line() + line(2) + line(3, '0000000003-26-000001', 'S-11')
        queue = m.build_queue(*fixture(rows=rows))
        self.assertEqual(len(queue['entries']), 3)
        self.assertTrue(all(e['status'] == 'held' for e in queue['entries']))
        self.assertIsNone(m.capture_request(queue))

    def test_conflicting_index_rows_remain_held_across_checkpoints(self):
        first = m.build_queue(*fixture())
        spec, artifacts = fixture(rows=line(form='F-1'))
        queue = m.build_queue(spec, artifacts, first)
        self.assertEqual(queue['entries'][0]['status'], 'held')
        self.assertIn('conflicting_index_rows', queue['entries'][0]['hold_reasons'])
        later = m.build_queue(*fixture(), previous=queue)
        self.assertEqual(later['entries'][0]['status'], 'held')

    def test_monitor_hints_never_create_census_records(self):
        hints = [dict(cik='2', accession_no='0000000002-26-000001')]
        queue = m.build_queue(*fixture(), monitor_hints=hints)
        self.assertEqual(len(queue['entries']), 1)
        self.assertEqual(queue['monitor_only_identities'], ['0000000002/0000000002-26-000001'])

    def test_staged_identity_is_not_issuer_wide_completion(self):
        staged = [dict(cik=CIK, accession_no=ACC, form='S-1', filing_date='2026-09-28')]
        queue = m.build_queue(*fixture(rows=line() + line(acc='0000000001-26-000002', form='S-1/A')), staged=staged)
        self.assertEqual([e['status'] for e in queue['entries']], ['staged_snapshot_observed', 'capture_pending'])
        self.assertTrue(all(e['existing_issuer'] for e in queue['entries']))
        staged[0]['form'] = '424B4'
        self.assertEqual(m.build_queue(*fixture(), staged=staged)['entries'][0]['status'], 'held')

    def test_failed_capture_does_not_starve_unattempted_candidates(self):
        rows = ''.join(line(i, f'{i:010d}-26-000001') for i in range(1, 7))
        queue = m.build_queue(*fixture(rows=rows))
        for entry in queue['entries'][:4]:
            queue = m.record_capture_failure(queue, entry['key'], 'HTTPError')
        request = m.capture_request(queue)
        self.assertEqual([r['cik'] for r in request['filings'][:2]], ['0000000005', '0000000006'])
        with self.assertRaises(ValueError):
            m.record_capture_failure(queue, queue['entries'][0]['key'], 'secret contact@example.com')

    def test_captured_packet_is_replayed_and_survives_incremental_selection(self):
        queue = m.build_queue(*fixture())
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            packet, _ = captured_fixture(directory, queue['entries'][0])
            updated, bound = m.record_capture(queue, queue['entries'][0]['key'], packet, directory)
            self.assertEqual(updated['entries'][0]['status'], 'captured_review_pending')
            self.assertEqual(updated['entries'][0]['registration_file_number'], '333-123456')
            self.assertEqual(bound['intake_record_id'], queue['entries'][0]['intake']['records'][0]['id'])
            next_run = m.build_queue(*fixture(), previous=updated)
            self.assertIsNone(m.capture_request(next_run))
            packet['documents'][0]['source']['content_sha256'] = '0' * 64
            with self.assertRaisesRegex(ValueError, 'source version'):
                m.bind_capture(queue['entries'][0], packet, directory)

    def test_reviewed_handoff_requires_exact_manifest_and_source(self):
        queue = m.build_queue(*fixture(), staged=[]); entry = queue['entries'][0]
        with tempfile.TemporaryDirectory() as temp:
            directory = Path(temp)
            packet, review = captured_fixture(directory, entry)
            bound = m.bind_capture(entry, packet, directory)
            manifest, expected_sql, _ = build_review(bound, review, entry['intake'], directory)
            receipt, sql, _ = m.reviewed_handoff(entry, packet, review, directory, manifest)
            self.assertEqual(receipt['status'], 'reviewed_import_ready')
            self.assertEqual(sql, expected_sql)
            self.assertFalse(receipt['applied'])
            self.assertFalse(receipt['publication_allowed'])
            with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
                m.reviewed_handoff(entry, packet, review, directory, dict(manifest, people=4))
            bad = copy.deepcopy(review); bad['operating_company'] = False
            with self.assertRaises(ValueError):
                m.reviewed_handoff(entry, packet, bad, directory, manifest)
            entry['existing_issuer'] = True
            receipt, sql, _ = m.reviewed_handoff(entry, packet, review, directory, manifest)
            self.assertEqual(receipt['status'], 'reviewed_refresh_held')
            self.assertIsNone(sql)
            entry['existing_issuer'] = False
            entry['staging_inventory_checked'] = False
            receipt, sql, _ = m.reviewed_handoff(entry, packet, review, directory, manifest)
            self.assertEqual(receipt['reason'], 'staging_inventory_unverified')
            self.assertIsNone(sql)

    def test_checkpoint_archives_only_private_hash_bound_bytes(self):
        spec, artifacts = fixture()
        queue = m.build_queue(spec, artifacts)
        sql, receipt = m.checkpoint_sql(queue, artifacts)
        self.assertIn('insert into ops.sec_artifacts', sql)
        self.assertNotIn('research.', sql)
        self.assertNotIn('app.', sql)
        self.assertEqual(receipt['checkpoint_object_sha256'], m.sha(m.canonical(queue).encode()))
        queue['entries'][0]['status'] = 'invented'
        with self.assertRaises(ValueError):
            m.checkpoint_sql(queue)

    def test_cli_discovers_captures_and_prepares_reviewed_import_without_applying(self):
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            spec, artifacts = fixture()
            (base / 'input.json').write_text(json.dumps(spec))
            (base / 'index.idx').write_bytes(next(iter(artifacts.values())))
            (base / 'staged.json').write_text('[]')
            queue = m.build_queue(spec, artifacts, staged=[])
            entry = queue['entries'][0]
            archive = base / 'archive'; archive.mkdir()
            packet, review = captured_fixture(archive, entry)
            bound = m.bind_capture(entry, packet, archive)
            manifest, _, _ = build_review(bound, review, entry['intake'], archive)
            for name, value in [('packet', packet), ('review', review), ('manifest', manifest)]:
                (base / (name + '.json')).write_text(json.dumps(value))
            args = ['commercial_discovery.py', '--input', str(base / 'input.json'),
                    '--staged', str(base / 'staged.json'), '--output-dir', str(base / 'output'),
                    '--capture', str(base / 'packet.json'), m.sha((base / 'packet.json').read_bytes()), str(archive),
                    '--review', entry['key'], str(base / 'review.json'), str(base / 'manifest.json')]
            with patch.object(sys, 'argv', args), redirect_stdout(StringIO()):
                m.main()
            output = base / 'output'
            result = json.loads((output / 'queue.json').read_text())
            self.assertEqual(result['entries'][0]['status'], 'reviewed_import_ready')
            self.assertFalse(result['entries'][0]['handoff']['applied'])
            self.assertIsNone(json.loads((output / 'capture-request.json').read_text()))
            self.assertEqual(len(list(output.glob('reviewed-*.sql'))), 1)
            self.assertEqual(len(list(output.glob('*-intake.sql'))), 1)
            archive_sql = (output / 'checkpoint.sql').read_text()
            self.assertIn(result['entries'][0]['capture']['packet_sha256'], archive_sql)
            self.assertNotIn('research.', archive_sql)


if __name__ == '__main__':
    unittest.main()
