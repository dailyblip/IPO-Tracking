import type { LiquidityReport } from './liquidity.js';

// Shared filing facts. No private report IDs, timestamps, request status or history.
export type OwnershipPosition = Pick<LiquidityReport['positions'][number],
  'id' | 'shareClass' | 'reportedTotal' | 'quantityKind' | 'positionBasis' |
  'holdingsAsOf' | 'filingDate' | 'filingAccession' | 'source' | 'components' |
  'restrictionTimeline' | 'conditions' | 'explanation' | 'assessmentDate' | 'evidence' |
  'reportedHolder' | 'attribution'>;

const instruments = { common_share: 'Common shares', option: 'Option underlying shares', rsu: 'RSU underlying shares', warrant: 'Warrant underlying shares', preferred_conversion: 'Common shares issuable on preferred conversion' };
const attributions = { direct: 'Direct holding as disclosed', trust_or_family: 'Trust / family attribution', fund_or_control: 'Fund / control attribution', unknown: 'Attribution unconfirmed' };

export function ownershipRows(positions: OwnershipPosition[]) {
  return positions.flatMap(p => p.quantityKind === 'beneficial_total' && p.components?.status === 'reconciled'
    ? p.components.items.map(c => ({ id: `${p.id}-${c.ordinal}`, security: instruments[c.instrument],
      quantity: c.quantity, attribution: attributions[c.attribution], source: c.source,
      description: c.description, position: p }))
    : [{ id: p.id, security: p.shareClass || 'Class / series unconfirmed', quantity: p.reportedTotal ?? null,
      attribution: p.attribution ? `${p.attribution.kind === 'beneficial_entitlement' ? 'Beneficiary entitlement' : p.attribution.kind === 'reported_beneficial_owner' ? 'SEC-reported beneficial owner' : 'Voting / control authority'} · reported holder: ${p.reportedHolder?.name || 'unconfirmed'}` : p.quantityKind === 'beneficial_total' ? 'Reported beneficial total · breakdown pending' : 'See ownership footnotes',
      source: p.source, description: p.explanation, position: p }]);
}
