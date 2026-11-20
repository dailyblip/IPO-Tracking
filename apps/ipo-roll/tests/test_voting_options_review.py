import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / 'scripts'))
import build_holdings_review as m
from review_voting_options import parse_voting_options


class VotingOptionReviewTests(unittest.TestCase):
    def note(self):
        return ('(5) Consists of (i) 91,998 shares of common stock and '
                '(ii) 1,188,945 shares of common stock underlying outstanding stock options '
                'exercisable within 60 days of October 31, 2025.')

    def fixture(self, directory):
        lines = [
            'Number of shares of voting common stock beneficially owned Number of Class A common stock beneficially owned Percentage of shares beneficially owned Name of beneficial owner Before offering After offering',
            ('The following table sets forth certain information regarding beneficial ownership of our capital stock as of October 31, 2025: '
             'after giving effect to the automatic conversion of all of our redeemable convertible preferred stock. In computing the number of shares '
             'beneficially owned, shares of common stock subject to options held by such person that are currently exercisable or will become exercisable '
             'within 60 days of October 31, 2025, are considered outstanding.'),
            'Matthew Roden, PhD(5)', '1,280,943 — 3.6% 2.4%', self.note(),
            ('Our directors and executive officers have entered into lock-up agreements, with limited exceptions, for 180 days after the date of this prospectus '
             'without the prior written consent of the underwriters. The lock-up securities include securities which may be issued upon exercise of a stock option '
             'or warrant. Any lock-up securities received upon such exercise would remain restricted. The underwriters may release those securities.'),
        ]
        raw = ''.join('<p>'+line+'</p>' for line in lines).encode()
        text, _ = m.text_blocks(raw)
        (directory/'objects').mkdir()
        (directory/'objects'/m.sha(raw)).write_bytes(raw)
        current = dict(accessionNumber='0001193125-26-009078', form='424B4',
                       filingDate='2026-01-09', fileNumber='333-292283')
        packet = dict(cik='0002035832',
                      lineage=dict(current=current, root=current, status='metadata_resolved'),
                      documents=[dict(filing=current,
                                      source=dict(content_sha256=m.sha(raw)),
                                      normalized_text_sha256=m.sha(text.encode()))])
        review = dict(
            profile='dated-voting-options', reviewed_on=date.today().isoformat(),
            holdings_as_of='2025-10-31', headers=dict(first=0, last=0),
            basis=dict(first=1, last=1), restriction=dict(first=5, last=5),
            restriction_literal='180 days after the date of this prospectus',
            positions=[dict(name='Matthew Roden', row_name='Matthew Roden, PhD',
                            row=dict(first=2, last=3), share_block=3, shares=1280943,
                            footnote_number=5, footnote=dict(first=4, last=4))])
        return packet, review

    def test_reconciles_common_and_option_components(self):
        components = parse_voting_options(self.note(), '5', 'October 31, 2025', 1280943)
        self.assertEqual([(c['instrument'], c['quantity'], c['attribution']) for c in components], [
            ('common_share', 91998, 'unknown'), ('option', 1188945, 'unknown')])

    def test_reconciles_supported_option_only_shape(self):
        note = ('(6) Consists of 124,805 shares of common stock underlying outstanding stock options '
                'exercisable within 60 days of October 31, 2025.')
        components = parse_voting_options(note, '6', 'October 31, 2025', 124805)
        self.assertEqual([(c['instrument'], c['quantity']) for c in components], [('option', 124805)])

    def test_rejects_mismatch_date_or_extra_attribution(self):
        changes = [
            (self.note(), '5', 'October 31, 2025', 1280944),
            (self.note(), '5', 'October 30, 2025', 1280943),
            (self.note()+' Includes trust shares.', '5', 'October 31, 2025', 1280943),
            (self.note().replace('stock options', 'restricted stock units'), '5', 'October 31, 2025', 1280943),
        ]
        for args in changes:
            with self.subTest(args=args), self.assertRaises(ValueError):
                parse_voting_options(*args)

    def test_builds_replay_safe_unknown_position(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); packet, review = self.fixture(d)
            manifest, sql = m.build(packet, review, d)
            self.assertEqual((manifest, sql), m.build(packet, review, d))
            position = manifest['positions'][0]
            self.assertEqual(position['quantity_kind'], 'beneficial_total')
            self.assertEqual(position['share_class'], 'Voting common stock and underlying options')
            self.assertEqual(position['holdings_as_of'], '2025-10-31')
            self.assertEqual(len(position['components']), 2)
            self.assertIn("'unknown'", sql)
            for forbidden in ('insert into app.', 'insert into research.roles', 'market_prices', 'lockup_end'):
                self.assertNotIn(forbidden, sql)

    def test_requires_exact_source_name_final_form_basis_and_row(self):
        with tempfile.TemporaryDirectory() as t:
            d = Path(t); packet, review = self.fixture(d)
            changes = []
            changed = copy.deepcopy(review); changed['positions'][0].pop('row_name'); changes.append((packet, changed))
            changed = copy.deepcopy(review); changed['positions'][0]['row_name'] = 'Matthew Roden'; changes.append((packet, changed))
            changed = copy.deepcopy(review); changed['positions'][0]['shares'] = 1280942; changes.append((packet, changed))
            changed = copy.deepcopy(review); changed['holdings_as_of'] = '2025-10-30'; changes.append((packet, changed))
            changed_packet = copy.deepcopy(packet); changed_packet['lineage']['current']['form'] = 'S-1/A'; changes.append((changed_packet, review))
            for changed_packet, changed_review in changes:
                with self.subTest(review=changed_review), self.assertRaises(ValueError):
                    m.build(changed_packet, changed_review, d)


if __name__ == '__main__':
    unittest.main()
