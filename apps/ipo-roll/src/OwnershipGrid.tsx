import { Fragment, useState, type ReactNode } from 'react';
import type { Source } from '../shared/types.js';
import { ownershipRows, type OwnershipPosition } from '../shared/ownership.js';

function Evidence({ source }: { source: Source }) {
  return <div className="grid-evidence"><strong>{source.title}</strong><p>{source.excerpt}</p>
    <small>{source.date}</small>{source.url?.startsWith('https://') && <a href={source.url} target="_blank" rel="noreferrer">Open filing ↗</a>}</div>;
}
export function OwnershipGrid({ positions, action }: { positions?: OwnershipPosition[]; action: ReactNode }) {
  const [expanded, setExpanded] = useState<string | null>(null);
  const rows = ownershipRows(positions || []);
  return <section className="ownership-reference" aria-label="Beneficial ownership quick reference">
    <div className="ownership-heading"><div><span className="eyebrow">INDIVIDUAL RESEARCH</span><h4>Beneficial ownership</h4></div>{action}</div>
    <p className="ownership-intro">Disclosed stock and award interests, with restrictions at a glance.</p>
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
              <td>{p.restrictionTimeline?.length ? p.restrictionTimeline.map(t => <div key={t.id}><strong>{t.dayCount} calendar days</strong><small>From {t.triggerDate}</small><span className="restriction-date">Boundary {t.boundaryDate}</span><small>Conditional · sale eligibility unconfirmed</small></div>) : <><strong>Timing unconfirmed</strong><small>{p.conditions ? 'Restriction terms in footnotes' : 'Review pending'}</small></>}</td>
              <td><button className="grid-footnote-button" aria-expanded={expanded === row.id} onClick={() => setExpanded(expanded === row.id ? null : row.id)}>Footnotes</button></td>
            </tr>{expanded === row.id && <tr><td colSpan={5}><div className="ownership-footnotes"><p>{row.description}</p>
                <Evidence source={row.source}/>
                {p.conditions && <><strong>Restrictions · reviewed {p.assessmentDate || 'date unknown'}</strong><p>{p.conditions}</p></>}
                {p.restrictionTimeline?.map(t => <div key={t.id}><p>{t.conditions}</p>{t.evidence.map((s,i)=><Evidence source={s} key={i}/>)}</div>)}
                {p.evidence.map((s,i)=><Evidence source={s} key={i}/>)}
                <small>SEC accession {p.filingAccession}</small>
              </div></td></tr>}</Fragment>;
          })}</tbody>
        </table>
      </div>
      <p className="ownership-note">Award components are shown once, without adding their parent total. Pre-IPO and projected positions are alternative snapshots; do not add them together. A lock-up boundary alone does not establish sale eligibility.</p>
    </> : <div className="ownership-empty">No reviewed holdings available yet. This does not establish zero ownership.</div>}
    <div className="wealth-reference">
      <div><small>Estimated holdings value</small><strong>Not yet available</strong><span>Requires a supported position and licensed matching quote.</span></div>
      <div><small>Documented IPO sale proceeds</small><strong>Not established</strong><span>No verified personal sale proceeds are recorded here.</span></div>
    </div>
    <p className="ownership-note">Holdings value and money received from selling shares are different measures. Liquidity Analysis opens your private, dated assessment.</p>
  </section>;
}
