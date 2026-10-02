import type { Source } from './types.js';
export type Holding = {
  id: string;
  issuerId: string;
  securityId: string;
  shareClass: string;
  shares: number;
  basis: 'current' | 'projected-post-offering';
  asOf: string;
  ownership: 'direct' | 'trust' | 'indirect' | 'mixed' | 'unknown';
  personalEconomicInterestConfirmed: boolean;
  reconciliationConfirmed: boolean;
  reconciledThrough?: string;
  reviewed: boolean;
  instrument: 'common' | 'option' | 'other';
  footnotes: Source[];
  source: Source;
  restrictions: string;
  restrictionSource?: Source;
};
export type HoldingQuote = {
  issuerId: string;
  securityId: string;
  price: number;
  currency: string;
  asOf: string;
  kind: 'live' | 'last-known';
  verified: boolean;
  source: Source;
};
/** No preliminary IPO prices, inferred trust interests, or option share multiplication. */
export function valueHolding(h: Holding, q?: HoldingQuote) {
  const unavailable = (reason: string) => ({ amount: null, reason, quote: null });
  if (!h.reviewed || !h.source.url || !h.source.excerpt) return unavailable('Holding evidence has not been reviewed.');
  if (h.basis !== 'current') return unavailable('Projected position; not confirmed current holdings.');
  if (h.instrument !== 'common') return unavailable('Instrument requires a separate valuation method.');
  if (!h.personalEconomicInterestConfirmed) return unavailable('Personal economic interest has not been confirmed.');
  if (!h.reconciliationConfirmed) return unavailable('Holdings and corporate actions have not been reconciled to the price date.');
  if (!Number.isSafeInteger(h.shares) || h.shares < 0) return unavailable('Share count is not verified for calculation.');
  if (!q?.verified || !q.source.url || !Number.isFinite(q.price) || q.price <= 0)
    return unavailable('No verified trading price available.');
  if (h.issuerId !== q.issuerId || h.securityId !== q.securityId)
    return unavailable('Price does not match this issuer and share class.');
  const priceTime = Date.parse(q.asOf), holdingTime = Date.parse(h.asOf);
  if (!Number.isFinite(priceTime) || !Number.isFinite(holdingTime) || priceTime < holdingTime || priceTime > Date.now())
    return unavailable('Price date is incompatible with the disclosed position.');
  const reconciledTime = Date.parse(h.reconciledThrough || '');
  if (!Number.isFinite(reconciledTime) || reconciledTime < priceTime) return unavailable('Holdings have not been reconciled through the quote timestamp.');
  if (!/^[A-Z]{3}$/.test(q.currency)) return unavailable('Price currency is not verified.');
  const amount = h.shares * q.price;
  if (!Number.isFinite(amount) || amount > Number.MAX_SAFE_INTEGER) return unavailable('Value exceeds supported precision.');
  return { amount, reason: 'Gross market estimate, not cash proceeds or confirmation of saleability. Before taxes, fees and market impact.', quote: q };
}
