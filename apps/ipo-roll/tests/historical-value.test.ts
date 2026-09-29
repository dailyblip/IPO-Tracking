import test from 'node:test';
import assert from 'node:assert/strict';
import { createElement } from 'react';
import { renderToStaticMarkup } from 'react-dom/server';
import { OwnershipValueSummary } from '../src/OwnershipGrid.js';
import { LiquidityProfileView } from '../src/LiquidityProfileView.js';
import {
  calculateHistoricalPosition, calculateHistoricalHoldings, calculateDocumentedHolderSale,
  checkedHistoricalSnapshot, HISTORICAL_VALUE_METHOD, type SavedHistoricalValues,
  type HistoricalEvidence, type HistoricalPosition, type HistoricalIpoPrice,
  type HistoricalCompatibility, type HistoricalContext, type DocumentedHolderSale,
} from '../shared/historical-value.js';

const evidence: HistoricalEvidence = {
  documentId: 'filing-1', documentHash: 'a'.repeat(64), sourceVersion: 'filing-1/v1',
  filingAccession: '0001234567-26-000001', filingDate: '2026-04-03',
  retrievedAt: '2026-04-03T12:00:00Z', reviewedAt: '2026-04-04T12:00:00Z', reviewStatus: 'reviewed',
  url: 'https://www.sec.gov/Archives/edgar/data/1234567/synthetic.htm', locator: 'Synthetic table and footnote',
  excerpt: 'Synthetic fixture: the named holder owns 100 Class A common shares.',
};
const context: HistoricalContext = { analysisAsOf: '2026-04-05T12:00:00Z', currentSourceHashes: { 'filing-1': evidence.documentHash } };
const position: HistoricalPosition = {
  id: 'position-1', issuerId: 'issuer-1', offeringId: 'offering-1', securityId: 'class-a', shareClass: 'Class A',
  holder: { id: 'holder-1', name: 'Synthetic Holder', kind: 'person', attribution: 'personal_economic', evidence: [evidence] },
  instrument: 'common_share', quantityKind: 'disaggregated_shares', shares: 100,
  basis: 'actual_disclosed', holdingsDate: '2026-03-31', evidence: [evidence],
  overlap: { status: 'reviewed_distinct', exposureId: 'exposure-1', evidence: [evidence] },
};
const price: HistoricalIpoPrice = {
  issuerId: 'issuer-1', offeringId: 'offering-1', securityId: 'class-a', shareClass: 'Class A',
  kind: 'authoritative_final_ipo_price', price: '12.34', currency: 'USD', pricingDate: '2026-04-02', evidence: [evidence],
};
const compatibility: HistoricalCompatibility = {
  status: 'reviewed_compatible', positionId: 'position-1', fromSecurityId: 'class-a', toSecurityId: 'class-a',
  method: 'same_security', numerator: 1, denominator: 1, reconciledThrough: '2026-04-02', evidence: [evidence],
};
const sale: DocumentedHolderSale = {
  id: 'sale-1', issuerId: 'issuer-1', offeringId: 'offering-1', securityId: 'class-a', shareClass: 'Class A',
  holder: position.holder, kind: 'completed_holder_sale', instrument: 'common_share',
  sharesSold: 25, saleDate: '2026-04-02', evidence: [evidence],
  price: { issuerId: 'issuer-1', offeringId: 'offering-1', securityId: 'class-a', shareClass: 'Class A',
    kind: 'documented_completed_holder_sale_price', holderId: 'holder-1', saleId: 'sale-1', saleDate: '2026-04-02',
    amount: '12.34', currency: 'USD', evidence: [evidence] },
};

test('historical estimate is exact, source-version-bound, dated, and reproducible', () => {
  const result = calculateHistoricalPosition(position, price, compatibility, context);
  assert.equal(result.status, 'established');
  assert.equal(result.grossAmount, '1234.00');
  assert.equal(result.pricedShares, '100');
  assert.equal(result.priceDate, '2026-04-02');
  assert.equal(result.holdingsDate, '2026-03-31');
  assert.equal(result.valueScope, 'personal_economic_holding');
  assert.equal(result.evidence[0].documentHash, evidence.documentHash);
  assert.deepEqual(result, calculateHistoricalPosition(position, price, compatibility, context));
  assert.match(result.limitations.join(' '), /not a current market quote/);
  assert.match(result.limitations.join(' '), /saleability/);
});

test('decimal arithmetic does not inherit floating-point error or round fractional conversions', () => {
  assert.equal(calculateHistoricalPosition({ ...position, shares: 3 }, { ...price, price: '0.10' }, compatibility, context).grossAmount, '0.30');
  assert.equal(calculateHistoricalPosition({ ...position, shares: Number.MAX_SAFE_INTEGER }, { ...price, price: '0.01' }, compatibility, context).grossAmount, '90071992547409.91');
  assert.equal(calculateHistoricalPosition({ ...position, shares: 3 }, price,
    { ...compatibility, method: 'reviewed_common_share_conversion', numerator: 1, denominator: 2 }, context).reason, 'unsupported_conversion');
});

test('missing quantity remains unknown while an explicitly reviewed zero is zero', () => {
  assert.equal(calculateHistoricalPosition({ ...position, shares: null }, price, compatibility, context).grossAmount, null);
  assert.equal(calculateHistoricalPosition({ ...position, shares: 0 }, price, compatibility, context).grossAmount, '0.00');
  for (const shares of [-1, 1.2, Infinity, NaN, Number.MAX_SAFE_INTEGER + 1]) {
    assert.equal(calculateHistoricalPosition({ ...position, shares }, price, compatibility, context).reason, 'invalid_quantity');
  }
});

test('aggregate beneficial totals and mixed or derivative instruments cannot be multiplied', () => {
  assert.equal(calculateHistoricalPosition({ ...position, quantityKind: 'beneficial_total' }, price, compatibility, context).reason, 'aggregate_or_unknown_quantity');
  for (const instrument of ['option', 'rsu', 'warrant', 'preferred_share', 'unknown'] as const) {
    assert.equal(calculateHistoricalPosition({ ...position, instrument }, price, compatibility, context).reason, 'unsupported_instrument');
  }
});

test('fund and trust estimates remain attributed to the reported holder; control is not ownership', () => {
  for (const [kind, attribution] of [['organization', 'reported_organization'], ['trust', 'reported_trust']] as const) {
    const result = calculateHistoricalPosition({ ...position, holder: { ...position.holder, kind, attribution } }, price, compatibility, context);
    assert.equal(result.status, 'established');
    assert.equal(result.valueScope, 'reported_holder_holding');
    assert.match(result.limitations.join(' '), /personal economic ownership is not established/);
  }
  for (const attribution of ['control_authority', 'unknown', 'reported_organization'] as const) {
    const result = calculateHistoricalPosition({ ...position, holder: { ...position.holder, attribution } }, price, compatibility, context);
    assert.equal(result.reason, 'unsupported_holder_attribution');
    assert.equal(result.grossAmount, null);
  }
  assert.equal(calculateHistoricalPosition({ ...position, holder: { ...position.holder, kind: 'group' } }, price, compatibility, context).reason, 'unsupported_holder_attribution');
});

test('projected estimates require explicit conditions and retain their separate basis and label', () => {
  const projected = { ...position, basis: 'projected_post_offering' as const };
  assert.equal(calculateHistoricalPosition(projected, price, compatibility, context).reason, 'unknown_position_basis');
  const result = calculateHistoricalPosition({ ...projected, projectionConditions: 'Subject to completion of the IPO and reviewed conversion.' }, price, compatibility, context);
  assert.equal(result.status, 'established');
  assert.equal(result.positionBasis, 'projected_post_offering');
  assert.match(result.label, /Projected post-offering/);
  assert.match(result.conditions!, /Subject to completion/);
});

test('preliminary pricing and invalid decimal or currency inputs never become a value', () => {
  assert.equal(calculateHistoricalPosition(position, { ...price, kind: 'preliminary_price' }, compatibility, context).reason, 'non_final_price');
  for (const invalidPrice of ['0', '-1', '1e2', 'NaN', 'Infinity', '01.25', '0.123456789', '1,200']) {
    assert.equal(calculateHistoricalPosition(position, { ...price, price: invalidPrice }, compatibility, context).reason, 'invalid_price');
  }
  assert.equal(calculateHistoricalPosition(position, { ...price, currency: '' }, compatibility, context).reason, 'invalid_price');
});

test('issuer, offering, security, and share class must match the reviewed price basis', () => {
  for (const delta of [{ issuerId: 'different' }, { offeringId: 'different' }]) {
    assert.equal(calculateHistoricalPosition(position, { ...price, ...delta }, compatibility, context).reason, 'identity_mismatch');
  }
  assert.equal(calculateHistoricalPosition(position, { ...price, shareClass: 'Class B' }, compatibility, context).reason, 'unsupported_conversion');
  assert.equal(calculateHistoricalPosition(position, price, { ...compatibility, positionId: 'another-position' }, context).reason, 'identity_mismatch');
  assert.equal(calculateHistoricalPosition(position, price, { ...compatibility, status: 'unknown' }, context).reason, 'unreviewed_compatibility');
});

test('a documented common-share conversion uses its reviewed exact ratio', () => {
  const converted = calculateHistoricalPosition({ ...position, securityId: 'class-b', shareClass: 'Class B' }, price,
    { ...compatibility, fromSecurityId: 'class-b', method: 'reviewed_common_share_conversion', numerator: 3, denominator: 2 }, context);
  assert.equal(converted.status, 'established');
  assert.equal(converted.pricedShares, '150');
  assert.equal(converted.grossAmount, '1851.00');
  assert.equal(calculateHistoricalPosition(position, price, { ...compatibility, numerator: 2 }, context).reason, 'unsupported_conversion');
});

test('overlap review is mandatory and repeated exposure representations are excluded on all rows', () => {
  assert.equal(calculateHistoricalPosition({ ...position, overlap: { ...position.overlap, status: 'unknown' } }, price, compatibility, context).reason, 'overlap_not_excluded');
  const results = calculateHistoricalHoldings([
    { position, price, compatibility },
    { position: { ...position, id: 'duplicate', holder: { ...position.holder, id: 'controller' } }, price,
      compatibility: { ...compatibility, positionId: 'duplicate' } },
  ], context);
  assert.equal(results.length, 2);
  for (const result of results) {
    assert.equal(result.status, 'unknown');
    assert.equal(result.reason, 'duplicate_exposure');
    assert.equal(result.grossAmount, null);
  }
});

test('actual and projected representations stay separate and the helper never emits a total', () => {
  const results = calculateHistoricalHoldings([
    { position, price, compatibility },
    { position: { ...position, id: 'projected', basis: 'projected_post_offering', projectionConditions: 'On IPO completion.' }, price,
      compatibility: { ...compatibility, positionId: 'projected' } },
  ], context);
  assert.deepEqual(results.map((r) => r.status), ['established', 'established']);
  assert.deepEqual(results.map((r) => r.positionBasis), ['actual_disclosed', 'projected_post_offering']);
  assert.ok(Array.isArray(results));
});

test('stale, missing, conflicting, or incomplete source evidence is never accuracy approval', () => {
  for (const e of [
    { ...evidence, reviewStatus: 'unreviewed' as const },
    { ...evidence, reviewStatus: 'conflicting' as const },
    { ...evidence, documentHash: '' }, { ...evidence, sourceVersion: '' },
    { ...evidence, excerpt: '' }, { ...evidence, locator: '' },
    { ...evidence, url: 'javascript:alert(1)' }, { ...evidence, filingAccession: 'invalid' },
    { ...evidence, reviewedAt: '2026-04-01T00:00:00Z' },
  ]) {
    assert.equal(calculateHistoricalPosition({ ...position, evidence: [e] }, price, compatibility, context).reason, 'invalid_evidence');
  }
  assert.equal(calculateHistoricalPosition({ ...position, evidence: [] }, price, compatibility, context).reason, 'invalid_evidence');
  assert.equal(calculateHistoricalPosition(position, price, compatibility, { ...context, currentSourceHashes: {} }).reason, 'source_version_mismatch');
  assert.equal(calculateHistoricalPosition(position, price, compatibility,
    { ...context, currentSourceHashes: { 'filing-1': 'b'.repeat(64) } }).reason, 'source_version_mismatch');
});

test('invalid, future, or unreconciled dates fail closed with an explicit clock', () => {
  assert.equal(calculateHistoricalPosition(position, price, compatibility, { ...context, analysisAsOf: '2026-02-30T12:00:00Z' }).reason, 'invalid_analysis_time');
  assert.equal(calculateHistoricalPosition(position, price, compatibility, { ...context, analysisAsOf: '2026-04-05' }).reason, 'invalid_analysis_time');
  for (const holdingsDate of ['2026-02-30', '2026-04-06', '']) {
    assert.equal(calculateHistoricalPosition({ ...position, holdingsDate }, price, compatibility, context).reason, 'invalid_dates');
  }
  assert.equal(calculateHistoricalPosition(position, { ...price, pricingDate: '2026-04-06' }, compatibility, context).reason, 'invalid_dates');
  assert.equal(calculateHistoricalPosition(position, price, { ...compatibility, reconciledThrough: '2026-04-01' }, context).reason, 'incomplete_reconciliation');
});

test('calculation snapshots are detached from subsequent input changes', () => {
  const isolatedPosition = structuredClone(position);
  const result = calculateHistoricalPosition(isolatedPosition, price, compatibility, context);
  isolatedPosition.evidence[0].excerpt = 'Changed later';
  assert.notEqual(result.evidence[0].excerpt, isolatedPosition.evidence[0].excerpt);
  assert.equal(result.grossAmount, '1234.00');
});

test('earlier filings cannot establish later holdings, final prices, reconciliation, or completed sales', () => {
  const earlier = { ...evidence, filingDate: '2026-03-01' };
  assert.equal(calculateHistoricalPosition({ ...position, evidence: [earlier] }, price, compatibility, context).reason, 'invalid_dates');
  assert.equal(calculateHistoricalPosition(position, { ...price, evidence: [earlier] }, compatibility, context).reason, 'invalid_dates');
  assert.equal(calculateHistoricalPosition(position, price, { ...compatibility, evidence: [earlier] }, context).reason, 'incomplete_reconciliation');
  assert.equal(calculateDocumentedHolderSale({ ...sale, evidence: [earlier] }, context).reason, 'invalid_dates');
});

test('documented completed holder sales use actual sale quantity and price as gross consideration', () => {
  const result = calculateDocumentedHolderSale(sale, context);
  assert.equal(result.status, 'established');
  assert.equal(result.grossAmount, '308.50');
  assert.equal(result.positionBasis, 'completed_holder_sale');
  assert.match(result.label, /gross holder-sale/);
  assert.match(result.limitations.join(' '), /payment receipt are unknown/);
});

test('proposed sales, issuer proceeds, or IPO-price-only evidence cannot become holder-sale proceeds', () => {
  for (const kind of ['proposed_holder_sale', 'company_offering', 'unknown'] as const) {
    assert.equal(calculateDocumentedHolderSale({ ...sale, kind }, context).reason, 'sale_not_completed');
  }
  assert.equal(calculateDocumentedHolderSale({ ...sale, price: { ...sale.price, kind: 'ipo_price_only' } }, context).reason, 'sale_price_not_established');
  assert.equal(calculateDocumentedHolderSale({ ...sale, sharesSold: null }, context).grossAmount, null);
  assert.equal(calculateDocumentedHolderSale({ ...sale, instrument: 'option' }, context).reason, 'unsupported_instrument');
});

test('a completed sale price cannot be reused across holders, sale events, security classes, or dates', () => {
  for (const delta of [{ holderId: 'other' }, { saleId: 'other' }, { issuerId: 'other' }, { offeringId: 'other' }, { securityId: 'other' }, { shareClass: 'Class B' }]) {
    assert.equal(calculateDocumentedHolderSale({ ...sale, price: { ...sale.price, ...delta } }, context).reason, 'identity_mismatch');
  }
  assert.equal(calculateDocumentedHolderSale({ ...sale, price: { ...sale.price, saleDate: '2026-04-03' } }, context).reason, 'invalid_dates');
});

test('trust or fund sale consideration does not establish a controller personal cash receipt', () => {
  const result = calculateDocumentedHolderSale({ ...sale, holder: { ...sale.holder, kind: 'organization', attribution: 'reported_organization' } }, context);
  assert.equal(result.status, 'established');
  assert.equal(result.valueScope, 'reported_holder_holding');
  assert.match(result.limitations.join(' '), /does not establish personal cash proceeds/);
  assert.equal(calculateDocumentedHolderSale({ ...sale, holder: { ...sale.holder, attribution: 'control_authority' } }, context).reason, 'unsupported_holder_attribution');
});

function savedSnapshot(): SavedHistoricalValues {
  return {
    version: 'historical-value-snapshot/1', calculator: HISTORICAL_VALUE_METHOD, asOf: context.analysisAsOf,
    holdings: [{ claimId: position.id, ownershipId: 'ownership-1', exposureId: position.overlap.exposureId,
      position: structuredClone(position), price: structuredClone(price), compatibility: structuredClone(compatibility),
      context: structuredClone(context), output: calculateHistoricalPosition(position, price, compatibility, context) }],
    sales: [{ claimId: sale.id, ownershipId: 'ownership-1', exposureId: 'sale-exposure-1', sale: structuredClone(sale),
      context: structuredClone(context), output: calculateDocumentedHolderSale(sale, context) }],
    notice: 'Static historical calculations. Alternative positions are not summed.',
  };
}

test('private report renderer uses the saved exact outputs, dates, attribution, and evidence', () => {
  const snapshot = savedSnapshot();
  const before = JSON.stringify(snapshot);
  const checked = checkedHistoricalSnapshot(snapshot);
  assert.equal(checked.holdings[0].saved, snapshot.holdings[0].output);
  assert.equal(checked.holdings[0].verified, true);
  assert.equal(checked.sales[0].verified, true);
  const html = renderToStaticMarkup(createElement(OwnershipValueSummary, { historicalValues: snapshot }));
  for (const text of ['USD 1,234.00', 'USD 308.50', 'Holdings 2026-03-31', 'Price 2026-04-02',
    'Reviewed personal economic interest', 'Class A', 'SHA-256', 'fees, taxes, net proceeds', 'Explicit refresh creates a new report version']) {
    assert.ok(html.includes(text), text);
  }
  assert.equal(JSON.stringify(snapshot), before, 'Rendering must not mutate the saved report');
});

test('saved unknown remains unknown even if the input calculator could now return an amount', () => {
  const snapshot = savedSnapshot();
  snapshot.holdings[0].output = { ...snapshot.holdings[0].output, status: 'unknown', reason: 'non_final_price', grossAmount: null, price: null, pricedShares: null, currency: null };
  const checked = checkedHistoricalSnapshot(snapshot);
  assert.equal(checked.holdings[0].saved.status, 'unknown');
  assert.equal(checked.holdings[0].saved.grossAmount, null);
  const html = renderToStaticMarkup(createElement(OwnershipValueSummary, { historicalValues: snapshot }));
  assert.ok(!html.includes('USD 1,234.00'));
  assert.ok(html.includes('non final price'));
});

test('tampered or unsupported saved calculations never get replaced by a fresh amount', () => {
  const snapshot = savedSnapshot();
  snapshot.holdings[0].output.grossAmount = '99999999.99';
  assert.equal(checkedHistoricalSnapshot(snapshot).holdings[0].verified, false);
  let html = renderToStaticMarkup(createElement(OwnershipValueSummary, { historicalValues: snapshot }));
  assert.ok(!html.includes('99,999,999.99') && !html.includes('1,234.00'));
  assert.ok(html.includes('no replacement estimate generated'));
  snapshot.calculator = 'future-unimplemented/2' as typeof HISTORICAL_VALUE_METHOD;
  assert.equal(checkedHistoricalSnapshot(snapshot).sales[0].verified, false);
  html = renderToStaticMarkup(createElement(OwnershipValueSummary, { historicalValues: snapshot }));
  assert.ok(!html.includes('USD 308.50'));
});

test('duplicate retained or sale exposures cannot display established saved estimates', () => {
  const snapshot = savedSnapshot();
  snapshot.holdings.push(structuredClone(snapshot.holdings[0]));
  snapshot.sales.push(structuredClone(snapshot.sales[0]));
  const checked = checkedHistoricalSnapshot(snapshot);
  assert.ok(checked.holdings.every((h) => !h.verified));
  assert.ok(checked.sales.every((s) => !s.verified));
});

test('legacy reports without valuation snapshots retain unknown cards', () => {
  const html = renderToStaticMarkup(createElement(OwnershipValueSummary));
  assert.equal((html.match(/Not established/g) || []).length, 2);
  assert.ok(html.includes('Current market value is unavailable'));
});

test('primary private profile shows saved values without contradicting documented sales', () => {
  const report = {
    id: 'synthetic-report', version: 'liquidity/1', asOf: context.analysisAsOf,
    method: 'Synthetic QA', offeringId: 'offering-1', personId: position.holder.id,
    company: 'Synthetic issuer', person: position.holder.name, relationship: 'Director',
    relationshipSource: {title:'Synthetic source', url:null, date:'2026-04-02', excerpt:'Synthetic', locator:'1'},
    notice: 'Static private snapshot', positions: [], historicalValues: savedSnapshot(),
  };
  const before = JSON.stringify(report);
  const html = renderToStaticMarkup(createElement(LiquidityProfileView, {report,onBack:()=>{},scenarioKey:'synthetic'}));
  assert.ok(html.includes('USD 1,234.00') && html.includes('Documented holder sale'));
  assert.ok(!html.includes('This snapshot does not establish completed sales'));
  assert.equal(JSON.stringify(report), before);
});
