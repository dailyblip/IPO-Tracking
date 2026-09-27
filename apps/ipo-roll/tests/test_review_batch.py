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

    def test_large_artifacts_are_losslessly_chunked_without_raising_blob_limit(self):
        raw = (b'large-sec-source-' * 300) + b'end'
        logical_hash = m.sha(raw)
        stored, chunked = m.plan_artifact_archive(
            {logical_hash: raw}, inline_limit=4096, chunk_bytes=1000, max_bytes=8192)
        self.assertNotIn(logical_hash, stored)
        self.assertEqual(chunked[logical_hash]['raw_bytes'], len(raw))
        self.assertGreater(len(chunked[logical_hash]['chunks']), 1)
        self.assertTrue(all(len(value) <= 4096 for value in stored.values()
                            if value != stored[chunked[logical_hash]['manifest_sha256']]))
        self.assertEqual(m.restore_artifact(logical_hash, stored, chunked), raw)
        self.assertTrue(all(m.sha(value) == checksum for checksum, value in stored.items()))

        damaged = dict(stored)
        first = chunked[logical_hash]['chunks'][0]['sha256']
        damaged[first] = b'changed'
        with self.assertRaisesRegex(ValueError, 'chunk hash/length'):
            m.restore_artifact(logical_hash, damaged, chunked)

        reordered = copy.deepcopy(chunked)
        reordered[logical_hash]['chunks'].reverse()
        with self.assertRaisesRegex(ValueError, 'manifest mismatch'):
            m.restore_artifact(logical_hash, stored, reordered)

    def test_artifact_archive_limits_fail_closed(self):
        raw = b'12345'; checksum = m.sha(raw)
        for kwargs in (
            dict(inline_limit=0, chunk_bytes=1, max_bytes=5),
            dict(inline_limit=4, chunk_bytes=5, max_bytes=5),
            dict(inline_limit=4, chunk_bytes=2, max_bytes=4),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                m.plan_artifact_archive({checksum: raw}, **kwargs)
        with self.assertRaisesRegex(ValueError, 'content hash mismatch'):
            m.plan_artifact_archive({'0' * 64: raw}, inline_limit=4,
                                    chunk_bytes=2, max_bytes=5)

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

    def test_424b1_preserves_preliminary_price_and_requires_final_evidence(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r,i=self.fixture(d)
            root=copy.deepcopy(p['lineage']['root'])
            final=dict(root, accessionNumber='0000000001-26-000002',form='424B1',filingDate='2026-09-02')
            raw=b'<p>Example Manufacturing</p><p>This is the initial public offering. Price per share $22.00. Gross offering $22,000,000. September 2, 2026.</p><p>We manufacture industrial machines.</p>'
            text,_=m.text_blocks(raw);h=m.sha(raw);th=m.sha(text.encode())
            (d/'objects'/h).write_bytes(raw);(d/'objects'/th).write_text(text)
            p['documents'].append(dict(filing=final,source=dict(content_sha256=h,url='https://www.sec.gov/Archives/edgar/data/1/000000000126000002/final.htm',retrieved_at='2026-09-23T00:00:00Z'),normalized_text_sha256=th,normalizer='sec-review/1'))
            p['lineage']['current']=final;i['records'][0]['values']['filed']='2026-09-02'
            r['people']=[]
            r['fields']['preliminary']['accession']=root['accessionNumber']
            for key in ('final_price','pricing_date','offering_value'):r['fields'][key]=dict(first=1)
            r.update(preceding_filings_reviewed=True,final_price=22,pricing_date='2026-09-02',offering_value=22000000)
            _,sql,_=m.build(p,r,i,d)
            self.assertIn("'Priced'",sql);self.assertIn('$20.00–$24.00',sql)
            self.assertNotIn('insert into research.market_prices',sql)
            self.assertNotIn('insert into research.ownerships',sql)
            for field,value in [('final_price',23),('pricing_date','2026-09-03'),('preceding_filings_reviewed',False)]:
                bad=copy.deepcopy(r);bad[field]=value
                with self.assertRaises(ValueError):m.build(p,bad,i,d)
