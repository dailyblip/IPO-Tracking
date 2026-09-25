import type { Source } from './types.js';
export type LiquidityReport = {
  id: string;
  version: string;
  asOf: string;
  method: string;
  offeringId: string;
  personId: string;
  company: string;
  person: string;
  relationship: string;
  relationshipSource: Source;
  notice: string;
  positions: {
    id: string;
    shareClass: string | null;
    shares: number | null;
    quantityKind?: 'reported_shares' | 'beneficial_total';
    reportedTotal?: number | null;
    components?: {
      status: 'not_reviewed' | 'incomplete' | 'reconciled';
      items: { ordinal: number; instrument: 'common_share' | 'rsu' | 'option' | 'warrant'; quantity: number; attribution: 'direct' | 'trust_or_family' | 'fund_or_control' | 'unknown'; description: string; source: Source }[];
    };
    positionBasis: string;
    holdingsDate: string;
    filingDate?: string;
    holdingsAsOf?: string | null;
    filingAccession?: string;
    documentHash?: string;
    source: Source;
    category: 'liquid' | 'future' | 'illiquid' | 'unknown';
    assessmentDate: string | null;
    validThrough: string | null;
    lockupStart: string | null;
    lockupEnd: string | null;
    restrictionTimeline?: {
      id: string; trigger: string; triggerDate: string; dayCount: number;
      boundaryDate: string; method: string; reviewedOn: string;
      conditions: string; evidence: Source[];
    }[];
    explanation: string;
    conditions: string;
    evidence: Source[];
    marketValue: number | null;
    valuationReason: string;
  }[];
};
