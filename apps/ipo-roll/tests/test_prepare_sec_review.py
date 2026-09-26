import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import prepare_sec_review as m
import tempfile
import unittest

class SelectedReviewTests(unittest.TestCase):
    def fixture(self,d):
        raw=b'<html><div>Jordan Example has served as our Chief Operating Officer since 2020.</div><div>Jordan received an MBA from the University of</div><div>Michigan and a degree from Another College.</div></html>'
        text,blocks=m.text_blocks(raw)
        (d/'objects').mkdir()
        h=m.sha(raw); th=m.sha(text.encode())
        (d/'objects'/h).write_bytes(raw);(d/'objects'/th).write_text(text)
        packet={'lineage':{'current':{'accessionNumber':'test'}},'documents':[{'filing':{'accessionNumber':'test'},'source':{'content_sha256':h},'normalized_text_sha256':th}], 'metadata_artifacts':[], 'intake_record_id':'10000000-0000-4000-8000-000000000001'}
        selection={'name':'Jordan Example','title':'Chief Operating Officer','relationship':'Executive','first_block':0,'last_block':2,'relationship_first_block':0,'relationship_last_block':0,'search_terms':['University of Michigan']}
        return packet,selection
    def test_line_wrapped_literal_affiliation_preserves_exact_span(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,s=self.fixture(d);r=m.prepare(p,[s],d)
            self.assertIn('University of\nMichigan',r['people'][0]['biography']['excerpt'])
            self.assertFalse(r['publication_allowed'])
            self.assertEqual(r['rights_status'],'unreviewed')
            self.assertEqual(r,m.prepare(p,[s],d))
    def test_inferred_affiliation_or_wrong_person_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,s=self.fixture(d)
            for changed in ({'name':'Different Person'},{'search_terms':['Harvard']},{'title':'Chief Executive Officer'},{'relationship_last_block':3},{'first_block':-1}):
                with self.assertRaises(ValueError):m.prepare(p,[{**s,**changed}],d)
    def test_artifact_round_trip_and_sql_stays_private(self):
        import gzip,base64
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,s=self.fixture(d);r=m.prepare(p,[s],d)
            for h,n,b in m.artifacts(p,d):
                raw=gzip.decompress(base64.b64decode(b));self.assertEqual(m.sha(raw),h);self.assertEqual(len(raw),n)
            sql=m.export_sql(r,d)
            self.assertNotIn('insert into research.',sql)
            self.assertIn('ops.sec_review_packets',sql)
            self.assertIn('Immutable packet conflict',sql)
    def test_corrupt_normalized_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,s=self.fixture(d);p['documents'][0]['normalized_text_sha256']='a'*64
            with self.assertRaises(ValueError):m.prepare(p,[s],d)
