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
        self.assertIsNone(m.quantity('—'));self.assertEqual(m.quantity('0'),0)
        self.assertEqual(m.quantity('1,234'),1234)
        for v in ('1,23','-1','1.2','1e3','9007199254740992','12 34','00'):
            with self.subTest(v=v),self.assertRaises(ValueError):m.quantity(v)

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

    def test_duplicate_html_row_and_repeated_person_are_not_double_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            d=Path(tmp);p,r=self.fixture(d);bad=copy.deepcopy(r);bad['people']*=2
            with self.assertRaises(ValueError):m.build(p,bad,d)
            doc=p['documents'][0];raw=(d/'objects'/doc['source']['content_sha256']).read_bytes()
            table=raw[raw.index(b'<table>'):raw.index(b'</table>')+8];raw+=table
            doc['source']['content_sha256']=m.sha(raw);doc['normalized_text_sha256']=m.sha(m.text_blocks(raw)[0].encode())
            (d/'objects'/m.sha(raw)).write_bytes(raw)
            with self.assertRaisesRegex(ValueError,'Whole source row'):m.build(p,r,d)


if __name__=='__main__':unittest.main()
