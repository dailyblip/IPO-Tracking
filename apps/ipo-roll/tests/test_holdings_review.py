import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_holdings_review as m


class HoldingsReviewTests(unittest.TestCase):
    def fixture(self, directory):
        lines = ['Shares of Common Stock Beneficially Owned After this Offering',
                 'Shares of Class A Common Stock', 'Assumptions after the offering.',
                 'Jordan Example(3)', '1,234', '(3)Includes 100 shares held in trust.',
                 'We will sign lock-up agreements for not less than 180 days from the date of this prospectus without prior written consent, subject to certain exceptions.']
        raw = ''.join('<p>'+s+'</p>' for s in lines).encode()
        text, _ = m.text_blocks(raw)
        (directory/'objects').mkdir()
        (directory/'objects'/m.sha(raw)).write_bytes(raw)
        current = dict(accessionNumber='0000000001-26-000001',form='S-1/A',filingDate='2026-09-01',fileNumber='333-123456')
        packet = dict(cik='0000000001',lineage=dict(current=current,root=current,status='metadata_resolved'),documents=[dict(filing=current,source=dict(content_sha256=m.sha(raw)),normalized_text_sha256=m.sha(text.encode()))])
        review = dict(reviewed_on=date.today().isoformat(),headers=dict(first=0,last=1),basis=dict(first=2,last=2),restriction=dict(first=6,last=6),restriction_literal='not less than 180 days',positions=[dict(name='Jordan Example',row=dict(first=3,last=4),share_block=4,shares=1234,footnote_number=3,footnote=dict(first=5,last=5))])
        return packet,review

    def test_retains_evidence_and_never_promotes_to_current_wealth(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d);manifest,sql=m.build(p,r,d)
            self.assertEqual((manifest,sql),m.build(p,r,d))
            self.assertFalse(manifest['published'])
            self.assertEqual(manifest['positions'][0]['shares'],1234)
            self.assertIn("'post',1234",sql)
            self.assertIn("'unknown'",sql)
            self.assertNotIn('insert into app.',sql)
            self.assertNotIn('insert into research.roles',sql)
            self.assertNotIn('market_prices',sql)
            self.assertIn('Manifest conflict',sql)

    def test_rejects_identity_count_footnote_and_header_mismatches(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d)
            for field,value in [('name','Jordan Other'),('shares',123),('share_block',2),('footnote_number',4)]:
                changed=copy.deepcopy(r);changed['positions'][0][field]=value
                with self.subTest(field=field),self.assertRaises(ValueError):m.build(p,changed,d)
            changed=copy.deepcopy(r);changed['headers']=dict(first=2,last=2)
            with self.assertRaises(ValueError):m.build(p,changed,d)

    def test_rejects_corrupt_source_and_unsupported_lifecycle(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d)
            changed=copy.deepcopy(p);changed['lineage']['current']['form']='424B4'
            with self.assertRaises(ValueError):m.build(changed,r,d)
            h=p['documents'][0]['source']['content_sha256'];(d/'objects'/h).write_bytes(b'changed')
            with self.assertRaises(ValueError):m.build(p,r,d)

    def test_rejects_unsupported_restriction_and_duplicate_position(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d)
            changed=copy.deepcopy(r);changed['restriction_literal']='90 days'
            with self.assertRaises(ValueError):m.build(p,changed,d)
            changed=copy.deepcopy(r);changed['positions']*=2
            with self.assertRaises(ValueError):m.build(p,changed,d)
