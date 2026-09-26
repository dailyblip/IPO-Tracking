import type { LiquidityReport } from './liquidity.js';

// Shared filing facts. No private report IDs, timestamps, request status or history.
export type OwnershipPosition = Pick<LiquidityReport['positions'][number],
  'id' | 'shareClass' | 'reportedTotal' | 'quantityKind' | 'positionBasis' |
  'holdingsAsOf' | 'filingDate' | 'filingAccession' | 'source' | 'components' |
  'restrictionTimeline' | 'conditions' | 'explanation' | 'assessmentDate' | 'evidence'>;

const instruments = { common_share: 'Common shares', option: 'Option underlying shares', rsu: 'RSU underlying shares', warrant: 'Warrant underlying shares' };
const attributions = { direct: 'Direct holding as disclosed', trust_or_family: 'Trust / family attribution', fund_or_control: 'Fund / control attribution', unknown: 'Attribution unconfirmed' };

export function ownershipRows(positions: OwnershipPosition[]) {
  return positions.flatMap(p => p.quantityKind === 'beneficial_total' && p.components?.status === 'reconciled'
    ? p.components.items.map(c => ({ id: `${p.id}-${c.ordinal}`, security: instruments[c.instrument],
      quantity: c.quantity, attribution: attributions[c.attribution], source: c.source,
      description: c.description, position: p }))
    : [{ id: p.id, security: p.shareClass || 'Class / series unconfirmed', quantity: p.reportedTotal ?? null,
      attribution: p.quantityKind === 'beneficial_total' ? 'Breakdown incomplete · includes awards' : 'See ownership footnotes',
      source: p.source, description: p.explanation, position: p }]);
}
