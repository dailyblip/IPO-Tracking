"""Import contract tests: identity, provenance, exclusion and failure isolation."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location('import_legacy', Path(__file__).parents[1] / 'scripts/import_legacy.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
COMMIT = 'a' * 40


def fixture():
    return {'schema_version': 1, 'generated_at': '2026-09-23T00:00:00+00:00', 'filings': [{
        'company': 'Cardinal Test Manufacturing', 'ticker': 'TEST', 'cik': '0000000001',
        'accession_no': '0000000002-26-000001', 'form': '424B4', 'filed': '2026-09-22',
        'filing_date': '2026-08-01', 'pricing_date': '2026-09-20', 'stage': 'Priced',
        'offering_price': 12, 'value': None, 'filing_price': '10-12',
        'sec_url': 'https://www.sec.gov/Archives/edgar/data/1/000000000226000001/0000000002-26-000001-index.htm',
        'filing_price_source': {'source': 'SEC EDGAR', 'form': 'S-1/A',
            'filing_date': '2026-09-15', 'accession_no': '0000000002-26-000002', 'file_number': '333-123456',
            'sec_url': 'https://www.sec.gov/Archives/edgar/data/1/000000000226000002/0000000002-26-000002-index.htm'},
        'current_price': 99.12, 'signals': ['Stanford'], 'stanford_count': 99,
        'people': [{'name': 'Jordan Example', 'holder_type': 'individual', 'is_beneficial_owner': True,
                    'stanford_university_bio': 'private enrichment sentinel', 'shares_before_ipo': 100,
                    'biography': 'Never import a biography from this feed'}]}]}


def build(f=None):
    return m.build(json.dumps(f or fixture()).encode(), COMMIT)


class ImportTests(unittest.TestCase):
    def test_replay_and_changes_have_deterministic_distinct_identity(self):
        a, b = build(), build()
        self.assertEqual(a, b)
        changed = fixture()
        changed['filings'][0]['offering_price'] = 13
        c = build(changed)
        self.assertNotEqual(a['id'], c['id'])
        self.assertEqual(a['payload_sha256'], m.digest({k:v for k,v in a.items() if k != 'payload_sha256'}))

    def test_allowlist_excludes_quotes_biographies_and_legacy_enrichment(self):
        data = build()
        encoded = m.canonical(data)
        for forbidden in ('current_price', '99.12', 'stanford', 'private enrichment sentinel', 'Never import'):
            self.assertNotIn(forbidden.lower(), encoded.lower())
        self.assertEqual(data['records'][0]['values']['company'], 'Cardinal Test Manufacturing')
        self.assertEqual(data['records'][0]['holders'][0]['values']['shares_before_ipo'], 100)
        self.assertEqual(m.summary(data)['published'], 0)

    def test_priced_document_date_is_not_root_registration_date(self):
        r = build()['records'][0]
        self.assertNotIn('PRICING_PRECEDES_REPORTED_REGISTRATION', r['findings'])
        obs = {o['field']: o for o in r['observations']}
        self.assertEqual(obs['filed']['value'], '2026-09-22')
        self.assertEqual(obs['filing_date']['value'], '2026-08-01')
        self.assertEqual(obs['filing_price']['reported_source']['accession'], '0000000002-26-000002')
        self.assertEqual(obs['filing_price']['verification'], 'feed_reported')
        self.assertIn('ROOT_LINEAGE_UNVERIFIED', r['findings'])

    def test_url_validation_matches_issuer_and_accession_not_agent_prefix(self):
        url = fixture()['filings'][0]['sec_url']
        self.assertEqual(m.sec_index(url, '0000000001', '0000000002-26-000001'), url)
        for bad in (url.replace('/data/1/', '/data/2/'), url.replace('www.sec.gov', 'www.sec.gov.evil.test'), url+'?x=1', url.replace('https:', 'http:')):
            self.assertIsNone(m.sec_index(bad, '0000000001', '0000000002-26-000001'))

    def test_unsupported_final_price_is_not_filled(self):
        f = fixture()
        f['filings'][0]['offering_price'] = None
        r = build(f)['records'][0]
        self.assertIn('FINAL_PRICE_DATE_MISSING', r['findings'])
        self.assertNotIn('offering_price', r['values'])
        self.assertNotIn('value', r['values'])

    def test_prepricing_conflicts_and_duplicate_records_are_quarantined(self):
        f = fixture()
        f['filings'][0]['stage'] = 'Pre-pricing'
        f['filings'].append(copy.deepcopy(f['filings'][0]))
        for r in build(f)['records']:
            self.assertIn('PREPRICING_FINAL_OR_QUOTE_CONFLICT', r['findings'])
            self.assertIn('DUPLICATE_FILING_IDENTITY', r['findings'])
            self.assertEqual(r['status'], 'quarantined')

    def test_invalid_types_and_restricted_text_never_become_candidate_facts(self):
        f = fixture()
        f['filings'][0].update(company='Stanford restricted example', offering_price=True)
        r = build(f)['records'][0]
        self.assertNotIn('company', r['values'])
        self.assertNotIn('offering_price', r['values'])
        self.assertIn('INVALID_OR_RESTRICTED_FIELD', r['findings'])

    def test_hostile_text_is_data_not_sql(self):
        f = fixture()
        f['filings'][0]['company'] = "Example'); drop schema research cascade; -- $intake$"
        b = build(f)
        script = m.sql(b)
        delimiter = '$intake_' + m.digest(m.canonical(b).encode()) + '$'
        self.assertEqual(script.count(delimiter), 2)
        self.assertIn("Example'); drop schema", script)

    def test_contract_failures_abort_batch(self):
        for change in ({'schema_version': 2}, {'generated_at': '2026-09-23'}, {'filings': [None]}):
            with self.assertRaises(ValueError):
                f = fixture()
                f.update(change)
                build(f)
        with self.assertRaises(ValueError):
            m.build(json.dumps(fixture()).encode(), 'main')


if __name__ == '__main__':
    unittest.main()
