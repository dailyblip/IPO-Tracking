import type { LiquidityReport } from '../shared/liquidity.js';
import type { Source } from '../shared/types.js';
import { OwnershipGrid } from './OwnershipGrid.js';

const categories = { liquid: 'Currently liquid', future: 'Potential future liquidity', illiquid: 'Illiquid holdings', unknown: 'Insufficient evidence' } as const;
function Evidence({ source }: { source: Source }) {
  let location = source.locator;
  try {
    const loc = JSON.parse(source.locator);
    if (Number.isInteger(loc.first_block) && Number.isInteger(loc.last_block))
      location = loc.first_block === loc.last_block ? `Source block ${loc.first_block}` : `Source blocks ${loc.first_block}–${loc.last_block}`;
  } catch { /* Preserve human-readable locators. */ }
  return <div className="grid-evidence"><strong>{source.title}</strong><p>{source.excerpt}</p><small>{source.date} · {location}</small>{source.url?.startsWith('https://') && <a href={source.url} target="_blank" rel="noreferrer">View source ↗</a>}</div>;
}

export function LiquidityReportView({ report }: { report: LiquidityReport }) {
  return <>
    <p className="report-context">{report.company} · {report.roles?.length
      ? report.roles.map(role => `${role.title} · ${role.relationship}`).join(' · ')
      : report.relationship}</p>
    <div className="report-asof"><span>Analysis as of <strong>{new Date(report.asOf).toLocaleString()}</strong></span><span>Static snapshot · may be stale</span></div>
    <div className="liquidity-summary" aria-label="Reviewed position counts">
      {Object.entries(categories).map(([key, label]) => <div key={key}><strong>{report.positions.length ? report.positions.filter(p => p.category === key).length : '—'}</strong><span>{label}</span></div>)}
    </div>
    <p className="ownership-note">Position counts, not share or dollar totals. Status reflects this saved analysis date.</p>
    <OwnershipGrid positions={report.positions.map(p => ({ ...p, reportedTotal: p.reportedTotal ?? (p.quantityKind === 'beneficial_total' ? null : p.shares), filingDate: p.filingDate || p.holdingsDate }))}
      classifications={Object.fromEntries(report.positions.map(p => [p.id, categories[p.category]]))} action={null}/>
    <details className="report-method"><summary>Assessment details &amp; source versions</summary>
      <p>{report.method} · {report.version}</p>
      {report.positions.map(p => <section className="assessment-detail" key={p.id}>
        <h4>{p.shareClass || 'Share class unspecified'} · {categories[p.category]}</h4>
        <p>{p.explanation}</p><p>{p.conditions}</p>
        <dl><div><dt>Holdings as of</dt><dd>{p.holdingsAsOf || 'Not established'}</dd></div><div><dt>Filing date</dt><dd>{p.filingDate || p.holdingsDate}</dd></div>
          <div><dt>Evidence reviewed</dt><dd>{p.assessmentDate || 'Not recorded'}</dd></div><div><dt>Assessment valid through</dt><dd>{p.validThrough || 'Not established'}</dd></div>
          <div><dt>Lock-up start / end</dt><dd>{p.lockupStart || 'Not confirmed'} / {p.lockupEnd || 'Not confirmed'}</dd></div></dl>
        <p>Current market value unavailable. {p.valuationReason}</p>
        <p>Award components are parts of the reported total, not additional positions. Underlying awards are not confirmed issued shares.</p>
        <p>SEC accession: {p.filingAccession || 'Not recorded in this snapshot'}</p>
        <p className="document-hash">SHA-256: {p.documentHash || 'Not recorded in this snapshot'}</p>
        <details><summary>Source passages and footnotes ({p.evidence.length + 1})</summary><Evidence source={p.source}/>{p.evidence.map((s,i) => <Evidence source={s} key={i}/>)}</details>
      </section>)}
      <details><summary>Company relationship evidence</summary>
        {report.roles?.length
          ? report.roles.map((role, index) => <section key={`${role.title}-${role.relationship}-${index}`}><strong>{role.title} · {role.relationship}</strong><Evidence source={role.source}/></section>)
          : <Evidence source={report.relationshipSource}/>}</details>
      <p>{report.notice}</p>
    </details>
  </>;
}
