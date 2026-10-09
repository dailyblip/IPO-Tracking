import { useRef, useState } from 'react';
import { ArrowLeft, ArrowUpRight, Check, Layers, X } from 'lucide-react';
import type { LiquidityReport } from '../shared/liquidity.js';
import { LiquidityProfileView } from './LiquidityProfileView.js';
export type ProfileSection = 'overview' | 'activity' | 'people' | 'saved' | 'methodology';
export function LiquidityAnalysis({ offeringId, personId, name, demo, request, ticker, saved, toggleSaved, navigate }: {
  offeringId: string; personId: string; name: string; demo: boolean;
  ticker?: string; saved?: boolean; toggleSaved?: () => void; navigate?: (view: ProfileSection) => void;
  request: <T>(path: string, init?: RequestInit) => Promise<T>;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const pending = useRef<{ requestId: string; previousId: string | null } | null>(null);
  const [report, setReport] = useState<LiquidityReport | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [scenarioSession, setScenarioSession] = useState(0);
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
  function close() { dialog.current?.close(); setScenarioSession(n => n + 1); trigger.current?.focus(); }
  return <>
    <button className="value-trigger" ref={trigger} onClick={() => void load()} aria-haspopup="dialog">Liquidity Analysis <ArrowUpRight size={16}/></button>
    <dialog className="value-dialog liquidity-dialog liquidity-profile" ref={dialog} aria-label={`Liquidity Analysis for ${name}`} onKeyDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()} onCancel={e => { e.preventDefault(); close(); }}>
      <header className="profile-topbar"><div className="profile-brand"><Layers size={25}/> IPO Roll<span>.</span></div>
        {navigate && <nav aria-label="Profile navigation">{([['people', 'People Search'], ['activity', 'IPO Activity'], ['saved', 'Saved / Watchlist'], ['methodology', 'Methodology'], ['overview', 'Overview']] as const).map(([view, label]) => <button key={view} className={view === 'people' ? 'active' : ''} onClick={() => { close(); navigate(view); }}>{label}</button>)}</nav>}
        <span className="profile-privacy">PRIVATE TO YOUR ACCOUNT</span><button className="icon-button" aria-label="Close liquidity analysis" onClick={close}><X size={22}/></button>
      </header>
      <div className="profile-page">
        <button className="profile-outline profile-back" onClick={close}><ArrowLeft size={14}/> Back to company research</button>
        <div className="profile-person-heading"><span className="profile-avatar" aria-hidden="true">{name.split(' ').map(n => n[0]).slice(0, 2).join('')}</span><div className="profile-person-copy"><h1>{name}</h1><p>{report ? `${report.relationship} · ${report.company}` : 'Liquidity Analysis'}</p><small>Offering-specific source identity · cross-offering links not yet reviewed</small></div>
          <div className="profile-actions">{toggleSaved && <button className="profile-outline" onClick={toggleSaved}>{saved ? 'Unwatch offering' : 'Watch offering'}</button>}{report && <><span className="profile-saved"><Check size={14}/> Private snapshot saved</span><button className="profile-primary" disabled={busy} onClick={() => void load(true)}>Refresh analysis</button></>}</div>
        </div>
        {busy && <p role="status">Loading your saved analysis…</p>}
        {error && <p role="alert">{error}</p>}
        {error && !demo && <button className="profile-outline" disabled={busy} onClick={() => void load()}>Retry analysis</button>}
        {report && <LiquidityProfileView report={report} ticker={ticker} onBack={close} scenarioKey={`${scenarioSession}-${report.id}`}/>}
      </div>
    </dialog>
  </>;
}
