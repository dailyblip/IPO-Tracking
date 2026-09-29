/**
 * Pure, filing-based calculations. Callers must supply reviewed claims; this module
 * neither extracts facts nor persists or refreshes a user's static report.
 */
export const HISTORICAL_VALUE_METHOD = 'reviewed-filing-historical-value/1';

export type HistoricalEvidence = {
  documentId: string;
  documentHash: string;
  sourceVersion: string;
  filingAccession: string;
  filingDate: string;
  retrievedAt: string;
  reviewedAt: string;
  reviewStatus: 'reviewed' | 'unreviewed' | 'conflicting';
  url: string;
  locator: string;
  excerpt: string;
};

export type HistoricalContext = {
  /** Explicit clock makes calculations deterministic and snapshots reproducible. */
  analysisAsOf: string;
  /** Server-provided document hashes, never claims supplied by an ordinary client. */
  currentSourceHashes: Record<string, string>;
};

type Security = {
  issuerId: string;
  offeringId: string;
  securityId: string;
  shareClass: string;
};

type Holder = {
  id: string;
  name: string;
  kind: 'person' | 'organization' | 'trust' | 'group' | 'unknown';
  attribution: 'personal_economic' | 'reported_organization' | 'reported_trust' | 'control_authority' | 'unknown';
  evidence: HistoricalEvidence[];
};

export type HistoricalPosition = Security & {
  id: string;
  holder: Holder;
  instrument: 'common_share' | 'preferred_share' | 'option' | 'rsu' | 'warrant' | 'unknown';
  quantityKind: 'disaggregated_shares' | 'beneficial_total' | 'unknown';
  shares: number | null;
  basis: 'actual_disclosed' | 'projected_post_offering' | 'unknown';
  holdingsDate: string;
  /** Required for projections; never represented as an actual holding. */
  projectionConditions?: string;
  evidence: HistoricalEvidence[];
  overlap: {
    status: 'reviewed_distinct' | 'overlapping' | 'unknown';
    /** Canonical reviewed exposure identity, shared by duplicate representations. */
    exposureId: string;
    evidence: HistoricalEvidence[];
  };
};

export type HistoricalIpoPrice = Security & {
  kind: 'authoritative_final_ipo_price' | 'preliminary_price' | 'unknown';
  /** Decimal text avoids binary floating-point rounding of money. */
  price: string;
  currency: string;
  pricingDate: string;
  evidence: HistoricalEvidence[];
};

export type HistoricalCompatibility = {
  status: 'reviewed_compatible' | 'unknown' | 'conflicting';
  positionId: string;
  fromSecurityId: string;
  toSecurityId: string;
  method: 'same_security' | 'reviewed_common_share_conversion' | 'unknown';
  /** Explicit conversion of the disclosed common-share class into the IPO class. */
  numerator: number;
  denominator: number;
  reconciledThrough: string;
  evidence: HistoricalEvidence[];
};

type UnknownReason =
  | 'invalid_analysis_time' | 'invalid_evidence' | 'source_version_mismatch'
  | 'unsupported_holder_attribution' | 'unsupported_instrument' | 'aggregate_or_unknown_quantity'
  | 'invalid_quantity' | 'unknown_position_basis' | 'invalid_dates' | 'overlap_not_excluded'
  | 'duplicate_exposure' | 'non_final_price' | 'invalid_price' | 'identity_mismatch'
  | 'unreviewed_compatibility' | 'unsupported_conversion' | 'incomplete_reconciliation'
  | 'sale_not_completed' | 'sale_price_not_established';

export type HistoricalValueResult = {
  status: 'established' | 'unknown';
  reason: UnknownReason | null;
  method: typeof HISTORICAL_VALUE_METHOD;
  analysisAsOf: string;
  positionId: string;
  holderId: string;
  valueScope: 'personal_economic_holding' | 'reported_holder_holding' | 'unknown';
  label: string;
  /** Exact decimal string, never a current quote or realized cash amount. */
  grossAmount: string | null;
  currency: string | null;
  inputShares: number | null;
  pricedShares: string | null;
  price: string | null;
  holdingsDate: string | null;
  priceDate: string | null;
  positionBasis: HistoricalPosition['basis'] | 'completed_holder_sale';
  conditions: string | null;
  evidence: HistoricalEvidence[];
  limitations: string[];
};

const LIMITATIONS = [
  'Historical filing-based estimate; not a current market quote or current personal wealth.',
  'Does not establish cash proceeds, transferable shares, or saleability. Restrictions may still apply.',
  'Fees, taxes, net proceeds, and market impact are unknown.',
];

function day(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const time = Date.parse(`${value}T00:00:00Z`);
  return Number.isFinite(time) && new Date(time).toISOString().slice(0, 10) === value ? time : null;
}

function instant(value: string): number | null {
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})$/.test(value)) return null;
  if (day(value.slice(0, 10)) === null) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? time : null;
}

function review(evidence: HistoricalEvidence[], context: HistoricalContext): UnknownReason | null {
  const asOf = instant(context.analysisAsOf);
  if (asOf === null) return 'invalid_analysis_time';
  if (!evidence.length) return 'invalid_evidence';
  for (const e of evidence) {
    const retrieved = instant(e.retrievedAt), reviewed = instant(e.reviewedAt), filed = day(e.filingDate);
    let safeUrl = false;
    try { safeUrl = new URL(e.url).protocol === 'https:'; } catch { /* Incomplete evidence. */ }
    if (e.reviewStatus !== 'reviewed' || !e.documentId.trim() || !e.sourceVersion.trim()
      || !/^[0-9a-f]{64}$/.test(e.documentHash) || !/^\d{10}-\d{2}-\d{6}$/.test(e.filingAccession)
      || !safeUrl || !e.locator.trim() || !e.excerpt.trim() || retrieved === null || reviewed === null
      || filed === null || filed > retrieved || retrieved > reviewed || reviewed > asOf) return 'invalid_evidence';
    if (context.currentSourceHashes[e.documentId] !== e.documentHash) return 'source_version_mismatch';
  }
  return null;
}

function checkedReviews(groups: HistoricalEvidence[][], context: HistoricalContext): UnknownReason | null {
  for (const group of groups) {
    const reason = review(group, context);
    if (reason) return reason;
  }
  return null;
}

function hasEvidenceOnOrAfter(evidence: HistoricalEvidence[], date: number): boolean {
  return evidence.some((e) => (day(e.filingDate) ?? -Infinity) >= date);
}

function holderScope(holder: Holder): HistoricalValueResult['valueScope'] {
  if (holder.kind === 'person' && holder.attribution === 'personal_economic') return 'personal_economic_holding';
  if ((holder.kind === 'organization' && holder.attribution === 'reported_organization')
    || (holder.kind === 'trust' && holder.attribution === 'reported_trust')) return 'reported_holder_holding';
  return 'unknown';
}

function quantity(value: number | null): value is number {
  return value !== null && Number.isSafeInteger(value) && value >= 0;
}

function decimalPrice(value: string): { units: bigint; scale: number } | null {
  if (!/^(?:0|[1-9]\d{0,19})(?:\.\d{1,8})?$/.test(value)) return null;
  const [whole, fraction = ''] = value.split('.');
  const units = BigInt(whole + fraction);
  return units > 0n ? { units, scale: fraction.length } : null;
}

function multiply(shares: bigint, price: { units: bigint; scale: number }): string {
  const digits = (shares * price.units).toString().padStart(price.scale + 1, '0');
  return price.scale ? `${digits.slice(0, -price.scale)}.${digits.slice(-price.scale)}` : digits;
}

function snapshot(evidence: HistoricalEvidence[]): HistoricalEvidence[] {
  // Copy, rather than retain caller references in an eventual immutable report.
  return evidence.map((e) => ({ ...e }));
}

/** One reviewed position, with source snapshots and no cross-holder aggregate. */
export function calculateHistoricalPosition(
  position: HistoricalPosition, price: HistoricalIpoPrice,
  compatibility: HistoricalCompatibility, context: HistoricalContext,
): HistoricalValueResult {
  const scope = holderScope(position.holder);
  const result: HistoricalValueResult = {
    status: 'unknown', reason: null, method: HISTORICAL_VALUE_METHOD,
    analysisAsOf: context.analysisAsOf, positionId: position.id, holderId: position.holder.id,
    valueScope: scope,
    label: position.basis === 'projected_post_offering'
      ? 'Projected post-offering historical IPO-price estimate' : 'Historical IPO-price estimate',
    grossAmount: null, currency: null, inputShares: position.shares, pricedShares: null, price: null,
    holdingsDate: position.holdingsDate || null, priceDate: price.pricingDate || null,
    positionBasis: position.basis, conditions: position.projectionConditions || null,
    evidence: snapshot([...position.evidence, ...position.holder.evidence, ...position.overlap.evidence,
      ...price.evidence, ...compatibility.evidence]), limitations: [...LIMITATIONS],
  };
  const unknown = (reason: UnknownReason) => ({ ...result, reason });
  const evidenceReason = checkedReviews([position.evidence, position.holder.evidence,
    position.overlap.evidence, price.evidence, compatibility.evidence], context);
  if (evidenceReason) return unknown(evidenceReason);
  if (scope === 'unknown' || !position.holder.id.trim() || !position.holder.name.trim()) return unknown('unsupported_holder_attribution');
  if (position.instrument !== 'common_share') return unknown('unsupported_instrument');
  if (position.quantityKind !== 'disaggregated_shares') return unknown('aggregate_or_unknown_quantity');
  if (!quantity(position.shares)) return unknown('invalid_quantity');
  if (!['actual_disclosed', 'projected_post_offering'].includes(position.basis)
    || (position.basis === 'projected_post_offering' && !position.projectionConditions?.trim())) return unknown('unknown_position_basis');
  if (position.overlap.status !== 'reviewed_distinct' || !position.overlap.exposureId.trim()) return unknown('overlap_not_excluded');
  if (price.kind !== 'authoritative_final_ipo_price') return unknown('non_final_price');
  const parsedPrice = decimalPrice(price.price);
  if (!parsedPrice || !/^[A-Z]{3}$/.test(price.currency)) return unknown('invalid_price');
  const holdingsDate = day(position.holdingsDate), pricingDate = day(price.pricingDate), through = day(compatibility.reconciledThrough);
  const asOfDay = day(context.analysisAsOf.slice(0, 10))!;
  if (holdingsDate === null || pricingDate === null || holdingsDate > asOfDay || pricingDate > asOfDay) return unknown('invalid_dates');
  if (!hasEvidenceOnOrAfter(position.evidence, holdingsDate)
    || !hasEvidenceOnOrAfter(price.evidence, pricingDate)) return unknown('invalid_dates');
  if (!position.id.trim() || !position.issuerId.trim() || !position.offeringId.trim()
    || !position.securityId.trim() || !position.shareClass.trim() || !price.securityId.trim() || !price.shareClass.trim()
    || position.issuerId !== price.issuerId || position.offeringId !== price.offeringId
    || compatibility.positionId !== position.id || compatibility.fromSecurityId !== position.securityId
    || compatibility.toSecurityId !== price.securityId) return unknown('identity_mismatch');
  if (compatibility.status !== 'reviewed_compatible') return unknown('unreviewed_compatibility');
  if (through === null || through < Math.max(holdingsDate, pricingDate) || through > asOfDay
    || !hasEvidenceOnOrAfter(compatibility.evidence, through)) return unknown('incomplete_reconciliation');
  if (!Number.isSafeInteger(compatibility.numerator) || compatibility.numerator <= 0
    || !Number.isSafeInteger(compatibility.denominator) || compatibility.denominator <= 0) return unknown('unsupported_conversion');
  if (compatibility.method === 'same_security') {
    if (position.securityId !== price.securityId || position.shareClass !== price.shareClass
      || compatibility.numerator !== 1 || compatibility.denominator !== 1) return unknown('unsupported_conversion');
  } else if (compatibility.method !== 'reviewed_common_share_conversion') return unknown('unsupported_conversion');
  const numerator = BigInt(position.shares) * BigInt(compatibility.numerator), denominator = BigInt(compatibility.denominator);
  // Fractional entitlements need separate reviewed treatment; never round them.
  if (numerator % denominator !== 0n) return unknown('unsupported_conversion');
  const pricedShares = numerator / denominator;
  return { ...result, status: 'established', reason: null,
    grossAmount: multiply(pricedShares, parsedPrice), currency: price.currency,
    pricedShares: pricedShares.toString(), price: price.price,
    limitations: scope === 'reported_holder_holding'
      ? [...result.limitations, 'Value belongs to the disclosed organization or trust position; personal economic ownership is not established.']
      : result.limitations };
}

/** No totals: duplicate exposure representations become unknown on every row. */
export function calculateHistoricalHoldings(
  inputs: { position: HistoricalPosition; price: HistoricalIpoPrice; compatibility: HistoricalCompatibility }[],
  context: HistoricalContext,
): HistoricalValueResult[] {
  const exposureCounts = new Map<string, number>(), idCounts = new Map<string, number>();
  for (const { position } of inputs) {
    const exposure = `${position.issuerId}\u0000${position.offeringId}\u0000${position.basis}\u0000${position.overlap.exposureId}`;
    exposureCounts.set(exposure, (exposureCounts.get(exposure) || 0) + 1);
    idCounts.set(position.id, (idCounts.get(position.id) || 0) + 1);
  }
  return inputs.map(({ position, price, compatibility }) => {
    const result = calculateHistoricalPosition(position, price, compatibility, context);
    const exposure = `${position.issuerId}\u0000${position.offeringId}\u0000${position.basis}\u0000${position.overlap.exposureId}`;
    if ((exposureCounts.get(exposure) || 0) > 1 || (idCounts.get(position.id) || 0) > 1) {
      return { ...result, status: 'unknown', reason: 'duplicate_exposure', grossAmount: null,
        currency: null, pricedShares: null, price: null };
    }
    return result;
  });
}

export type DocumentedHolderSale = Security & {
  id: string;
  holder: Holder;
  kind: 'completed_holder_sale' | 'proposed_holder_sale' | 'company_offering' | 'unknown';
  instrument: HistoricalPosition['instrument'];
  sharesSold: number | null;
  saleDate: string;
  evidence: HistoricalEvidence[];
  price: Security & {
    kind: 'documented_completed_holder_sale_price' | 'ipo_price_only' | 'unknown';
    holderId: string;
    saleId: string;
    saleDate: string;
    amount: string;
    currency: string;
    evidence: HistoricalEvidence[];
  };
};

/** Completed sales require holder-specific evidence; an IPO price alone is insufficient. */
export function calculateDocumentedHolderSale(sale: DocumentedHolderSale, context: HistoricalContext): HistoricalValueResult {
  const scope = holderScope(sale.holder);
  const result: HistoricalValueResult = {
    status: 'unknown', reason: null, method: HISTORICAL_VALUE_METHOD,
    analysisAsOf: context.analysisAsOf, positionId: sale.id, holderId: sale.holder.id, valueScope: scope,
    label: 'Documented gross holder-sale proceeds', grossAmount: null, currency: null,
    inputShares: sale.sharesSold, pricedShares: null, price: null,
    holdingsDate: sale.saleDate || null, priceDate: sale.price.saleDate || null,
    positionBasis: 'completed_holder_sale', conditions: null,
    evidence: snapshot([...sale.evidence, ...sale.holder.evidence, ...sale.price.evidence]),
    limitations: ['Gross documented sale consideration; fees, taxes, net proceeds, and payment receipt are unknown.',
      'A fund or trust sale does not establish personal cash proceeds for a controller or beneficiary.'],
  };
  const unknown = (reason: UnknownReason) => ({ ...result, reason });
  const evidenceReason = checkedReviews([sale.evidence, sale.holder.evidence, sale.price.evidence], context);
  if (evidenceReason) return unknown(evidenceReason);
  if (scope === 'unknown' || !sale.holder.id.trim() || !sale.holder.name.trim()) return unknown('unsupported_holder_attribution');
  if (sale.kind !== 'completed_holder_sale') return unknown('sale_not_completed');
  if (sale.instrument !== 'common_share') return unknown('unsupported_instrument');
  if (!quantity(sale.sharesSold)) return unknown('invalid_quantity');
  if (sale.price.kind !== 'documented_completed_holder_sale_price') return unknown('sale_price_not_established');
  const saleDate = day(sale.saleDate);
  if (saleDate === null || saleDate > day(context.analysisAsOf.slice(0, 10))!
    || sale.saleDate !== sale.price.saleDate || !hasEvidenceOnOrAfter(sale.evidence, saleDate)
    || !hasEvidenceOnOrAfter(sale.price.evidence, saleDate)) return unknown('invalid_dates');
  if (!sale.id.trim() || !sale.issuerId.trim() || !sale.offeringId.trim() || !sale.securityId.trim() || !sale.shareClass.trim()
    || sale.issuerId !== sale.price.issuerId || sale.offeringId !== sale.price.offeringId
    || sale.securityId !== sale.price.securityId || sale.shareClass !== sale.price.shareClass
    || sale.holder.id !== sale.price.holderId || sale.id !== sale.price.saleId) return unknown('identity_mismatch');
  const parsedPrice = decimalPrice(sale.price.amount);
  if (!parsedPrice || !/^[A-Z]{3}$/.test(sale.price.currency)) return unknown('invalid_price');
  return { ...result, status: 'established', grossAmount: multiply(BigInt(sale.sharesSold), parsedPrice),
    currency: sale.price.currency, pricedShares: String(sale.sharesSold), price: sale.price.amount };
}

export type SavedHistoricalValues = {
  version: 'historical-value-snapshot/1';
  calculator: typeof HISTORICAL_VALUE_METHOD;
  asOf: string;
  holdings: {
    claimId: string; ownershipId: string; exposureId: string; position: HistoricalPosition;
    price: HistoricalIpoPrice; compatibility: HistoricalCompatibility;
    context: HistoricalContext; output: HistoricalValueResult;
  }[];
  sales: {
    claimId: string; ownershipId: string; exposureId: string; sale: DocumentedHolderSale;
    context: HistoricalContext; output: HistoricalValueResult;
  }[];
  notice: string;
};

/**
 * Render the saved SQL output, never a recomputed replacement. This check may
 * reject an inconsistent saved amount but never upgrades a saved unknown.
 * Preserve this version's calculator when adding a later calculation method.
 */
export function checkedHistoricalSnapshot(snapshot: SavedHistoricalValues): {
  holdings: { saved: HistoricalValueResult; verified: boolean; security: string }[];
  sales: { saved: HistoricalValueResult; verified: boolean; security: string }[];
} {
  const versionSupported = snapshot.version === 'historical-value-snapshot/1'
    && snapshot.calculator === HISTORICAL_VALUE_METHOD;
  const matches = (saved: HistoricalValueResult, calculated: HistoricalValueResult, context: HistoricalContext): boolean => {
    if (!versionSupported || saved.analysisAsOf !== snapshot.asOf || context.analysisAsOf !== snapshot.asOf
      || saved.method !== HISTORICAL_VALUE_METHOD) return false;
    if (saved.status === 'unknown') return saved.grossAmount === null;
    if (saved.status !== 'established' || calculated.status !== 'established') return false;
    return (['grossAmount', 'currency', 'pricedShares', 'price', 'holderId', 'positionId', 'valueScope',
      'holdingsDate', 'priceDate', 'positionBasis'] as const).every((key) => saved[key] === calculated[key]);
  };
  let holdings: ReturnType<typeof checkedHistoricalSnapshot>['holdings'];
  try {
    // Different frozen contexts are evaluated independently; duplicate exposure
    // checks remain across this complete saved report, not across live records.
    const duplicateExposure = new Set<string>();
    const seen = new Set<string>();
    for (const h of snapshot.holdings) {
      const key = `${h.position.issuerId}|${h.position.offeringId}|${h.position.basis}|${h.position.overlap.exposureId}`;
      if (seen.has(key)) duplicateExposure.add(key);
      seen.add(key);
    }
    holdings = snapshot.holdings.map((h) => {
      const key = `${h.position.issuerId}|${h.position.offeringId}|${h.position.basis}|${h.position.overlap.exposureId}`;
      const calculated = calculateHistoricalPosition(h.position, h.price, h.compatibility, h.context);
      return { saved: h.output, verified: matches(h.output, calculated, h.context)
        && (h.output.status === 'unknown' || !duplicateExposure.has(key)), security: h.price.shareClass };
    });
  } catch {
    holdings = snapshot.holdings.map((h) => ({ saved: h.output, verified: false, security: '' }));
  }
  const sales = snapshot.sales.map((s) => {
    try {
      const duplicate = snapshot.sales.some((other) => other !== s && (other.claimId === s.claimId
        || (other.sale.offeringId === s.sale.offeringId && other.exposureId === s.exposureId)));
      return { saved: s.output, verified: matches(s.output, calculateDocumentedHolderSale(s.sale, s.context), s.context)
        && (s.output.status === 'unknown' || !duplicate), security: s.sale.shareClass };
    } catch { return { saved: s.output, verified: false, security: '' }; }
  });
  return { holdings, sales };
}
