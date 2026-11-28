import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_lockup_review as importer
import build_holdings_review as holdings
from review_lockup import calendar_boundary, review_terms

COVER='Prospectus\nSeptember 17, 2026'
DEFINITION='Consent: prior written consent; for a period of 180 days after the date of this prospectus (such period, the “restricted period”).'
SCOPE='Our directors and executive officers have entered into lock-up agreements; with limited exceptions, for the restricted period, prior written consent is needed for securities convertible into or exercisable or exchangeable for our Class A common stock.'
EXCEPTIONS='Transfers subject in certain cases to various conditions; received shares would be subject to restrictions similar to existing ones. Representatives, in their sole discretion, may release securities in whole or in part at any time.'

class LockupTests(unittest.TestCase):
    def test_calendar_arithmetic_does_not_shift_holidays_weekends_or_leap_days(self):
        for start,days,end in [('2026-09-17',180,'2027-03-16'),('2024-02-28',1,'2024-02-29'),('2025-02-28',1,'2025-03-01'),('2026-12-31',1,'2027-01-01'),('2026-09-25',1,'2026-09-26')]:
            with self.subTest(start=start):self.assertEqual(calendar_boundary(start,days),end)

    def test_invalid_dates_and_durations_fail_closed(self):
        for d in [True,False,0,-1,731,180.5,'180',None]:
            with self.subTest(days=d),self.assertRaises(ValueError):calendar_boundary('2026-09-17',d)
        for s in ['2026-02-29','1999-01-01','2101-01-01','09/17/2026']:
            with self.subTest(date=s),self.assertRaises(ValueError):calendar_boundary(s,180)

    def test_exact_terms_preserve_conditional_not_cash_meaning(self):
        result=review_terms(COVER,DEFINITION,SCOPE,EXCEPTIONS,'2026-09-17',180)
        self.assertEqual(result['boundary_date'],'2027-03-16')
        self.assertIn('No present ownership',result['conditions'])
        self.assertNotIn('classification',result)

    def test_rejects_wrong_trigger_incomplete_scope_and_complex_schedules(self):
        original=[COVER,DEFINITION,SCOPE,EXCEPTIONS,'2026-09-17',180]
        changes=[(0,'Prospectus\nSeptember 21, 2026'),(0,COVER+'\nSeptember 18, 2026'),
                 (1,DEFINITION.replace('180 days','180 business days')),
                 (1,DEFINITION.replace('prospectus','closing')),(1,DEFINITION+' Early release applies.'),
                 (2,SCOPE.replace('have entered into','will enter into')),
                 (3,EXCEPTIONS.replace('in their sole discretion, may release','cannot release')),
                 (5,179)]
        for i,v in changes:
            args=original.copy();args[i]=v
            with self.subTest(change=v),self.assertRaises(ValueError):review_terms(*args)

    def test_full_source_import_is_private_reproducible_and_never_changes_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);(d/'objects').mkdir()
            lines=['Prospectus','September 17, 2026',DEFINITION,SCOPE,EXCEPTIONS,
                   'before this offering after this offering Class A Class B',
                   'The beneficial ownership of our common stock as of September 3, 2026, follows.',
                   'Jordan Example(1)','1,234','(1)Represents 1,234 shares of Class B common stock.',
                   'Our directors and executive officers have entered into lock-up agreements: 180 days after the date of this prospectus, limited exceptions, prior written consent, and representatives may release.']
            raw=''.join('<p>'+s+'</p>' for s in lines).encode();normalized,_=holdings.text_blocks(raw)
            (d/'objects'/holdings.sha(raw)).write_bytes(raw)
            f=dict(accessionNumber='0000000001-26-000001',form='424B4',filingDate='2026-09-21',fileNumber='333-123456')
            packet=dict(cik='0000000001',lineage=dict(current=f,root=f,status='metadata_resolved'),documents=[dict(filing=f,source=dict(content_sha256=holdings.sha(raw)),normalized_text_sha256=holdings.sha(normalized.encode()))])
            hreview=dict(profile='dated-pre-common',reviewed_on=date.today().isoformat(),holdings_as_of='2026-09-03',headers=dict(first=5,last=5),basis=dict(first=6,last=6),restriction=dict(first=10,last=10),restriction_literal='180 days after the date of this prospectus',positions=[dict(name='Jordan Example',row=dict(first=7,last=8),share_block=8,shares=1234,share_class='Class B common stock',footnote_number=1,footnote=dict(first=9,last=9))])
            manifest,_=holdings.build(packet,hreview,d)
            review=dict(reviewed_on=date.today().isoformat(),trigger_date='2026-09-17',days=180,cover=dict(first=0,last=1),definition=dict(first=2,last=2),scope=dict(first=3,last=3),exceptions=dict(first=4,last=4))
            m,sql=importer.build(packet,manifest,review,d)
            self.assertEqual((m,sql),importer.build(packet,manifest,review,d))
            self.assertEqual(m['terms']['boundary_date'],'2027-03-16')
            self.assertFalse(m['published']);self.assertEqual(len(m['spans']),4)
            self.assertIn("r.relationship in ('Executive','Director')",sql)
            for forbidden in ['insert into app.','update research.','market_prices','classification']:
                self.assertNotIn(forbidden,sql)
            wrong=copy.deepcopy(manifest);wrong['positions'][0]['shares']=1
            with self.assertRaises(ValueError):importer.build(packet,wrong,review,d)
            wrong=copy.deepcopy(review);wrong['cover']['first']=1
            with self.assertRaises(ValueError):importer.build(packet,manifest,wrong,d)
            wrong=copy.deepcopy(review);wrong['trigger_date']='2026-09-22'
            with self.assertRaises(ValueError):importer.build(packet,manifest,wrong,d)
