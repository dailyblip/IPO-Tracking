"""Synthetic census accounting; never claims live SEC completeness."""
import base64
import copy
import gzip
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import reconcile_sec_census as m

URL='https://www.sec.gov/Archives/edgar/full-index/2026/QTR1/master.idx'


def row(cik, acc, form='424B1', filed='2026-01-02'):
    return f'{cik}|Same Display Name|{form}|{filed}|edgar/data/{cik}/{acc}.txt\n'


class CensusTests(unittest.TestCase):
    def test_expanded_forms_and_month_boundaries(self):
        raw=(row(1,'0000000001-26-000001')+
             row(2,'0000000002-26-000002','S-11')+
             row(3,'0000000003-26-000003','F-10')+
             row(4,'0000000004-26-000004','424B3')+
             row(5,'0000000005-26-000005','424B5')+
             row(6,'0000000006-25-000006',filed='2025-12-31')).encode()
        rows,other=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
        self.assertEqual(len(rows),4)
        self.assertEqual(other,{'424B5':1})
        self.assertEqual({r['form'] for r in rows},{'424B1','S-11','F-10','424B3'})

    def test_names_and_cik_alone_never_suppress_other_filings(self):
        raw=(row(1,'0000000001-26-000001')+row(1,'0000000001-26-000002')+row(2,'0000000002-26-000001')).encode()
        rows,_=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
        staged=[dict(cik='0000000001',accession_no='0000000001-26-000001',id='test-offering')]
        result=m.reconcile(rows,staged)
        self.assertEqual([r['status'] for r in result],['exact_current_snapshot','issuer_present_lineage_review','unreviewed_candidate'])
        self.assertEqual(sum(m.summarize(result)['2026-01'].values()),3)
        self.assertIsNone(result[1]['offering_id'])

    def test_corruption_duplicates_and_malformed_rows_fail(self):
        raw=row(1,'0000000001-26-000001').encode()
        for source,expected in [(raw,'0'*64),(raw+raw,m.sha(raw+raw)),(b'1|broken\n',m.sha(b'1|broken\n'))]:
            with self.assertRaises(ValueError):m.parse_index(source,URL,expected,'2026-01-01','2026-01-31')
        rows,_=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
        with self.assertRaises(ValueError):m.reconcile(rows+rows,[])

    def test_ordered_chunks_and_full_hash_are_verified(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);parts=[b'first',b'second'];raw=b''.join(parts)
            spec=dict(bytes=len(raw),sha256=m.sha(raw),metadata=dict(sha256=m.sha(raw)),chunks=[])
            start=0
            for part in parts:
                h=m.sha(part);(d/(h+'.b64')).write_text(base64.b64encode(gzip.compress(part)).decode())
                spec['chunks'].append(dict(start=start,length=len(part),sha256=h));start+=len(part)
            self.assertEqual(m.restore_index(spec,d),raw)
            bad=copy.deepcopy(spec);bad['chunks'].reverse()
            with self.assertRaises(ValueError):m.restore_index(bad,d)
            bad=copy.deepcopy(spec);bad['sha256']='0'*64
            with self.assertRaises(ValueError):m.restore_index(bad,d)
            (d/(m.sha(parts[0])+'.b64')).write_text(base64.b64encode(gzip.compress(b'wrong')).decode())
            with self.assertRaises(ValueError):m.restore_index(spec,d)
