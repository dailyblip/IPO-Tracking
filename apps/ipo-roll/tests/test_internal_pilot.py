import sys,json,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_internal_pilot as m
class PilotTests(unittest.TestCase):
    def fixture(self,d):
        raw=b'<html><p>Example Manufacturing</p><p>This is the initial public offering under EXAM. Price between $20.00 and $24.00.</p><p>We design and manufacture industrial machines.</p></html>'
        h=m.sha(raw);text,blocks=m.text_blocks(raw);(d/'objects').mkdir();(d/'objects'/h).write_bytes(raw)
        filing={'accessionNumber':'0000000001-26-000001','form':'S-1','filingDate':'2026-09-01','fileNumber':'333-123456'}
        review={'capture':{'cik':'0000000001','lineage':{'current':filing,'root':filing},'documents':[{'filing':filing,'source':{'content_sha256':h,'url':'https://www.sec.gov/Archives/edgar/data/1/000000000126000001/test.htm','retrieved_at':'2026-09-23T00:00:00Z'},'normalized_text_sha256':m.sha(text.encode()),'normalizer':'sec-review/1'}]},'people':[],'rights_status':'unreviewed','publication_allowed':False}
        review.update(sha256=m.sha(m.canonical(review).encode()),id='10000000-0000-4000-8000-000000000001',intake_run_id='10000000-0000-4000-8000-000000000002')
        f={k:dict(first_block=a,last_block=a,literal=val) for k,a,val in [('company',0,'Example Manufacturing'),('ticker',1,'EXAM'),('filing_price',1,'between $20.00 and $24.00'),('initial_offering',1,'initial public offering'),('operating_business',2,'design and manufacture')]}
        f['filing_price'].update(low=20,high=24)
        return review,f
    def test_pilot_has_no_commercial_approval_or_invented_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);r,f=self.fixture(d);manifest,sql=m.build(r,f,d)
            self.assertFalse(manifest['manifest']['published'])
            self.assertIn('current_price',manifest['manifest']['null_fields'])
            self.assertIn("'internal_review'",sql)
            self.assertNotIn('insert into app.entitlements',sql)
            self.assertEqual((manifest,sql),m.build(r,f,d))
    def test_changed_price_or_tampered_review_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);r,f=self.fixture(d);f['filing_price']['low']=21
            with self.assertRaises(ValueError):m.build(r,f,d)
            f['filing_price']['low']=20;r['people']=[{'name':'Fake'}]
            with self.assertRaises(ValueError):m.build(r,f,d)
