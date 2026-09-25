import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_holdings_review as m
from review_components import parse_components

NOTE = '(5) Consists of (i) 1,000 shares of common stock directly held by Jordan Example, (ii) 200 shares of common stock directly held by family trusts of which Mr. Example or his spouse serves as trustee, (iii) 30 shares of common stock underlying RSUs directly held by Mr. Example that vest and settle within 60 days of September 15, 2026, and (iv) 400 shares of common stock underlying stock options directly held by Mr. Example that are currently exercisable or would be exercisable within 60 days of September 15, 2026.'

class ComponentsTests(unittest.TestCase):
    def parse(self,note=NOTE,total=1630):
        return parse_components(note,'5','Jordan Example','September 15, 2026',total)

    def test_complete_reconciled_components_keep_instruments_and_attribution(self):
        rows=self.parse()
        self.assertEqual([r['instrument'] for r in rows],['common_share','common_share','rsu','option'])
        self.assertEqual([r['quantity'] for r in rows],[1000,200,30,400])
        self.assertEqual([r['attribution'] for r in rows],['direct','trust_or_family','direct','direct'])

    def test_rejects_unresolved_or_invented_facts(self):
        for before,after in [('Jordan Example','Other Person'),('RSUs','warrants'),('September 15','September 16'),('(ii)','(i)'),('1,000','1,00'),('1,000','0'),('family trusts of which Mr. Example or his spouse serves as trustee','Example Investment Fund')]:
            with self.subTest(before=before),self.assertRaises(ValueError):self.parse(NOTE.replace(before,after))
        with self.assertRaises(ValueError):self.parse(total=1631)
        with self.assertRaises(ValueError):self.parse(NOTE+' Additional 100 options are not included.')

    def test_trust_rsus_require_resolved_antecedent(self):
        note='(5) Consists of (i) 1,000 shares of common stock directly held by a family trust of which Jordan Example serves as trustee and (ii) 30 shares of common stock underlying RSUs directly held by the family trust that vest and settle within 60 days of September 15, 2026.'
        rows=self.parse(note,1030)
        self.assertTrue(all(r['attribution']=='trust_or_family' for r in rows))
        with self.assertRaises(ValueError):self.parse(note.replace('a family trust of which Jordan Example serves as trustee','Jordan Example'),1030)

    def test_full_import_is_private_reconciled_and_never_valued(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);(d/'objects').mkdir()
            lines=['Owned Before This Offering / Owned After This Offering',
                   'The beneficial ownership of our common stock as of September 15, 2026, gives effect to Preferred Stock Conversion, SAFE Conversion and RSU Net Settlement.',
                   'Jordan Example(5)','1,630 1% 1,630',NOTE,
                   'all of our directors and executive officers: 180 days from the date of this prospectus; various intervals; stock price exceeds certain thresholds; ability to release.']
            raw=''.join('<p>'+s+'</p>' for s in lines).encode();text,_=m.text_blocks(raw)
            (d/'objects'/m.sha(raw)).write_bytes(raw)
            f=dict(accessionNumber='0000000001-26-000001',form='S-1/A',filingDate='2026-09-21',fileNumber='333-123456')
            p=dict(cik='0000000001',lineage=dict(current=f,root=f,status='metadata_resolved'),documents=[dict(filing=f,source=dict(content_sha256=m.sha(raw)),normalized_text_sha256=m.sha(text.encode()))])
            r=dict(profile='reviewed-mixed-awards',reviewed_on=date.today().isoformat(),holdings_as_of='2026-09-15',headers=dict(first=0,last=0),basis=dict(first=1,last=1),restriction=dict(first=5,last=5),restriction_literal='various intervals',positions=[dict(name='Jordan Example',row=dict(first=2,last=3),share_block=3,shares=1630,footnote_number=5,footnote=dict(first=4,last=4))])
            manifest,sql=m.build(p,r,d)
            self.assertEqual(len(manifest['positions']),1)
            self.assertEqual(len(manifest['positions'][0]['components']),4)
            self.assertEqual((manifest,sql),m.build(p,r,d))
            self.assertIn("'beneficial_total'",sql)
            self.assertIn("'unknown'",sql)
            self.assertNotIn('insert into app.',sql)
            self.assertNotIn('market_prices',sql)
            wrong=copy.deepcopy(r);wrong['positions'][0]['shares']=2000
            with self.assertRaises(ValueError):m.build(p,wrong,d)
