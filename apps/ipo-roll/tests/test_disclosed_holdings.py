import copy
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
sys.path.insert(0,str(Path(__file__).parents[1]/'scripts'))
import build_disclosed_holdings as m


class DisclosedHoldingsTests(unittest.TestCase):
    def fixture(self,d):
        raw=b'<p>Common Stock Before offering After offering</p><p>Ownership as of January 1, 2026 includes awards and trust attribution.</p><table><tr><td>Jordan Example</td><td>1,000</td><td>5 %</td><td>0</td><td>0 %</td></tr></table><p>(1) The total includes options. Saleability is not established.</p>'
        text,blocks=m.text_blocks(raw);(d/'objects').mkdir();(d/'objects'/m.sha(raw)).write_bytes(raw)
        filing=dict(accessionNumber='0000000001-26-000001',form='424B4',filingDate='2026-01-02',fileNumber='333-123456')
        p=dict(cik='0000000001',lineage=dict(status='metadata_resolved',current=filing,root=filing),documents=[dict(filing=filing,source=dict(content_sha256=m.sha(raw)),normalized_text_sha256=m.sha(text.encode()))])
        start=next(b['index'] for b in blocks if 'Jordan Example' in b['text']);end=next(b['index'] for b in blocks if '(1)' in b['text'])
        r=dict(reviewed_on=date.today().isoformat(),column_order_reviewed=True,basis_review='Full table and ordered cells reviewed.',headers=dict(first=0,last=0),basis=dict(first=1,last=1),holdings_as_of='2026-01-01',columns=[dict(key='pre',kind='quantity',position_basis='pre',header_literal='Before offering'),dict(key='pre_pct',kind='percent'),dict(key='post',kind='quantity',position_basis='post',header_literal='After offering'),dict(key='post_pct',kind='percent')],people=[dict(name='Jordan Example',source_label='Jordan Example',identity_reviewed=True,row=dict(first=start,last=end-1),cells=['1,000','5 %','0','0 %'],share_class='Common Stock',footnotes=[dict(first=end,last=end)],interpretation_note='Includes awards; decomposition and saleability are unknown.')])
        return p,r

    def test_reported_totals_are_independent_of_liquidity_and_replay_safe(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d);manifest,sql=m.build(p,r,d)
            self.assertEqual([x['shares'] for x in manifest['positions']],[1000,0])
            self.assertEqual([x['position_basis'] for x in manifest['positions']],['pre','post'])
            self.assertIn("'beneficial_total'",sql);self.assertIn("'unknown'",sql)
            self.assertNotIn('insert into research.ownership_components',sql)
            self.assertNotIn('update ',sql.lower())
            self.assertNotIn('market_prices',sql)
            self.assertIn('Existing holding requires explicit overlap review',sql)
            self.assertIn('Manifest conflict',sql)
            self.assertEqual((manifest,sql),m.build(p,r,d))

    def test_dash_zero_and_invalid_quantities(self):
        self.assertIsNone(m.quantity('—'));self.assertIsNone(m.quantity('*'))
        self.assertEqual(m.quantity('0'),0)
        self.assertEqual(m.quantity('1,234'),1234)
        for v in ('1,23','-1','1.2','1e3','9007199254740992','12 34','00'):
                with self.subTest(v=v),self.assertRaises(ValueError):m.quantity(v)

    def test_zero_width_edgar_table_spacing_is_ignored_for_row_identity(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            doc=p['documents'][0]
            raw=(d/'objects'/doc['source']['content_sha256']).read_bytes()
            raw=raw.replace(b'<td>1,000</td>',b'<td>\xe2\x80\x8b 1,000 \xe2\x80\x8b</td>')
            source=m.sha(raw);text,_=m.text_blocks(raw);(d/'objects'/source).write_bytes(raw)
            doc['source']['content_sha256']=source;doc['normalized_text_sha256']=m.sha(text.encode())
            manifest,_=m.build(p,r,d)
            self.assertEqual(manifest['positions'][0]['shares'],1000)

    def test_percent_cells_allow_table_header_percent_convention_but_reject_out_of_range(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            r['people'][0]['cells'][1]='58.74';r['people'][0]['cells'][3]='100'
            raw=(d/'objects'/p['documents'][0]['source']['content_sha256']).read_bytes().replace(b'5 %',b'58.74').replace(b'0 %',b'100')
            source=m.sha(raw);text,_=m.text_blocks(raw);(d/'objects'/source).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=source;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            m.build(p,r,d)
            for invalid in ('100.1','101','1e2'):
                bad=copy.deepcopy(r);bad['people'][0]['cells'][1]=invalid
                with self.subTest(invalid=invalid),self.assertRaises(ValueError):m.build(p,bad,d)

    def test_dash_percent_cells_remain_undisclosed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            r['people'][0]['cells'][1]='— %';r['people'][0]['cells'][3]='— %'
            raw=(d/'objects'/p['documents'][0]['source']['content_sha256']).read_bytes().replace(b'5 %',b'\xe2\x80\x94 %').replace(b'0 %',b'\xe2\x80\x94 %')
            source=m.sha(raw);text,_=m.text_blocks(raw);(d/'objects'/source).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=source;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            manifest,_=m.build(p,r,d)
            self.assertEqual([x['shares'] for x in manifest['positions']],[1000,0])

    def test_wrong_row_columns_identity_header_class_date_and_source_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            for change in ('quantity','order','identity','alias','header','class','date','review','source','scenario'):
                pp=copy.deepcopy(p);rr=copy.deepcopy(r);person=rr['people'][0]
                if change=='quantity':person['cells'][0]='1,001'
                elif change=='order':person['cells'][0],person['cells'][2]=person['cells'][2],person['cells'][0]
                elif change=='identity':person['identity_reviewed']=False
                elif change=='alias':person['name']='Someone Else'
                elif change=='header':rr['columns'][0]['header_literal']='Different column'
                elif change=='class':person['share_class']='Class B'
                elif change=='date':rr['holdings_as_of']='2026-01-03'
                elif change=='review':rr['column_order_reviewed']=False
                elif change=='scenario':rr['columns'][2]['position_basis']='pre'
                else:pp['documents'][0]['normalized_text_sha256']='0'*64
                with self.subTest(change=change),self.assertRaises(ValueError):m.build(pp,rr,d)

    def test_multiple_share_classes_remain_separate_on_each_basis(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            raw=b'<p>Class A common stock Class B common stock Before offering After offering</p><p>Ownership as of January 1, 2026 includes awards and trust attribution.</p><table><tr><td>Jordan Example</td><td>1,000</td><td>5 %</td><td>2,000</td><td>10 %</td><td>0</td><td>0 %</td><td>2,000</td><td>9 %</td></tr></table><p>(1) The total includes options. Saleability is not established.</p>'
            text,blocks=m.text_blocks(raw);source=m.sha(raw);(d/'objects'/source).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=source;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            start=next(b['index'] for b in blocks if 'Jordan Example' in b['text']);end=next(b['index'] for b in blocks if '(1)' in b['text'])
            r['columns']=[dict(key='a_pre',kind='quantity',position_basis='pre',share_class='Class A common stock',header_literal='Before offering'),dict(key='a_pre_pct',kind='percent'),dict(key='b_pre',kind='quantity',position_basis='pre',share_class='Class B common stock',header_literal='Before offering'),dict(key='b_pre_pct',kind='percent'),dict(key='a_post',kind='quantity',position_basis='post',share_class='Class A common stock',header_literal='After offering'),dict(key='a_post_pct',kind='percent'),dict(key='b_post',kind='quantity',position_basis='post',share_class='Class B common stock',header_literal='After offering'),dict(key='b_post_pct',kind='percent')]
            r['people'][0].pop('share_class');r['people'][0]['row']=dict(first=start,last=end-1);r['people'][0]['cells']=['1,000','5 %','2,000','10 %','0','0 %','2,000','9 %'];r['people'][0]['footnotes']=[dict(first=end,last=end)]
            manifest,_=m.build(p,r,d)
            self.assertEqual([(x['share_class'],x['position_basis'],x['shares']) for x in manifest['positions']],[('Class A common stock','pre',1000),('Class B common stock','pre',2000),('Class A common stock','post',0),('Class B common stock','post',2000)])

    def test_duplicate_html_row_and_repeated_person_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d);bad=copy.deepcopy(r);bad['people']*=2
            with self.assertRaises(ValueError):m.build(p,bad,d)
            doc=p['documents'][0];raw=(d/'objects'/doc['source']['content_sha256']).read_bytes()
            table=raw[raw.index(b'<table>'):raw.index(b'</table>')+8];raw+=table
            doc['source']['content_sha256']=m.sha(raw);doc['normalized_text_sha256']=m.sha(m.text_blocks(raw)[0].encode())
            (d/'objects'/m.sha(raw)).write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'Whole source row'):m.build(p,r,d)

    def test_organization_holder_keeps_beneficiary_and_control_attribution_distinct(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            raw=(b'<p>Immediately Prior to this Offering Class A common shares</p>'
                 b'<p>Ownership as of January 1, 2026 reports beneficial ownership.</p>'
                 b'<table><tr><td>Example Foundation(1)</td><td>1,000</td><td>5 %</td></tr></table>'
                 b'<p>(1) Jordan Example holds the beneficial entitlement to shares held by Example Foundation.</p>')
            text,_=m.text_blocks(raw);h=m.sha(raw);(d/'objects'/h).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=h;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            r.update(skip_undisclosed_quantities=True,
                columns=[dict(key='pre',kind='quantity',position_basis='pre',header_literal='Immediately Prior',share_class='Class A common shares'),dict(key='pre_pct',kind='percent')],
                people=[dict(name='Example Foundation',source_label='Example Foundation(1)',party_kind='organization',identity_reviewed=True,
                    alias_reviewed=True,alias_reason='Numeric footnote marker removed from the canonical holder name.',
                    row=dict(first=2,last=2),cells=['1,000','5 %'],footnotes=[dict(first=3,last=3)],
                    interpretation_note='Foundation is the reported holder; beneficiary entitlement is separately attributed.',
                    attributions=[dict(name='Jordan Example',kind='beneficial_entitlement',identity_reviewed=True,
                        description='Source states beneficiary entitlement through the foundation; direct title and present saleability are not established.',evidence=dict(first=3,last=3))])])
            manifest,sql=m.build(p,r,d)
            self.assertEqual(manifest['version'],'disclosed-holdings/2')
            self.assertEqual(manifest['positions'][0]['party_kind'],'organization')
            self.assertIn('insert into research.ownership_attributions',sql)
            self.assertIn("'beneficial_entitlement'",sql)
            bad=copy.deepcopy(r);bad['people'][0]['attributions'][0].update(kind='control_authority',description='Controls voting decisions.')
            with self.assertRaisesRegex(ValueError,'personal economic'):m.build(p,bad,d)

    def test_partial_quantity_selection_alias_attribution_and_omitted_rows_are_audited(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            raw=(b'<p>Class A common stock Class B common stock Before offering After offering</p>'
                 b'<p>Ownership as of January 1, 2026 reports beneficial ownership.</p>'
                 b'<table><tr><td>Example Fund (1)</td><td>1,000</td><td>5 %</td><td>2,000</td><td>9 %</td></tr>'
                 b'<tr><td>All holders as a group</td><td>1,000</td><td>5 %</td><td>2,000</td><td>9 %</td></tr></table>'
                 b'<p>(1) Alex Sample may be reported as a beneficial owner of Example Fund shares. Personal economic ownership is not established.</p>')
            text,_=m.text_blocks(raw);h=m.sha(raw);(d/'objects'/h).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=h;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            r.update(columns=[
                dict(key='pre_a',kind='quantity',position_basis='pre',header_literal='Before offering',share_class='Class A common stock'),
                dict(key='pre_pct',kind='percent'),
                dict(key='post_b',kind='quantity',position_basis='post',header_literal='After offering',share_class='Class B common stock'),
                dict(key='post_pct',kind='percent')],
                reviewed_non_imported_rows=[dict(source_label='All holders as a group',row=dict(first=3,last=3),
                    cells=['1,000','5 %','2,000','9 %'],reason='Aggregate duplicates selected holder rows.')],
                people=[dict(name='Example Fund',source_label='Example Fund (1)',party_kind='organization',identity_reviewed=True,
                    alias_reviewed=True,alias_reason='Numeric footnote marker removed.',row=dict(first=2,last=2),
                    cells=['1,000','5 %','2,000','9 %'],footnotes=[dict(first=4,last=4)],
                    interpretation_note='Entity is the reported holder.',import_quantity_keys=['post_b'],
                    not_imported_quantity_reason='The Class A quantity is represented by another non-overlapping reviewed record.',
                    attributions=[dict(name='Alexander Sample',source_name='Alex Sample',alias_reviewed=True,
                        alias_reason='Reviewed short-form name against the issuer roster.',kind='reported_beneficial_owner',
                        identity_reviewed=True,description='The SEC table reports the person through the fund; personal economic ownership is not established.',
                        evidence=dict(first=4,last=4))])])
            manifest,sql=m.build(p,r,d)
            self.assertEqual([(x['share_class'],x['shares']) for x in manifest['positions']],[('Class B common stock',2000)])
            self.assertEqual(len(manifest['reviewed_non_imported_rows']),1)
            self.assertIn("'reported_beneficial_owner'",sql)
            for mutate in ('selection','reason','alias','economic','omitted'):
                bad=copy.deepcopy(r)
                if mutate=='selection': bad['people'][0]['import_quantity_keys']=['missing']
                elif mutate=='reason': bad['people'][0]['not_imported_quantity_reason']=''
                elif mutate=='alias': bad['people'][0]['attributions'][0]['alias_reviewed']=False
                elif mutate=='economic': bad['people'][0]['attributions'][0]['description']='SEC-reported relationship.'
                else: bad['reviewed_non_imported_rows'][0]['cells'][0]='1,001'
                with self.subTest(mutate=mutate),self.assertRaises(ValueError):m.build(p,bad,d)

    def test_single_quantity_with_conflicting_source_dates_stays_unspecified(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d)
            raw=(b'<p>NUMBER OF SHARES BENEFICIALLY OWNED BEFORE OFFERING AFTER OFFERING common stock</p>'
                 b'<p>Ownership as of September 30, 2025. Percentages use December 31, 2025.</p>'
                 b'<table><tr><td>Jordan Example</td><td>1,000</td><td>5 %</td><td>3 %</td></tr></table>')
            text,_=m.text_blocks(raw);h=m.sha(raw);(d/'objects'/h).write_bytes(raw)
            p['documents'][0]['source']['content_sha256']=h;p['documents'][0]['normalized_text_sha256']=m.sha(text.encode())
            r.pop('holdings_as_of')
            r.update(position_basis_limitation=('The introduction says September 30, 2025, while the '
                     'denominator and option language use December 31, 2025; no date is selected.'),
                columns=[dict(key='reported_total',kind='quantity',position_basis='unspecified',
                              share_class='common stock',header_literal='NUMBER OF SHARES BENEFICIALLY OWNED'),
                         dict(key='before_pct',kind='percent'),dict(key='after_pct',kind='percent')],
                people=[dict(name='Jordan Example',source_label='Jordan Example',identity_reviewed=True,
                    row=dict(first=2,last=2),cells=['1,000','5 %','3 %'],
                    interpretation_note='The filing supplies one quantity and two percentages.')])
            manifest,sql=m.build(p,r,d)
            self.assertEqual(len(manifest['positions']),1)
            self.assertEqual(manifest['positions'][0]['position_basis'],'unspecified')
            self.assertIsNone(manifest['positions'][0]['holdings_as_of'])
            self.assertIn("'unspecified'",sql)
            self.assertIn('stored once',manifest['positions'][0]['explanation'])
            bad=copy.deepcopy(r);bad.pop('position_basis_limitation')
            with self.assertRaisesRegex(ValueError,'source limitation'):m.build(p,bad,d)


if __name__=='__main__':unittest.main()
