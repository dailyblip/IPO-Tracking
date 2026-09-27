import { useState } from 'react';
import { hypotheticalValue, boundaryAtDate } from '../shared/liquidity-scenario.js';
import type { LiquidityReport } from '../shared/liquidity.js';

export function LiquidityScenario({ report }: { report: LiquidityReport }) {
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [date, setDate] = useState('');
  const result = hypotheticalValue(quantity, price);
  return <details className="liquidity-scenario">
    <summary>Explore a hypothetical price or date</summary>
    <p className="ownership-note">Your assumptions only. This does not determine liquidity or change your saved report.</p>
    <div className="scenario-inputs">
      <label>Assumed shares<input inputMode="numeric" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="Enter quantity" maxLength={12}/></label>
      <label>Assumed price (USD)<input inputMode="decimal" value={price} onChange={e => setPrice(e.target.value)} placeholder="Enter price" maxLength={12}/></label>
    </div>
    <output aria-live="polite" className="scenario-output">{result === null ? 'Enter whole shares and a nonnegative price with up to two decimals.' : `$${result} hypothetical gross value`}</output>
    <p className="ownership-note">Shares × assumed price. No sale proceeds, fees, taxes, exercise costs or sale eligibility are established. Inputs stay in this view and reset when it closes.</p>
    <div className="scenario-inputs"><label>Scenario date<input type="date" value={date} onChange={e => setDate(e.target.value)}/></label></div>
    {date && <div className="scenario-boundaries" aria-live="polite">
      <p className="ownership-note">Calendar comparison with this snapshot’s reviewed boundaries. Reaching a boundary does not establish release, current holdings or permission to sell.</p>
      {report.positions.flatMap(p => (p.restrictionTimeline || []).map(t => <p key={`${p.id}-${t.id}`}><strong>{p.shareClass || 'Class unspecified'}</strong> · {t.boundaryDate} · {boundaryAtDate(t.boundaryDate, date) === 'reached' ? 'Boundary reached by scenario date; conditions still apply' : boundaryAtDate(t.boundaryDate, date) === 'ahead' ? 'Boundary remains ahead of scenario date' : 'Date comparison unavailable'}</p>))}
      {!report.positions.some(p => p.restrictionTimeline?.length) && <p>No reviewed date boundaries in this snapshot.</p>}
    </div>}
  </details>;
}
