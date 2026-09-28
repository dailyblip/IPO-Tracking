import copy
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
from reconcile_people_roster import reconcile
from capture_sec_evidence import sha, text_blocks
from build_internal_pilot import uid


class RosterReconciliationTests(unittest.TestCase):
    def fixture(self, directory):
        raw = b'<p>Management</p><p>Jordan Example</p><p>Chief Legal Officer</p><p>Biographies</p><p>Jordan Example serves as our Chief Legal Officer. Jordan attended Stanford University.</p><p>Principal stockholders</p><p>Example Fund LLC</p><p>All officers as a group</p>'
        text, blocks = text_blocks(raw)
        source = sha(raw)
        (directory/'objects').mkdir()
        (directory/'objects'/source).write_bytes(raw)
        f = dict(accessionNumber='0000000001-26-000001',form='S-1',filingDate='2026-01-01',fileNumber='333-123456')
        packet = dict(cik='0000000001',lineage=dict(current=f,root=f,status='metadata_resolved'),documents=[dict(filing=f,source=dict(content_sha256=source),normalized_text_sha256=sha(text.encode()))])
        identity=dict(offering_id=uid('offering',packet['cik'],f['accessionNumber']),source_sha256=source)
        person=dict(kind='person',label='Jordan Example',canonical_name='Jordan Example',identity_reviewed=True)
        review=dict(**identity,sections=[dict(kind='management_table',first=0,last=2,boundaries_reviewed=True,parts=[dict(kind='context',first=0,last=0,reason='Section heading'),dict(**person,first=1,last=2)]),dict(kind='management_biographies',first=3,last=4,boundaries_reviewed=True,parts=[dict(kind='context',first=3,last=3,reason='Section heading'),dict(**person,first=4,last=4,complete_biography_reviewed=True)])])
        snapshot=dict(**identity,observed_at='2026-09-27T12:00:00Z',people=[dict(name='Jordan Example',biographies=[dict(source_sha256=source,excerpt=blocks[4]['text'])])])
        return packet,review,snapshot

    def test_complete_management_never_implies_complete_ownership(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            result=reconcile(p,r,s,d)
            self.assertTrue(result['management_complete'])
            self.assertFalse(result['company_complete'])
            self.assertEqual(result['ownership_table_status'],'not_reviewed')
            self.assertEqual(result['holdings_coverage'],'not_assessed')

    def test_missing_person_and_truncated_or_wrong_source_bio_fail_coverage(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            for change in ('missing','truncated','wrong_source'):
                bad=copy.deepcopy(s)
                if change=='missing':bad['people']=[]
                elif change=='truncated':bad['people'][0]['biographies'][0]['excerpt']='Jordan Example serves as our Chief Legal Officer.'
                else:bad['people'][0]['biographies'][0]['source_sha256']='0'*64
                self.assertFalse(reconcile(p,r,bad,d)['management_complete'])

    def test_rejects_missing_overlapping_and_unreviewed_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            for change in ('gap','overlap','boundary','label','identity','alias'):
                bad=copy.deepcopy(r);section=bad['sections'][0]
                if change=='gap':section['parts'][1]['last']=1
                elif change=='overlap':section['parts'][1]['first']=0
                elif change=='boundary':section['boundaries_reviewed']=False
                elif change=='label':section['parts'][1]['label']='Someone Else'
                elif change=='identity':section['parts'][1]['identity_reviewed']=False
                else:section['parts'][1]['canonical_name']='J. Example'
                with self.subTest(change=change),self.assertRaises(ValueError):reconcile(p,bad,s,d)

    def test_entities_and_groups_remain_pending_and_separate_from_people(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            r['sections'].append(dict(kind='ownership_table',first=5,last=7,boundaries_reviewed=True,parts=[dict(kind='context',first=5,last=5,reason='Table heading'),dict(kind='organization',first=6,last=6,label='Example Fund LLC'),dict(kind='group',first=7,last=7,label='All officers as a group')]))
            result=reconcile(p,r,s,d)
            self.assertEqual(result['sections'][-1]['pending'],2)
            self.assertFalse(result['company_complete'])
            self.assertEqual(len(s['people']),1)

    def test_stale_identity_duplicate_people_and_corrupt_artifacts_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            bad=copy.deepcopy(s);bad['offering_id']='other'
            with self.assertRaises(ValueError):reconcile(p,r,bad,d)
            bad=copy.deepcopy(s);bad['people']*=2
            with self.assertRaises(ValueError):reconcile(p,r,bad,d)
            (d/'objects'/s['source_sha256']).write_bytes(b'corrupt')
            with self.assertRaises(ValueError):reconcile(p,r,s,d)

    def test_named_footnote_controllers_cannot_disappear_into_a_reviewed_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r,s=self.fixture(d)
            raw=(d/'objects'/s['source_sha256']).read_bytes()
            raw+=b'<p>(1) Alex Controller and Casey Partner manage Example Fund GP and may be deemed to share voting authority. No personal economic ownership is established.</p>'
            source=sha(raw);(d/'objects'/source).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=source
            p['documents'][0]['normalized_text_sha256']=sha(text_blocks(raw)[0].encode())
            r['source_sha256']=s['source_sha256']=source
            s['people'][0]['biographies'][0]['source_sha256']=source
            part=dict(kind='footnote',first=8,last=8,label='(1)',named_people_reviewed=True,
                      named_people=[dict(name=n,attribution_reviewed=True,
                                         attribution_kind='shared_voting_dispositive',
                                         reason='Source names fund GP managers, not personal economic quantities.')
                                    for n in ('Alex Controller','Casey Partner')])
            r['sections'].append(dict(kind='ownership_footnotes',first=8,last=8,boundaries_reviewed=True,parts=[part]))
            result=reconcile(p,r,s,d)
            self.assertEqual(result['missing_named_footnote_people'],['Alex Controller','Casey Partner'])
            s['people'] += [dict(name=n,biographies=[]) for n in result['missing_named_footnote_people']]
            result=reconcile(p,r,s,d)
            self.assertEqual(result['missing_named_footnote_people'],[])
            self.assertFalse(result['company_complete'])
            self.assertEqual(result['sections'][-1]['pending'],1)
            for change in ('unreviewed','wrong_name','inferred_ownership','duplicate'):
                bad=copy.deepcopy(r);part=bad['sections'][-1]['parts'][0]
                if change=='unreviewed':part['named_people_reviewed']=False
                elif change=='wrong_name':part['named_people'][0]['name']='Other Person'
                elif change=='inferred_ownership':part['named_people'][0]['attribution_kind']='personal_ownership'
                else:part['named_people']*=2
                with self.subTest(change=change),self.assertRaises(ValueError):reconcile(p,bad,s,d)


if __name__ == '__main__':
    unittest.main()
