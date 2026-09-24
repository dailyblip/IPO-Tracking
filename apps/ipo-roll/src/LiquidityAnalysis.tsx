import { useRef, useState } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import type { LiquidityReport } from '../shared/liquidity.js';
import type { Source } from '../shared/types.js';
const categories = { liquid: 'Currently liquid', future: 'Potential future liquidity', illiquid: 'Illiquid holdings', unknown: 'Insufficient evidence' } as const;
function Evidence({ source }: { source: Source }) {
  const safeUrl = source.url?.startsWith('https://') ? source.url : null;
  return <div className="source-box"><div><strong>{source.title}</strong><p>{source.excerpt}</p><small>{source.date} · {source.locator}</small>{safeUrl && <p><a href={safeUrl} target="_blank" rel="noreferrer">View source ↗</a></p>}</div></div>;
}
export function LiquidityAnalysis({ offeringId, personId, name, demo, request }: {
  offeringId: string; personId: string; name: string; demo: boolean;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const pending = useRef<{ requestId: string; previousId: string | null } | null>(null);
  const [report, setReport] = useState<LiquidityReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const path = `/offerings/${offeringId}/people/${personId}/liquidity`;
  async function load(refresh = false) {
    if (busy) return;
    dialog.current?.showModal();
    if (demo) { setError('Private saved reports require a signed-in staging account. Sample mode does not save analyses.'); return; }
    setBusy(true); setError('');
    try {
      if (!refresh && !pending.current) {
        const saved = await request<LiquidityReport | null>(path);
        if (saved) { setReport(saved); return; }
      }
      pending.current ||= { requestId: crypto.randomUUID(), previousId: refresh ? report?.id || null : null };
      const result = await request<LiquidityReport>(path, { method: 'POST', body: JSON.stringify(pending.current) });
      setReport(result); pending.current = null;
    } catch (e) { setError(e instanceof Error ? e.message : 'Unable to load analysis.'); }
    finally { setBusy(false); }
  }
  function close() { dialog.current?.close(); trigger.current?.focus(); }
  return <>
    <button className="value-trigger" ref={trigger} onClick={() => void load()} aria-haspopup="dialog">Liquidity Analysis <ArrowUpRight size={16}/></button>
    <dialog className="value-dialog liquidity-dialog" ref={dialog} aria-label={`Liquidity Analysis for ${name}`} onKeyDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()} onCancel={e => { e.preventDefault(); close(); }}>
      <div className="value-dialog-heading"><div><span className="eyebrow">PRIVATE TO YOUR ACCOUNT</span><h2>Liquidity Analysis</h2></div><button className="icon-button" aria-label="Close liquidity analysis" onClick={close}><X size={22}/></button></div>
      <p className="value-person">{name}</p>
      {busy && <p role="status">Loading your saved analysis…</p>}
      {error && <p role="alert">{error}</p>}
      {error && !demo && <button className="value-trigger" disabled={busy} onClick={() => void load()}>Retry analysis</button>}
      {report && <>
        <p>{report.company} · {report.relationship}</p>
        <p>Saved {new Date(report.asOf).toLocaleString()} · {report.method}</p>
        <p className="value-note">This report does not update automatically. Dates, prices and restrictions may have changed. Refresh creates a new snapshot.</p>
        <p>Reviewed positions by liquidity category</p><div className="liquidity-summary">{Object.entries(categories).map(([key,label]) => <div key={key}><strong>{report.positions.length ? report.positions.filter(p => p.category === key).length : "—"}</strong><span>{label}</span></div>)}</div>
        {!report.positions.length && <div className="source-box"><div><strong>Insufficient evidence</strong><p>No reviewed individual stock positions are available for this person. Lock-ups, footnotes and liquidity cannot yet be assessed. This does not establish zero ownership.</p></div></div>}
        {report.positions.map(p => <section className="value-result" key={p.id}>
          <h3>{p.shareClass || 'Share class unspecified'}</h3><strong>{categories[p.category]}</strong>
          <p>{p.shares === null ? 'Share count unknown' : `${p.shares.toLocaleString()} disclosed shares`} · {p.positionBasis} offering basis · Filing date {p.holdingsDate}</p>
          <p>{p.explanation}</p><p>{p.conditions}</p>
          <p>Lock-up start: {p.lockupStart || 'Not confirmed'} · End: {p.lockupEnd || 'Not confirmed'}</p>
          {p.assessmentDate && <p>Evidence reviewed {p.assessmentDate} · Valid through {p.validThrough}. Expired assessments are classified as insufficient evidence.</p>}
          <p>Market-value estimate unavailable. {p.valuationReason}</p>
          <Evidence source={p.source}/>{p.evidence.map((s,i) => <Evidence source={s} key={i}/>)}
        </section>)}
        <details><summary>Company relationship evidence</summary><Evidence source={report.relationshipSource}/></details>
        <p className="value-note">{report.notice}</p>
        <button className="value-trigger" disabled={busy} onClick={() => void load(true)}>Refresh analysis</button>
      </>}
    </dialog>
  </>;
}
