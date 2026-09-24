import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_review_batch as m


class ReviewBatchTests(unittest.TestCase):
    def fixture(self, directory):
        raw=b'''<p>Example Manufacturing</p><p>This is the initial public offering. The initial public offering price is between $20.00 and $24.00.</p><p>We manufacture industrial machines.</p><p>Jordan Example has served as our Chief Operating Officer since 2020. Jordan earned an MBA from the University of Michigan.</p>'''
        text, _=m.text_blocks(raw); h=m.sha(raw); th=m.sha(text.encode())
        (directory/'objects').mkdir();(directory/'objects'/h).write_bytes(raw);(directory/'objects'/th).write_text(text)
        f=dict(accessionNumber='0000000001-26-000001',form='S-1',filingDate='2026-09-01',fileNumber='333-123456')
        rid='10000000-0000-4000-8000-000000000001'
        packet=dict(cik='0000000001',intake_record_id=rid,metadata_artifacts=[],lineage=dict(current=f,root=f,status='metadata_resolved'),documents=[dict(filing=f,source=dict(content_sha256=h,url='https://www.sec.gov/Archives/edgar/data/1/000000000126000001/test.htm',retrieved_at='2026-09-23T00:00:00Z'),normalized_text_sha256=th,normalizer='sec-review/1')])
        review=dict(intake_record_id=rid,company='Example Manufacturing',operating_company=True,preliminary=dict(low=20,high=24),fields={k:dict(first=n) for k,n in [('company',0),('initial_offering',1),('preliminary',1),('operating_business',2)]},people=[dict(name='Jordan Example',title='Chief Operating Officer',relationship='Executive',biography=dict(first=3))])
        intake=dict(run_id='10000000-0000-4000-8000-000000000002',records=[dict(id=rid,values=dict(cik='0000000001',filed='2026-09-01'))])
        return packet,review,intake

    def test_review_is_replayable_private_and_does_not_infer_ownership(self):
        with tempfile.TemporaryDirectory() as t:
            p,r,i=self.fixture(Path(t));result,sql,objects=m.build(p,r,i,Path(t))
            self.assertEqual((result,sql,objects),m.build(p,r,i,Path(t)))
            self.assertEqual(result['people'],1)
            self.assertIn("'biography_text'",sql)
            self.assertIn("'internal_review'",sql)
            self.assertNotIn('insert into research.ownerships',sql)
            self.assertNotIn('insert into app.',sql)
            self.assertNotIn('research.market_prices',sql)
            self.assertIn('then return; end if;',sql)
            self.assertTrue(all(m.sha(raw)==h for h,raw in objects.items()))

    def test_wrong_identity_unsupported_role_price_and_classification_fail(self):
        with tempfile.TemporaryDirectory() as t:
            p,r,i=self.fixture(Path(t))
            variants=[]
            v=copy.deepcopy(r);v['company']='Different Company';variants.append(v)
            v=copy.deepcopy(r);v['people'][0]['name']='Jordan Elsewhere';variants.append(v)
            v=copy.deepcopy(r);v['people'][0]['relationship']='Beneficial owner';variants.append(v)
            v=copy.deepcopy(r);v['people'][0]['title']='Chief Executive Officer';variants.append(v)
            v=copy.deepcopy(r);v['preliminary']['low']=21;variants.append(v)
            v=copy.deepcopy(r);v['operating_company']=False;variants.append(v)
            for v in variants:
                with self.assertRaises(ValueError):m.build(p,v,i,Path(t))

    def test_corrupt_snapshot_and_cross_registration_fail(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r,i=self.fixture(d)
            v=copy.deepcopy(p);v['documents'][0]['filing']=dict(v['documents'][0]['filing'],fileNumber='333-999999')
            with self.assertRaises(ValueError):m.build(v,r,i,d)
            h=p['documents'][0]['source']['content_sha256'];(d/'objects'/h).write_bytes(b'changed')
            with self.assertRaises(ValueError):m.build(p,r,i,d)

    def test_priced_filing_requires_authoritative_terms(self):
        with tempfile.TemporaryDirectory() as t:
            p,r,i=self.fixture(Path(t));p['lineage']['current']['form']='424B4';r.pop('preliminary');r['fields'].pop('preliminary')
            with self.assertRaisesRegex(ValueError,'Priced offering needs'):m.build(p,r,i,Path(t))
