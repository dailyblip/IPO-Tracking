"""Synthetic census accounting; never claims live SEC completeness."""
import base64
import copy
import gzip
import json
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
    def test_reverse_inventory_requires_exact_identity_and_filing_metadata(self):
        raw=(row(1,'0000000001-26-000001')+row(2,'0000000002-26-000001')).encode()
        rows,_=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
        staged=[dict(id='one',cik='1',accession_no=rows[0]['accession'],
                     form='424B1',filing_date='2026-01-02')]
        result=m.audit_staged_inventory(rows,staged)
        self.assertEqual(result[0]['status'],'pass')
        self.assertEqual(result[0]['index_sha256'],m.sha(raw))
        for field,value in [('form','S-1'),('filing_date','2026-01-03')]:
            bad=copy.deepcopy(staged);bad[0][field]=value
            self.assertEqual(m.audit_staged_inventory(rows,bad)[0]['status'],'fail')
            del bad[0][field]
            self.assertEqual(m.audit_staged_inventory(rows,bad)[0]['status'],'unverified')
        # Same issuer and display name do not establish a different accession.
        staged[0]['accession_no']='0000000001-26-000099'
        self.assertEqual(m.audit_staged_inventory(rows,staged)[0]['reason'],
                         'not_found_in_scoped_indexes')
        with self.assertRaisesRegex(ValueError,'Duplicate staged'):
            m.audit_staged_inventory(rows,staged*2)
        with self.assertRaisesRegex(ValueError,'Duplicate candidate'):
            m.audit_staged_inventory(rows*2,staged)

    def disposition_fixture(self, directory):
        raw=b'<p>This prospectus registers resale shares, not an initial offering.</p>'
        text,blocks=m.text_blocks(raw)
        (directory/'objects').mkdir()
        (directory/'objects'/m.sha(raw)).write_bytes(raw)
        item=dict(cik='0000000001',accession='0000000001-26-000001',
                  form='424B1',filed='2026-01-02',scope='exact_filing_only',
                  publication_allowed=False,disposition='resale_not_initial_ipo',
                  source=dict(content_sha256=m.sha(raw),bytes=len(raw),
                              url='https://www.sec.gov/Archives/edgar/data/1/000000000126000001/prospectus.htm'),
                  normalized_text_sha256=m.sha(text.encode()),
                  evidence=[m.passage(blocks,0,0,text)])
        return dict(version='sec-census-disposition-checkpoint/1',
                    issuer_wide_exclusion=False,reviewed_at='2026-09-27',rows=[item])

    def load_fixture(self, directory, checkpoint):
        raw=json.dumps(checkpoint).encode();path=directory/'dispositions.json'
        path.write_bytes(raw)
        return m.load_dispositions(path,m.sha(raw),directory)

    def test_review_excludes_only_exact_filing_and_keeps_every_row(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);cp=self.disposition_fixture(d);review=self.load_fixture(d,cp)
            raw=(row(1,'0000000001-26-000001')+row(1,'0000000001-26-000002')+
                 row(2,'0000000002-26-000001')).encode()
            rows,_=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
            result=m.reconcile(rows,[],review)
            self.assertEqual([r['status'] for r in result],
                             ['reviewed_excluded_filing','unreviewed_candidate','unreviewed_candidate'])
            self.assertEqual(sum(m.summarize(result)['2026-01'].values()),3)
            self.assertEqual(result[0]['review']['disposition'],'resale_not_initial_ipo')
            cp['rows'][0]['disposition']='held_uplisting_scope'
            held=m.reconcile(rows,[],self.load_fixture(d,cp))
            self.assertEqual(held[0]['status'],'reviewed_held_filing')
            self.assertEqual(held[1]['status'],'unreviewed_candidate')

    def test_disposition_conflicts_and_out_of_scope_fail_closed(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);review=self.load_fixture(d,self.disposition_fixture(d))
            raw=row(1,'0000000001-26-000001').encode()
            rows,_=m.parse_index(raw,URL,m.sha(raw),'2026-01-01','2026-01-31')
            with self.assertRaisesRegex(ValueError,'conflicts'):
                m.reconcile(rows,[dict(cik='0000000001',accession_no=rows[0]['accession'],id='already-imported')],review)
            for key,value in [('form','424B4'),('filed','2026-01-03')]:
                bad=copy.deepcopy(rows);bad[0][key]=value
                with self.assertRaisesRegex(ValueError,'identity mismatch'):m.reconcile(bad,[],review)
            with self.assertRaisesRegex(ValueError,'not present'):m.reconcile([],[],review)

    def test_disposition_evidence_tampering_and_broad_scope_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);cp=self.disposition_fixture(d)
            variants=[]
            for key,value in [('scope','issuer'),('publication_allowed',True),
                              ('disposition','guessed_exclusion'),('evidence',[]),
                              ('normalized_text_sha256','0'*64)]:
                bad=copy.deepcopy(cp);bad['rows'][0][key]=value;variants.append(bad)
            bad=copy.deepcopy(cp);bad['issuer_wide_exclusion']=True;variants.append(bad)
            bad=copy.deepcopy(cp);bad['rows']*=2;variants.append(bad)
            bad=copy.deepcopy(cp);bad['rows'][0]['evidence'][0]['excerpt']='invented';variants.append(bad)
            bad=copy.deepcopy(cp);bad['rows'][0]['source']['url']='https://example.com/source';variants.append(bad)
            for bad in variants:
                with self.assertRaises(ValueError):self.load_fixture(d,bad)
            self.load_fixture(d,cp)
            with self.assertRaisesRegex(ValueError,'checkpoint hash'):
                m.load_dispositions(d/'dispositions.json','0'*64,d)
            (d/'objects'/cp['rows'][0]['source']['content_sha256']).write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'source hash/length'):self.load_fixture(d,cp)

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
