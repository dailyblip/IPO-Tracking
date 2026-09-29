import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { LiquidityProfileView } from '../src/LiquidityProfileView.js';
import { LiquidityReportView } from '../src/LiquidityReportView.js';
import type { LiquidityReport } from '../shared/liquidity.js';
import { ownershipRows } from '../shared/ownership.js';

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

test('profile layout preserves projected/attributed evidence and does not invent other companies or sales', () => {
  const before = JSON.stringify(report);
  const html = renderToStaticMarkup(createElement(LiquidityProfileView, { report, ticker:'EXM', onBack:()=>{}, scenarioKey:'test' }));
  for (const label of ['Connected offering · 1','Liquidity timeline','What-if scenario','Projected post-offering position','Beneficial total','Not calculated','does not establish completed sales','reviewed identity links']) assert.ok(html.includes(label),label);
  assert.ok(!html.includes('Actual holdings reported'));
  assert.ok(!html.includes('Sold shares in the IPO'));
  assert.equal(JSON.stringify(report),before);
});

test('preferred conversion remains distinct and the profile exposes reconciled components without adding to totals', () => {
  const converted = structuredClone(report);
  converted.positions[0].components!.items[1] = {ordinal:2,instrument:'preferred_conversion',quantity:50,attribution:'trust_or_family',description:'Issuable upon conversion, not confirmed issued or personally owned.',source};
  const before = JSON.stringify(converted);
  const html = renderToStaticMarkup(createElement(LiquidityProfileView, {report:converted,onBack:()=>{},scenarioKey:'conversion'}));
  assert.ok(html.includes('What makes up this total'));
  assert.ok(html.includes('Common shares issuable on preferred conversion'));
  assert.ok(html.includes('Issuable upon conversion, not confirmed issued or personally owned.'));
  assert.ok(html.includes('Components of the reported total, not additional holdings'));
  assert.ok(html.includes('Trust / family attribution'));
  assert.equal(JSON.stringify(converted),before);
});

test('component rows preserve the reported class and entity attribution in both the grid and profile', () => {
  const attributed = structuredClone(report);
  const position = attributed.positions[0];
  position.shareClass = 'Class B common stock';
  position.reportedHolder = { id:'fund',name:'Example Fund LP',kind:'organization' };
  position.attribution = { kind:'control_authority',description:'Voting authority only; personal economic interest is not established.',source };
  position.components!.items[0].attribution = 'direct';
  const before = JSON.stringify(attributed);
  const rows = ownershipRows(attributed.positions);
  assert.equal(rows.length, 2, 'components replace rather than supplement their aggregate');
  assert.deepEqual(rows.map(row => row.quantity), [100, 50]);
  for (const row of rows) {
    assert.ok(row.security.includes('Reported class: Class B common stock'));
    assert.ok(row.attribution.includes('Voting / control authority · reported holder: Example Fund LP'));
    assert.equal(row.position.attribution, position.attribution);
  }
  assert.ok(rows[0].attribution.startsWith('Direct holding as disclosed'));
  for (const html of [
    renderToStaticMarkup(createElement(LiquidityReportView, {report:attributed})),
    renderToStaticMarkup(createElement(LiquidityProfileView, {report:attributed,onBack:()=>{},scenarioKey:'attribution'})),
  ]) {
    assert.ok(html.includes('Common shares · Reported class: Class B common stock'));
    assert.ok(html.includes('Direct holding as disclosed · Voting / control authority · reported holder: Example Fund LP'));
  }
  assert.equal(JSON.stringify(attributed), before);
});

test('components with no recorded class keep it unknown and retain all parent attribution kinds', () => {
  for (const [kind, label] of [['beneficial_entitlement', 'Beneficiary entitlement'], ['reported_beneficial_owner', 'SEC-reported beneficial owner']] as const) {
    const position = structuredClone(report.positions[0]);
    position.shareClass = null;
    position.attribution = {kind,description:'Filing attribution only.',source};
    const rows = ownershipRows([position]);
    assert.ok(rows.every(row => row.security.endsWith('Reported class: unconfirmed')));
    assert.ok(rows.every(row => row.attribution.includes(`${label} · reported holder: unconfirmed`)));
  }
});
