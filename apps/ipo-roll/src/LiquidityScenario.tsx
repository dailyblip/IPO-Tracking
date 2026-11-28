import { useState } from 'react';
import { hypotheticalValue, boundaryAtDate } from '../shared/liquidity-scenario.js';
import type { LiquidityReport } from '../shared/liquidity.js';

export function LiquidityScenario({ report, expanded = false }: { report: LiquidityReport; expanded?: boolean }) {
  const [quantity, setQuantity] = useState('');
  const [price, setPrice] = useState('');
  const [date, setDate] = useState('');
  const result = hypotheticalValue(quantity, price);
  const content = <>
    {expanded && <><h2>What-if scenario</h2><p className="scenario-warning">Hypothetical · not a quote, not proceeds</p></>}
    <p className="ownership-note">Your assumptions only. This does not determine liquidity or change your saved report.</p>
    <div className="scenario-inputs">
      <label>Assumed shares<input inputMode="numeric" value={quantity} onChange={e => setQuantity(e.target.value)} placeholder="Enter quantity" maxLength={12}/></label>
      <label>Assumed price (USD)<input inputMode="decimal" value={price} onChange={e => setPrice(e.target.value)} placeholder="Enter price" maxLength={12}/></label>
    </div>
    {expanded && <><label className="scenario-slider-label">Adjust assumed share price<input aria-label="Adjust assumed share price" type="range" min="0" max="500" step="0.25" disabled={!price || Number(price) > 500 || hypotheticalValue('1', price) === null} value={price && Number(price) <= 500 ? Number(price) : 0} onChange={e => setPrice(Number(e.target.value).toFixed(2))}/></label><p className="ownership-note">The slider adjusts your assumption from $0 to $500. It is not a live or IPO-price quote.</p></>}
    <output aria-live="polite" className="scenario-output">{expanded ? <><span>Hypothetical gross value</span><strong>{result === null ? 'Not calculated' : `$${result}`}</strong></> : result === null ? 'Enter whole shares and a nonnegative price with up to two decimals.' : `$${result} hypothetical gross value`}</output>
    {expanded && result === null && <p className="ownership-note">Enter whole shares and a nonnegative price with up to two decimals.</p>}
    <p className="ownership-note">Shares × assumed price. No sale proceeds, fees, taxes, exercise costs or sale eligibility are established. Inputs stay in this view and reset when it closes.</p>
    <div className="scenario-inputs"><label>Scenario date<input type="date" value={date} onChange={e => setDate(e.target.value)}/></label></div>
    {date && <div className="scenario-boundaries" aria-live="polite">
      <p className="ownership-note">Calendar comparison with this snapshot’s reviewed boundaries. Reaching a boundary does not establish release, current holdings or permission to sell.</p>
      {report.positions.flatMap(p => (p.restrictionTimeline || []).map(t => <p key={`${p.id}-${t.id}`}><strong>{p.shareClass || 'Class unspecified'}</strong> · {t.boundaryDate} · {boundaryAtDate(t.boundaryDate, date) === 'reached' ? 'Boundary reached by scenario date; conditions still apply' : boundaryAtDate(t.boundaryDate, date) === 'ahead' ? 'Boundary remains ahead of scenario date' : 'Date comparison unavailable'}</p>))}
      {!report.positions.some(p => p.restrictionTimeline?.length) && <p>No reviewed date boundaries in this snapshot.</p>}
    </div>}
    </>;
  return expanded ? <section className="liquidity-scenario expanded">{content}</section> : <details className="liquidity-scenario"><summary>Explore a hypothetical price or date</summary>{content}</details>;

}
