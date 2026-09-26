import { useEffect, useState } from 'react';
import { Pause, Play } from 'lucide-react';

const routes = [
  'M168 110 C270 110 242 242 354 242',
  'M168 238 C260 238 278 260 354 260',
  'M168 366 C270 366 242 278 354 278',
  'M446 242 C536 242 520 122 618 122',
  'M446 260 C530 260 540 250 618 250',
  'M446 278 C536 278 520 378 618 378',
];

export function LoginFlow() {
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return <figure className={`login-flow ${paused || reduced ? 'flow-paused' : ''}`}>
    <div className="flow-topline"><span><i /> FROM FILING TO INSIGHT</span><span>IPO ROLL / RESEARCH</span></div>
    <svg viewBox="0 0 800 480" aria-hidden="true" focusable="false">
      <defs>
        <pattern id="flow-grid" width="32" height="32" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#315061" opacity=".5" /></pattern>
        <radialGradient id="flow-aura"><stop stopColor="#32d4bf" stopOpacity=".17" /><stop offset="1" stopColor="#32d4bf" stopOpacity="0" /></radialGradient>
        <linearGradient id="flow-core" x2="1" y2="1"><stop stopColor="#153c45" /><stop offset="1" stopColor="#101f34" /></linearGradient>
        <linearGradient id="flow-edge"><stop stopColor="#214b57" /><stop offset=".5" stopColor="#3da4bb" /><stop offset="1" stopColor="#315070" /></linearGradient>
      </defs>
      <rect width="800" height="480" fill="url(#flow-grid)" />
      <ellipse cx="400" cy="260" rx="260" ry="220" fill="url(#flow-aura)" />
      <g className="flow-orbits" fill="none" stroke="#3ca8b2">
        <ellipse cx="400" cy="260" rx="154" ry="104" opacity=".14" />
        <ellipse cx="400" cy="260" rx="184" ry="134" opacity=".10" />
        <circle cx="400" cy="260" r="122" strokeDasharray="3 15" opacity=".3" className="flow-orbit" />
      </g>
      {routes.map((d, i) => <g key={d}>
        <path d={d} fill="none" stroke="url(#flow-edge)" strokeWidth="1.3" />
        <path d={d} fill="none" stroke={i < 3 ? '#5be5cf' : '#74b8ff'} strokeWidth="3" strokeLinecap="round" pathLength="100" className="flow-packet" style={{ animationDelay: `${-i * 1.7}s` }} />
      </g>)}
      {[['S-1 / F-1', 'Registration', 72], ['424B4', 'Final prospectus', 200], ['FOOTNOTES', 'Ownership evidence', 328]].map(([title, subtitle, y]) => <g key={title} transform={`translate(24 ${y})`}>
        <rect width="144" height="76" rx="9" fill="#101e29" stroke="#294653" />
        <path d="M14 16h12l5 5v17H14z M26 16v6h5 M18 28h9 M18 33h7" fill="none" stroke="#6fd7cc" strokeWidth="1.2" />
        <text x="43" y="29" className="flow-label">{title}</text>
        <text x="14" y="58" className="flow-subtitle">{subtitle}</text>
        <circle cx="144" cy="38" r="3" fill="#62e0cb" />
      </g>)}
      <g className="flow-hub">
        <rect x="345" y="205" width="110" height="110" rx="24" fill="url(#flow-core)" stroke="#5cc8c3" strokeOpacity=".55" transform="rotate(45 400 260)" />
        <rect x="354" y="214" width="92" height="92" rx="20" fill="none" stroke="#58bfc1" strokeOpacity=".16" transform="rotate(45 400 260)" />
        <path d="M383 242v30h9v-19h8v19h9v-34" fill="none" stroke="#7af0d8" strokeWidth="3" strokeLinejoin="round" />
        <text x="400" y="296" textAnchor="middle" className="flow-brand">IPO Roll</text>
      </g>
      <text x="400" y="65" textAnchor="middle" className="flow-kicker">PUBLIC EVIDENCE, CONNECTED.</text>
      <text x="400" y="425" textAnchor="middle" className="flow-caption">A clearer view of the people behind the offering.</text>
      {[['IPO ACTIVITY', 'Companies & pricing', 84], ['PEOPLE SEARCH', 'Biographies & sources', 212], ['OWNERSHIP', 'Holdings & restrictions', 340]].map(([title, subtitle, y]) => <g key={title} transform={`translate(618 ${y})`}>
        <rect width="158" height="76" rx="9" fill="#111f2d" stroke="#2c465c" />
        <circle cy="38" r="3" fill="#79b9ff" />
        <text x="15" y="29" className="flow-label">{title}</text>
        <text x="15" y="56" className="flow-subtitle">{subtitle}</text>
        <path d="M132 20l5 5-5 5" fill="none" stroke="#6ba4ce" />
      </g>)}
    </svg>
    <figcaption><span>Illustrated research flow · not a live data feed</span>
      <button type="button" className="flow-motion" disabled={reduced} onClick={() => setPaused(!paused)} aria-label={reduced ? 'Animation off for reduced motion' : paused ? 'Play visualization' : 'Pause visualization'}>
        {paused || reduced ? <Play size={12} /> : <Pause size={12} />}{reduced ? 'Motion off' : paused ? 'Play' : 'Pause'}
      </button>
    </figcaption>
  </figure>;
}
