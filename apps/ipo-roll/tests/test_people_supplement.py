import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_people_supplement as m


class PeopleSupplementTests(unittest.TestCase):
    def fixture(self, directory):
        raw = ('<p>Jordan Example has served as Chief Legal Officer since 2020. Previously Jordan worked at a company overseas.</p>'
               '<p>Jordan earned a degree from Example University.</p>'
               '<p>Taylor Sample is currently a director nominee and will join the board after the offering closes. Taylor has prior experience.</p>').encode()
        text, _ = m.text_blocks(raw)
        (directory/'objects').mkdir()
        (directory/'objects'/m.sha(raw)).write_bytes(raw)
        f = dict(accessionNumber='0000000001-26-000001',form='S-1',filingDate='2026-01-01',fileNumber='333-123456')
        packet = dict(cik='0000000001',lineage=dict(current=f,root=f,status='metadata_resolved'),documents=[dict(filing=f,source=dict(content_sha256=m.sha(raw)),normalized_text_sha256=m.sha(text.encode()))])
        review = dict(reviewed_on=date.today().isoformat(),people=[dict(name='Jordan Example',title='Chief Legal Officer',relationship='Executive',identity_reviewed=True,biography_complete_reviewed=True,biography=dict(first=0,last=1),relationship_evidence=dict(first=0,last=0))])
        return packet, review

    def test_supplement_preserves_complete_biography_and_is_deterministic(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp); p,r=self.fixture(d); manifest,sql=m.build(p,r,d)
            self.assertIn('Example University',sql)
            self.assertIn('biography_text',sql)
            self.assertIn('Canonical source or lineage mismatch',sql)
            self.assertIn('Biography conflict',sql)
            self.assertNotIn('insert into research.ownerships',sql)
            self.assertNotIn('update ',sql.lower())
            self.assertEqual((manifest,sql),m.build(p,r,d))
            self.assertFalse(manifest['published'])

    def test_discovery_does_not_require_previously_known_names_or_shareholdings(self):
        raw = b'<p>Jordan Example has served as Chief Legal Officer since 2020. Previously Jordan worked overseas.</p><p>Taylor Sample is currently a director nominee and will join upon completion. Prior work included accounting.</p>'
        _, blocks=m.text_blocks(raw)
        candidates=m.discover(blocks)
        self.assertEqual([c['name'] for c in candidates],['Jordan Example','Taylor Sample'])
        self.assertTrue(all(c['review_status']=='unreviewed' and not c['biography_complete'] for c in candidates))

    def test_factual_education_is_not_filtered_by_institution(self):
        from capture_sec_evidence import biography_candidates
        from prepare_sec_review import passage
        for school in ('Stanford University', 'University of Michigan', 'Harvard University'):
            text, blocks=m.text_blocks(('<p>Jordan Example has served as our Chief Legal Officer since 2020. Jordan earned a degree from '+school+'.</p>').encode())
            candidates=biography_candidates(blocks, [])
            self.assertEqual(len(candidates),1)
            self.assertFalse(candidates[0]['approved'])
            self.assertIn(school,passage(blocks,0,0,text)['excerpt'])

    def test_credentials_do_not_make_the_same_subject_look_like_two_people(self):
        from capture_sec_evidence import biography_candidates
        _,blocks=m.text_blocks(b'<p>Jordan Example, PhD has served as our Chief Medical Officer since 2020. Jordan earned a degree from Example University.</p>')
        candidates=biography_candidates(blocks,['Jordan Example'])
        self.assertEqual([p['name'] for p in candidates],['Jordan Example, PhD'])
        self.assertEqual(candidates[0]['identity_status'],'unverified')

    def test_capture_uses_independent_names_and_flags_partial_biographies(self):
        from capture_sec_evidence import biography_candidates
        raw = b'<p>Jordan Example is expected to join our board on completion of this offering. Jordan previously worked in accounting.</p><p>Prior to this offering, there has been no public market for our common stock and no listing has been approved.</p>'
        _, blocks=m.text_blocks(raw)
        candidates=biography_candidates(blocks, [])
        self.assertEqual([c['name'] for c in candidates],['Jordan Example'])
        self.assertFalse(candidates[0]['biography_complete'])
        self.assertFalse(candidates[0]['approved'])
        _, wrapped=m.text_blocks(b'<p>Jordan Example is our Chief Legal Officer.</p><p>Additional biography continues in another block.</p>')
        self.assertEqual(biography_candidates(wrapped,[])[0]['name'],'Jordan Example')

    def test_coverage_audit_keeps_missing_sources_distinct_from_zero_candidates(self):
        from audit_people_coverage import audit
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            h=p['documents'][0]['source']['content_sha256']
            rows=[dict(offering_id='a',source_sha256=h,people=['Jordan Example']),dict(offering_id='b',source_sha256='0'*64,people=[])]
            result=audit(rows,[d])
            self.assertEqual(result['counts']['sources_scanned'],1)
            self.assertEqual(result['counts']['sources_unavailable'],1)
            self.assertEqual(result['offerings'][0]['unmatched_candidates'][0]['name'],'Taylor Sample')
            self.assertNotIn('candidates',result['offerings'][1])
            (d/'objects'/h).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):audit(rows,[d])

    def test_rejects_wrong_identity_incomplete_review_and_corrupt_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            for key,val in [('name','Someone Else'),('title','Chief Financial Officer'),('identity_reviewed',False),('biography_complete_reviewed',False),('relationship','Investor')]:
                bad=copy.deepcopy(r);bad['people'][0][key]=val
                with self.subTest(key=key),self.assertRaises(ValueError):m.build(p,bad,d)
            bad=copy.deepcopy(r);bad['people']*=2
            with self.assertRaises(ValueError):m.build(p,bad,d)
            bad=copy.deepcopy(p);bad['documents'][0]['normalized_text_sha256']='0'*64
            with self.assertRaises(ValueError):m.build(bad,r,d)
            path=d/'objects'/p['documents'][0]['source']['content_sha256'];path.write_bytes(b'corrupt')
            with self.assertRaises(ValueError):m.build(p,r,d)

    def test_roster_only_record_requires_explicit_missing_biography_disposition(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d);person=r['people'][0];del person['biography']
            with self.assertRaises(ValueError):m.build(p,r,d)
            person['biography_status']='not_found_in_reviewed_filing'
            manifest,sql=m.build(p,r,d)
            self.assertIsNone(manifest['people'][0]['biography_span'])
            self.assertNotIn('insert into research.biographies',sql)


if __name__ == '__main__':
    unittest.main()
