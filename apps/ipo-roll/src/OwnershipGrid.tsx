import { Fragment, useState, type ReactNode } from 'react';
import type { Source } from '../shared/types.js';
import { ownershipRows, type OwnershipPosition } from '../shared/ownership.js';

function Evidence({ source }: { source: Source }) {
  return <div className="grid-evidence"><strong>{source.title}</strong><p>{source.excerpt}</p>
    <small>{source.date}</small>{source.url?.startsWith('https://') && <a href={source.url} target="_blank" rel="noreferrer">Open filing ↗</a>}</div>;
}
export function OwnershipGrid({ positions, action, classifications }: { positions?: OwnershipPosition[]; action: ReactNode; classifications?: Record<string, string> }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const rows = ownershipRows(positions || []);
  return <section className="ownership-reference" aria-label="Beneficial ownership quick reference">
    <div className="ownership-heading"><div><span className="eyebrow">INDIVIDUAL RESEARCH</span><h4>Beneficial ownership</h4></div>{action}</div>
    <OwnershipValueSummary />
    {rows.length ? <>
      <div className="ownership-scroll" role="region" aria-label="Stock classes and lock-up periods" tabIndex={0}>
        <table className="ownership-grid">
          <caption>Stock classes, disclosed quantities and lock-up evidence</caption>
          <thead><tr><th scope="col">Stock / series</th><th scope="col">Quantity</th><th scope="col">Position date</th><th scope="col">Lock-up period</th><th scope="col">Evidence</th></tr></thead>
          <tbody>{rows.map(row => {
            const p = row.position;
            return <Fragment key={row.id}><tr>
              <th scope="row"><strong>{row.security}</strong><small>{row.attribution}</small></th>
              <td className="ownership-quantity">{row.quantity?.toLocaleString() ?? 'Not established'}</td>
              <td><strong>{p.positionBasis === 'post' ? 'Projected after IPO' : p.positionBasis === 'pre' ? 'Before IPO' : 'Basis unconfirmed'}</strong><small>{p.holdingsAsOf || 'Holdings date unconfirmed'}</small><small>Filed {p.filingDate}</small></td>
              <td>{classifications && <span className="liquidity-status">{classifications[p.id]}</span>}{p.restrictionTimeline?.length ? p.restrictionTimeline.map(t => <div key={t.id}><strong>{t.dayCount} calendar days</strong><small>From {t.triggerDate}</small><span className="restriction-date">Boundary {t.boundaryDate}</span><small>Conditional · sale eligibility unconfirmed</small></div>) : <><strong>Timing unconfirmed</strong><small>{p.conditions ? 'See source footnotes' : 'Review pending'}</small></>}</td>
              <td><button className="grid-footnote-button" aria-expanded={expanded === row.id} onClick={() => setExpanded(expanded === row.id ? null : row.id)}>Footnotes</button></td>
            </tr>{expanded === row.id && <tr><td colSpan={5}><div className="ownership-footnotes"><p>{row.description}</p>
                <Evidence source={row.source}/>
                {p.attribution && <><strong>{p.attribution.kind === 'beneficial_entitlement' ? 'Beneficiary attribution' : 'Control attribution'}</strong><p>{p.attribution.description}</p><Evidence source={p.attribution.source}/></>}
                {p.conditions && <><strong>Restrictions · reviewed {p.assessmentDate || 'date unknown'}</strong><p>{p.conditions}</p></>}
                {p.restrictionTimeline?.map(t => <div key={t.id}><strong>{t.trigger}: {t.triggerDate} + {t.dayCount} calendar days → {t.boundaryDate}</strong><p>{t.conditions}</p><small>Trigger is day zero; no business-day, holiday or time-zone adjustment inferred. Terms reviewed {t.reviewedOn} · {t.method}</small>{t.evidence.map((s,i)=><Evidence source={s} key={i}/>)}</div>)}
                {p.evidence.map((s,i)=><Evidence source={s} key={i}/>)}
                <small>SEC accession {p.filingAccession}</small>
              </div></td></tr>}</Fragment>;
          })}</tbody>
        </table>
      </div>
      <p className="ownership-note">Alternative snapshots · do not sum. A lock-up boundary does not confirm sale eligibility.</p>
    </> : <div className="ownership-empty">Holdings review pending · unknown is not zero.</div>}
  </section>;
}

// The current reviewed position contract has neither a compatible historical
// price basis nor verified holder sale proceeds. Do not derive either from a
// beneficial total, an issuer offering amount or a current quote.
export function OwnershipValueSummary() {
  return <div className="wealth-reference" aria-label="Retained stake and IPO sale proceeds">
    <div><small>Retained stake value</small><strong>Not established</strong><span>Historical IPO-price basis</span></div>
    <div><small>Documented IPO sale proceeds</small><strong>Not established</strong><span>Gross personal sales · not company proceeds</span></div>
    <details className="value-basis"><summary>Value basis &amp; limitations</summary>
      <p>Retained stake value needs reviewed retained quantities, compatible security/class or conversion terms, and the final IPO price. It is a historical estimate, not current wealth.</p>
      <p>Sale proceeds need evidence of this holder’s completed sales and sale price. Proposed sales do not qualify. Fees, taxes and net proceeds are unknown.</p>
      <p>Beneficial ownership may include trust, fund or voting interests and awards. It does not by itself establish personal economic ownership or saleability. Current market value is unavailable without an approved quote feed.</p>
    </details>
  </div>;
}
