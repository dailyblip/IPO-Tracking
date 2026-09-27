import { useRef, useState } from 'react';
import { ArrowUpRight, X } from 'lucide-react';
import type { LiquidityReport } from '../shared/liquidity.js';
import { LiquidityReportView } from './LiquidityReportView.js';
import { LiquidityScenario } from './LiquidityScenario.js';
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
    <dialog className="value-dialog liquidity-dialog" ref={dialog} aria-label={`Liquidity Analysis for ${name}`} onKeyDown={e => e.stopPropagation()} onClick={e => e.stopPropagation()} onCancel={e => { e.preventDefault(); close(); }}>
      <div className="value-dialog-heading"><div><span className="eyebrow">PRIVATE TO YOUR ACCOUNT</span><h2>Liquidity Analysis</h2></div><button className="icon-button" aria-label="Close liquidity analysis" onClick={close}><X size={22}/></button></div>
      <p className="value-person">{name}</p>
      {busy && <p role="status">Loading your saved analysis…</p>}
      {error && <p role="alert">{error}</p>}
      {error && !demo && <button className="value-trigger" disabled={busy} onClick={() => void load()}>Retry analysis</button>}
      {report && <>
        <LiquidityReportView report={report}/>
        <LiquidityScenario key={`${scenarioSession}-${report.id}`} report={report}/>
        <div className="report-refresh"><p>Saved reports stay unchanged. Refresh creates a new dated version.</p>
          <button className="value-trigger" disabled={busy} onClick={() => void load(true)}>Refresh analysis</button>
        </div>
      </>}
    </dialog>
  </>;
}
