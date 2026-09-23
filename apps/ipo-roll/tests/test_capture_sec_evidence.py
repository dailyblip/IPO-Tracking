"""Synthetic fixtures: these tests do not assert live SEC verification."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
spec = importlib.util.spec_from_file_location('capture_sec', Path(__file__).parents[1] / 'scripts/capture_sec_evidence.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
CIK = '0000000001'
ROOT = dict(accessionNumber='0000000002-26-000001', filingDate='2026-08-01', form='S-1', fileNumber='333-123456', primaryDocument='root.htm')
FINAL = {**ROOT, 'accessionNumber':'0000000002-26-000002','filingDate':'2026-09-21','form':'424B4','primaryDocument':'final.htm'}
BIO = 'Jordan Example has served as our Chief Executive Officer since 2020. Jordan Example received a degree from the University of Michigan in 2001.'
def columns(rows):
    return {k:[r[k] for r in rows] for k in ROOT}
def save(d, url, raw):
    (d/'objects').mkdir(exist_ok=True)
    (d/'requests').mkdir(exist_ok=True)
    (d/'objects'/m.sha(raw)).write_bytes(raw)
    (d/'requests'/(m.sha(url.encode())+'.json')).write_text(json.dumps(dict(url=url,content_sha256=m.sha(raw),bytes=len(raw),retrieved_at='2026-09-23T00:00:00+00:00')))
class CaptureTests(unittest.TestCase):
    def test_lineage_excludes_parallel_registration(self):
        other = {**ROOT,'accessionNumber':'0000000002-26-000003','fileNumber':'333-999999'}
        result=m.resolve_lineage([other,ROOT,FINAL],FINAL['accessionNumber'])
        self.assertEqual(result['root'], ROOT)
        self.assertEqual(len(result['history']),2)
        for rows,number in (([FINAL,other],None),([ROOT,FINAL],'333-999999'),([ROOT,{**other,'fileNumber':ROOT['fileNumber']},FINAL],None),([ROOT,FINAL,{**FINAL,'fileNumber':'333-777777'}],None)):
            with self.assertRaises(ValueError): m.resolve_lineage(rows,FINAL['accessionNumber'],number)
    def test_hidden_content_and_inline_markup_offsets(self):
        raw=('<html><script>Fake University</script><div style="display:none">False Bio</div><ix:hidden>Hidden Fact</ix:hidden><p><b>Jordan Example</b> has served as our CEO since 2020. Jordan earned a degree from the <i>University of Michigan</i>.</p><p>Next paragraph.</p></html>').encode()
        text,blocks=m.text_blocks(raw)
        for hidden in ('Fake','False','Hidden'): self.assertNotIn(hidden,text)
        match=m.biography_candidates(blocks,['Jordan Example'])[0]
        self.assertEqual(text[match['locator']['start']:match['locator']['end']],match['excerpt'])
        self.assertNotIn('Next paragraph',match['excerpt'])
        self.assertFalse(match['approved'])
    def test_no_section_fallback_alias_inference_or_mixed_subjects(self):
        for passage in ('Management section. '+BIO,'Mr. Example graduated from the University of Michigan and has served on our board for ten years.',BIO+' Taylor Other also serves on the board.',BIO+' Additional Stanford reference.'):
            _,blocks=m.text_blocks(('<p>'+passage+'</p>').encode())
            self.assertEqual(m.biography_candidates(blocks,['Jordan Example','Taylor Other']),[])
    def test_url_controls(self):
        for url in ('https://evil.example/data.json','https://data.sec.gov@evil.example/submissions/CIK0000000001.json','https://data.sec.gov/submissions/../private.json'):
            with self.assertRaises(ValueError): m.valid_url(url)
        with self.assertRaises(ValueError): m.document_url(CIK,{**FINAL,'primaryDocument':'../bad.htm'})
        self.assertIn('/data/1/000000000226000002/',m.document_url(CIK,FINAL))
    def test_offline_end_to_end_captures_archived_root_without_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp)
            data={'cik':1,'filings':{'recent':columns([FINAL]),'files':[{'name':'CIK0000000001-submissions-001.json','filingCount':1}]}}
            save(d,'https://data.sec.gov/submissions/CIK0000000001.json',json.dumps(data).encode())
            save(d,'https://data.sec.gov/submissions/CIK0000000001-submissions-001.json',json.dumps(columns([ROOT])).encode())
            for f in (ROOT,FINAL): save(d,m.document_url(CIK,f),('<html><p>'+BIO+'</p></html>').encode())
            record={'id':'synthetic','values':{'cik':CIK,'accession_no':FINAL['accessionNumber'],'form':'424B4','filed':'2026-09-21'},'observations':[]}
            packet=m.capture(record,m.Archive(d),['Jordan Example'])
            self.assertFalse(packet['publication_allowed'])
            self.assertEqual(len(packet['metadata_artifacts']),2)
            self.assertEqual(len(packet['documents']),2)
            self.assertEqual(len(packet['documents'][1]['biography_candidates']),1)
            self.assertEqual(packet['lineage']['status'],'metadata_resolved')
            text_hash=packet['documents'][1]['normalized_text_sha256']
            self.assertEqual(m.sha((d/'objects'/text_hash).read_bytes()),text_hash)
    def test_corrupt_cache_or_missing_artifact_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); url='https://data.sec.gov/submissions/CIK0000000001.json'
            save(d,url,b'{}'); (d/'objects'/m.sha(b'{}')).write_bytes(b'changed')
            with self.assertRaises(ValueError): m.Archive(d).get(url)
            with self.assertRaises(ValueError): m.Archive(d).get(url.replace('0000000001','0000000002'))
    def test_live_contact_required_before_network(self):
        for agent in ('','Tests test@example.com','No contact'):
            with patch.dict(os.environ,{'SEC_EDGAR_USER_AGENT':agent}):
                with self.assertRaises(ValueError): m.Archive('/unused',fetch=True)
    def test_malformed_columns_fail_closed(self):
        bad=columns([ROOT]); bad['fileNumber']=[]
        with self.assertRaises(ValueError): m.column_rows(bad)
        with self.assertRaises(ValueError): m.column_rows(columns([{**ROOT,'filingDate':'2026-99-01'}]))
if __name__ == '__main__': unittest.main()
