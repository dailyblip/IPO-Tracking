import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { LiquidityReportView } from '../src/LiquidityReportView.js';
import type { LiquidityReport } from '../shared/liquidity.js';

const source = { title:'Synthetic filing',url:'https://example.test/filing',date:'2026-09-01',excerpt:'Exact synthetic evidence',locator:'{"first_block":4,"last_block":5}' };
const report: LiquidityReport = { id:'test-report',version:'liquidity/1.1',asOf:'2026-09-01T00:00:00Z',method:'Synthetic evidence review',offeringId:'o',personId:'p',company:'Example',person:'Example Person',relationship:'Director',relationshipSource:source,notice:'Private static report',positions:[{
  id:'position',shareClass:'Common and awards',shares:null,reportedTotal:150,quantityKind:'beneficial_total',positionBasis:'post',holdingsDate:'2026-09-01',filingDate:'2026-09-01',holdingsAsOf:'2026-08-01',filingAccession:'synthetic-accession',documentHash:'synthetic-hash',source,
  components:{status:'reconciled',items:[{ordinal:1,instrument:'common_share',quantity:100,attribution:'trust_or_family',description:'Trust attribution',source},{ordinal:2,instrument:'option',quantity:50,attribution:'unknown',description:'Options',source}]},
  category:'unknown',assessmentDate:'2026-09-01',validThrough:null,lockupStart:null,lockupEnd:null,explanation:'Assessment explanation',conditions:'No confirmation of personal ownership',evidence:[source],marketValue:null,valuationReason:'No compatible quote'
}]};
test('compact report retains distinct instruments, snapshot basis and evidence without summing or mutating a saved report', () => {
  const before = JSON.stringify(report);
  const html = renderToStaticMarkup(createElement(LiquidityReportView, { report }));
  for (const label of ['Retained stake value','Documented IPO sale proceeds','Common shares','Option underlying shares','Trust / family attribution','Projected after IPO','2026-08-01','synthetic-accession','synthetic-hash','Source blocks 4–5','Assessment explanation','No confirmation of personal ownership']) assert.ok(html.includes(label), label);
  assert.equal((html.match(/class="ownership-quantity"/g) || []).length, 2);
  assert.ok(!html.includes('>150<'), 'aggregate must not be added to component rows');
  assert.ok(!/<details[^>]*\bopen\b/.test(html), 'long evidence remains collapsed');
  assert.ok(html.includes('Position counts, not share or dollar totals'));
  assert.equal(JSON.stringify(report), before);
});
test('older saved reports retain their disclosed quantity and unknown dates without becoming current holdings', () => {
  const p = { ...report.positions[0], quantityKind:undefined, reportedTotal:undefined, components:undefined, shares:123, holdingsAsOf:undefined, filingDate:undefined, positionBasis:'pre' };
  const html = renderToStaticMarkup(createElement(LiquidityReportView, { report:{...report,positions:[p]} }));
  assert.ok(html.includes('>123</td>'));
  assert.ok(html.includes('Before IPO'));
  assert.ok(html.includes('Holdings date unconfirmed'));
  assert.ok(html.includes('Filed 2026-09-01'));
  const empty = renderToStaticMarkup(createElement(LiquidityReportView, { report:{...report,positions:[]} }));
  assert.ok(empty.includes('unknown is not zero'));
  assert.equal((empty.match(/<strong>Not established<\/strong>/g) || []).length, 2);
});
