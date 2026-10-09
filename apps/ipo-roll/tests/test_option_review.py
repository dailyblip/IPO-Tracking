import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_holdings_review as m
from review_options import parse_pre_options


class OptionReviewTests(unittest.TestCase):
    def note(self, repurchase=True):
        return ('(8) The number of shares beneficially owned prior to the offering consists of 1,200 shares of common stock subject to options that are exercisable within 60 days of August 1, 2026, but excludes any shares distributed to Dr. Example in connection with the LLC Distribution. In connection with the LLC Distribution, Dr. Example received 300 shares of common stock issuable upon conversion of our Series A redeemable convertible preferred stock'
                + (', of which 100 shares of Series A redeemable convertible preferred stock remain subject to a right of repurchase in our favor' if repurchase else '')
                + '. The shares received upon the LLC Distribution are included in the number of shares beneficially owned after the offering.')

    def fixture(self, directory, note=None, cell='1,200 3.4 % 1,500 3.0 %'):
        lines = ['SHARES BENEFICIALLY OWNED PRIOR TO OFFERING SHARES BENEFICIALLY OWNED AFTER OFFERING NUMBER PERCENTAGE',
                 'The beneficial ownership of our capital stock as of August 1, 2026, is shown. Applicable percentage ownership before the offering assumes automatic conversion of all outstanding shares of our redeemable convertible preferred stock. Options exercisable within 60 days of August 1, 2026 are included. This does not reflect any potential purchases.',
                 'Jordan Example, Ph.D. (8)', cell, note or self.note(),
                 'We, our officers, directors have agreed, subject to specified exceptions, for 180 days after the date of this prospectus with prior written consent. Transfers upon exercise are allowed but underlying shares of common stock shall continue to be subject to restrictions. Representatives may, in their sole discretion, release all or any portion.']
        raw = ''.join('<p>'+s+'</p>' for s in lines).encode()
        text, _ = m.text_blocks(raw)
        (directory/'objects').mkdir(exist_ok=True)
        (directory/'objects'/m.sha(raw)).write_bytes(raw)
        current = dict(accessionNumber='0000000001-26-000003',form='424B4',filingDate='2026-09-18',fileNumber='333-123456')
        packet = dict(cik='0000000001',lineage=dict(current=current,root=current,status='metadata_resolved'),documents=[dict(filing=current,source=dict(content_sha256=m.sha(raw)),normalized_text_sha256=m.sha(text.encode()))])
        review = dict(profile='dated-pre-options',reviewed_on=date.today().isoformat(),holdings_as_of='2026-08-01',headers=dict(first=0,last=0),basis=dict(first=1,last=1),restriction=dict(first=5,last=5),restriction_literal='180 days after the date of this prospectus',positions=[dict(name='Jordan Example, Ph.D.',row=dict(first=2,last=3),share_block=3,shares=1200,footnote_number=8,footnote=dict(first=4,last=4))])
        return packet, review

    def test_one_option_component_not_issued_shares_or_post_distribution(self):
        for repurchase in (True, False):
            c = parse_pre_options(self.note(repurchase), '8', 'Jordan Example, Ph.D.', 'August 1, 2026', 1200, 1500)
            self.assertEqual(len(c), 1)
            self.assertEqual((c[0]['instrument'], c[0]['quantity'], c[0]['attribution']), ('option',1200,'unknown'))

    def test_rejects_unreviewed_identity_date_instrument_or_tail(self):
        for note in [self.note().replace('Dr. Example','Dr. Other'), self.note().replace('August 1','August 2'),
                     self.note().replace('options that are exercisable','RSUs that vest'),
                     self.note()+' Also includes 100 trust shares.', self.note().replace('of which 100','of which 400')]:
            with self.subTest(note=note), self.assertRaises(ValueError):
                parse_pre_options(note,'8','Jordan Example, Ph.D.','August 1, 2026',1200,1500)

    def test_requires_reconciled_complete_post_column(self):
        for cell in ['1,200 3.4 % 1,501 3.0 %','1,200 3.4 % — —','1,200 3.4 % 1,500 3.0 % 100', '1,200 3.4 % 1,50,0 3.0 %']:
            with tempfile.TemporaryDirectory() as t:
                d=Path(t);p,r=self.fixture(d,cell=cell)
                with self.subTest(cell=cell),self.assertRaises(ValueError):m.build(p,r,d)

    def test_replay_and_conservative_sql(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d);manifest,sql=m.build(p,r,d)
            self.assertEqual((manifest,sql),m.build(p,r,d))
            position=manifest['positions'][0]
            self.assertEqual(position['quantity_kind'],'beneficial_total')
            self.assertEqual(position['position_basis'],'pre')
            self.assertEqual(position['holdings_as_of'],'2026-08-01')
            self.assertIn("'Common stock underlying options','pre',1200",sql)
            self.assertIn("'option',1200,'unknown'",sql)
            self.assertIn("'unknown'",sql)
            for forbidden in ['insert into app.', 'insert into research.roles', 'market_prices', 'lockup_end']:
                self.assertNotIn(forbidden,sql)

    def test_requires_final_source_date_basis_and_named_row(self):
        with tempfile.TemporaryDirectory() as t:
            d=Path(t);p,r=self.fixture(d)
            for field,value in [('holdings_as_of','2026-08-02'),('basis',dict(first=0,last=0))]:
                changed=copy.deepcopy(r);changed[field]=value
                with self.assertRaises(ValueError):m.build(p,changed,d)
            changed=copy.deepcopy(r);changed['positions'][0]['name']='Someone Else'
            with self.assertRaises(ValueError):m.build(p,changed,d)
            changed=copy.deepcopy(p);changed['lineage']['current']['form']='S-1/A'
            with self.assertRaises(ValueError):m.build(changed,r,d)
