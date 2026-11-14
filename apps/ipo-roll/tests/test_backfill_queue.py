import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_backfill_queue import build_queue
from import_legacy import digest


def intake(values):
    result = {'id': 'batch', 'source_commit': 'a' * 40,
              'records': [{'id': str(i), 'values': v} for i, v in enumerate(values)]}
    result['payload_sha256'] = digest(result)
    return result


class BackfillQueueTests(unittest.TestCase):
    def test_priced_in_year_includes_previous_year_registration_and_boundaries(self):
        batch = intake([
            dict(cik='1', accession_no='a', filing_date='2025-08-01', filed='2026-01-03', pricing_date='2026-01-01'),
            dict(cik='2', accession_no='b', filed='2026-09-25'),
            dict(cik='3', accession_no='c', filed='2025-12-31'),
            dict(cik='4', accession_no='d', filed='2026-09-26')])
        q = build_queue(batch, [], '2026-01-01', '2026-09-25')
        self.assertEqual([r['cik'] for r in q['records']], ['1', '2'])
        self.assertFalse(q['sec_coverage_complete'])
        self.assertEqual(q['months']['2026-02'], {})

    def test_exact_snapshot_dedup_and_issuer_reconciliation(self):
        batch = intake([dict(cik='1', accession_no=a, filed='2026-02-01') for a in ['a', 'b', 'c', 'c']])
        q = build_queue(batch, [dict(cik='1', accession='a')], '2026-01-01', '2026-09-25')
        self.assertEqual([r['status'] for r in q['records']], [
            'already_staged_snapshot', 'existing_issuer_reconciliation',
            'duplicate_identity_review', 'duplicate_identity_review'])
        batch['records'][0]['values']['cik'] = 'tampered'
        with self.assertRaisesRegex(ValueError, 'hash mismatch'):
            build_queue(batch, [], '2026-01-01', '2026-09-25')


if __name__ == '__main__':
    unittest.main()
