import type { ReactNode } from 'react';
import type { LiquidityReport } from '../shared/liquidity.js';
import type { Source } from '../shared/types.js';
import { LiquidityReportView } from './LiquidityReportView.js';
import { LiquidityScenario } from './LiquidityScenario.js';

function date(value: string | null | undefined) {
  if (!value) return 'Date not established';
  const parsed = new Date(`${value}T12:00:00Z`);
  return Number.isFinite(parsed.getTime()) ? parsed.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric', timeZone: 'UTC' }) : 'Date not established';
}
function SourceEvidence({ sources }: { sources: Source[] }) {
  return <details className="timeline-evidence"><summary>Filing evidence · {sources.length} {sources.length === 1 ? 'passage' : 'passages'}</summary>
    {sources.map((source, i) => <div key={i}><strong>{source.title}</strong><p>{source.excerpt}</p><small>{source.date}</small>{source.url?.startsWith('https://') && <a href={source.url} target="_blank" rel="noreferrer">View filing ↗</a>}</div>)}
  </details>;
}
function TimelineEvent({ when, title, badge, tone, children }: { when: string; title: string; badge: string; tone: string; sortDate?: string | null; children: ReactNode }) {
  return <li className={`profile-event ${tone}`}><div className="profile-event-date">{when}</div><div className="profile-event-content"><div className="profile-event-title"><h3>{title}</h3><span className="profile-event-badge">{badge}</span></div>{children}</div></li>;
}
export function LiquidityProfileView({ report, ticker, onBack, scenarioKey }: { report: LiquidityReport; ticker?: string; onBack: () => void; scenarioKey: string }) {
  const positions = [...report.positions].sort((a, b) => (a.holdingsAsOf || '9999').localeCompare(b.holdingsAsOf || '9999'));
  const boundaries = report.positions.flatMap(p => (p.restrictionTimeline || []).map(t => ({ p, t }))).sort((a, b) => a.t.boundaryDate.localeCompare(b.t.boundaryDate));
  return <div className="profile-columns">
    <aside className="profile-offerings" aria-label="Connected offerings">
      <h2>Connected offering · 1</h2>
      <div className="profile-offering-card"><div><strong>{report.company}</strong>{ticker && <span>{ticker}</span>}</div><p>{report.relationship}</p><small>Selected offering · saved analysis</small></div>
      <button className="profile-outline profile-offering-link" onClick={onBack}>View company research →</button>
      <p className="profile-scope">This snapshot covers one offering. Other offerings require reviewed identity links.</p>
      <div className="profile-snapshot"><span>PRIVATE SNAPSHOT</span><strong>{new Date(report.asOf).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}</strong><p>Saved as of {new Date(report.asOf).toLocaleTimeString()}. Source facts may have changed. Refresh explicitly to create a new version.</p></div>
    </aside>
    <section className="profile-timeline-panel" aria-labelledby="profile-timeline-title">
      <div className="profile-panel-heading"><h2 id="profile-timeline-title">Liquidity timeline{ticker ? ` · ${ticker}` : ''}</h2><span>Evidence from this snapshot</span></div>
      <ol className="profile-timeline">
        {[...positions.map(p => (
          <TimelineEvent key={`position-${p.id}`} sortDate={p.positionBasis === 'post' ? null : p.holdingsAsOf} when={p.positionBasis === 'post' ? 'Projected' : date(p.holdingsAsOf)} title={p.positionBasis === 'post' ? 'Projected post-offering position' : 'Disclosed ownership position'} badge={p.positionBasis === 'post' ? 'Projected' : 'Reported'} tone={p.positionBasis === 'post' ? 'projected' : 'reported'}>
            <p><strong>{p.reportedTotal == null && p.shares == null ? 'Quantity not established' : `${(p.reportedTotal ?? p.shares)!.toLocaleString('en-US')} reported`}</strong> · {p.shareClass || 'Share class unspecified'}</p>
            {p.reportedHolder && <p>Reported holder: {p.reportedHolder.name}. {p.attribution?.description}</p>}
            <p className="profile-event-note">{p.quantityKind === 'beneficial_total' ? 'Beneficial total; may include awards or attributed interests. Not a personal-share total.' : 'Personal economic ownership and current saleability are not established by the quantity alone.'}</p>
            <SourceEvidence sources={[p.source, ...p.evidence]}/>
            <small className="profile-filing-date">Filed {date(p.filingDate || p.holdingsDate)} · {p.filingAccession || 'Accession not recorded'}</small>
          </TimelineEvent>
        )), ...boundaries.map(({p, t}) => <TimelineEvent key={`${p.id}-${t.id}`} sortDate={t.boundaryDate} when={date(t.boundaryDate)} title="Lock-up boundary" badge="Scheduled · conditional" tone="conditional"><p>{p.shareClass || 'Share class unspecified'} · {t.trigger} + {t.dayCount} days.</p><p>{t.conditions}</p><p className="profile-event-note">Calendar boundary, not a confirmed release or permission to sell.</p><SourceEvidence sources={t.evidence}/></TimelineEvent>)].sort((a, b) => (a.props.sortDate || '9999').localeCompare(b.props.sortDate || '9999'))}
        {!report.positions.length && <TimelineEvent when="Review pending" title="Holdings evidence incomplete" badge="Not established" tone="projected"><p>No reviewed positions are included in this snapshot. This does not establish zero ownership.</p></TimelineEvent>}
        <TimelineEvent when="Not established" title="Completed holder sales" badge="Evidence required" tone="projected"><p>This snapshot does not establish completed sales or cash proceeds for this holder. Final offering terms alone do not prove a sale closed.</p></TimelineEvent>
      </ol>
      <details className="profile-full-evidence"><summary>Ownership grid, assessments &amp; full source versions</summary><LiquidityReportView report={report}/></details>
    </section>
    <aside className="profile-scenario-panel" aria-label="What-if scenario"><LiquidityScenario key={scenarioKey} report={report} expanded/></aside>
  </div>;
}
