import { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';

type Point = [number, number];
const W = 900, H = 430, CORE: Point = [478, 215];
const curves: Point[][] = [
  [[-25, 30], [285, -15], [220, 165], CORE],
  [[-30, 150], [235, 105], [245, 220], CORE],
  [[-30, 300], [210, 385], [288, 236], CORE],
  [[50, 445], [350, 475], [240, 275], CORE],
  [CORE, [668, 215], [636, -20], [925, 35]],
  [CORE, [650, 205], [710, 198], [930, 145]],
  [CORE, [688, 218], [670, 325], [930, 304]],
  [CORE, [633, 250], [710, 452], [918, 435]],
];
function point(curve: Point[], t: number): Point {
  const u = 1 - t;
  return [0, 1].map(k => u ** 3 * curve[0][k] + 3 * u * u * t * curve[1][k] + 3 * u * t * t * curve[2][k] + t ** 3 * curve[3][k]) as Point;
}
const paths = curves.map(c => Array.from({ length: 181 }, (_, i) => {
  const p = point(c, i / 180), a = point(c, Math.max(0, (i - 1) / 180)), b = point(c, Math.min(1, (i + 1) / 180));
  const length = Math.hypot(b[0] - a[0], b[1] - a[1]) || 1;
  return { x: p[0], y: p[1], nx: -(b[1] - a[1]) / length, ny: (b[0] - a[0]) / length };
}));

function ParticleTubes({ stopped }: { stopped: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const clock = useRef(0);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    let frame = 0, last = 0, visible = true, disposed = false;
    const colors = ['#46ead0', '#63aaff', '#c3fff4'];
    // Cache light sprites rather than allocating blur filters for each particle.
    const sprites = colors.map(color => {
      const sprite = document.createElement('canvas'); sprite.width = sprite.height = 32;
      const s = sprite.getContext('2d')!;
      const g = s.createRadialGradient(16, 16, 0, 16, 16, 16);
      g.addColorStop(0, '#ffffff'); g.addColorStop(.12, color); g.addColorStop(.35, color + '80'); g.addColorStop(1, color + '00');
      s.fillStyle = g; s.fillRect(0, 0, 32, 32); return sprite;
    });
    const background = document.createElement('canvas'); background.width = W; background.height = H;
    const b = background.getContext('2d')!;
    const aura = b.createRadialGradient(...CORE, 15, ...CORE, 310);
    aura.addColorStop(0, '#1b867b3b'); aura.addColorStop(.5, '#0d3c4928'); aura.addColorStop(1, '#0b152000');
    b.fillStyle = aura; b.fillRect(0, 0, W, H);
    for (let j = 0; j < 110; j++) {
      b.fillStyle = j % 3 ? '#749baa35' : '#73cfc963';
      b.fillRect((j * 137.51) % W, (j * 83.27) % H, j % 7 ? 1 : 2, 1);
    }
    paths.forEach((path, i) => {
      const color = i < 4 ? '68,230,202' : '95,167,255';
      const draw = (offset: number, width: number, alpha: number) => {
        b.beginPath(); path.forEach((p, j) => { const x = p.x + p.nx * offset, y = p.y + p.ny * offset; if (j) b.lineTo(x, y); else b.moveTo(x, y); });
        b.strokeStyle = `rgba(${color},${alpha})`; b.lineWidth = width; b.stroke();
      };
      draw(0, 34, .015); draw(0, 22, .025); draw(0, 17, .03);
      draw(-10, 3, .045); draw(10, 3, .045); draw(-10, .7, .3); draw(10, .7, .3);
      path.forEach((p, j) => { if (j % 13) return; b.beginPath(); b.moveTo(p.x - p.nx * 10, p.y - p.ny * 10); b.lineTo(p.x + p.nx * 10, p.y + p.ny * 10); b.strokeStyle = `rgba(${color},.10)`; b.lineWidth = .6; b.stroke(); });
    });
    function paint() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, W, H); ctx.drawImage(background, 0, 0);
      ctx.globalCompositeOperation = 'lighter';
      const time = clock.current;
      paths.forEach((path, i) => {
        // Dense moving clusters plus a thinner stream, constrained to each tube.
        for (let j = 0; j < 94; j++) {
          const phase = j < 68 ? Math.floor(j / 17) / 4 + (j % 17) * .0038 : j * .618034;
          const t = ((phase + time * (.073 + (j % 4) * .002) + i * .137) % 1 + 1) % 1;
          const p = path[Math.floor(t * 180)];
          const orbit = j * 2.39996 + time * 1.5;
          const spread = Math.sin(orbit) * (3 + j % 6);
          const depth = (Math.cos(orbit) + 1) / 2;
          const size = 3 + depth * 4 + (j % 13 === 0 ? 4 : 0);
          ctx.globalAlpha = .35 + depth * .6;
          ctx.drawImage(sprites[j % 11 === 0 ? 2 : i < 4 ? 0 : 1], p.x + p.nx * spread - size / 2, p.y + p.ny * spread - size / 2, size, size);
        }
      });
      for (let j = 0; j < 140; j++) {
        const a = j * 2.39996 + time * .18, radius = 60 + (j % 11) * 2.8;
        const x = CORE[0] + Math.cos(a) * radius, y = CORE[1] + Math.sin(a) * radius * .70;
        const size = 2.3 + (Math.sin(a) + 1) * 2.3;
        ctx.globalAlpha = .25 + (Math.sin(a) + 1) * .3;
        ctx.drawImage(sprites[j % 3], x - size / 2, y - size / 2, size, size);
      }
      ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
    }
    function tick(now: number) {
      if (disposed || stopped || !visible || document.hidden) { frame = 0; return; }
      if (!last || now - last >= 32) {
        clock.current += last ? Math.min(now - last, 64) / 1000 : 0;
        last = now; paint();
      }
      frame = requestAnimationFrame(tick);
    }
    function resume() { last = 0; if (!frame && !stopped && visible && !document.hidden) frame = requestAnimationFrame(tick); }
    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const width = Math.max(1, canvas!.getBoundingClientRect().width);
      canvas!.width = Math.round(width * dpr); canvas!.height = Math.round(width * H / W * dpr);
      ctx!.setTransform(canvas!.width / W, 0, 0, canvas!.height / H, 0, 0); paint();
    }
    const sizeObserver = new ResizeObserver(resize); sizeObserver.observe(canvas);
    const visibility = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; resume(); }); visibility.observe(canvas);
    document.addEventListener('visibilitychange', resume);
    resize(); resume();
    return () => { disposed = true; cancelAnimationFrame(frame); sizeObserver.disconnect(); visibility.disconnect(); document.removeEventListener('visibilitychange', resume); };
  }, [stopped]);
  return <canvas ref={ref} className="flow-canvas" aria-hidden="true" />;
}

export function LoginFlow() {
  const [paused, setPaused] = useState(false);
  const [reduced, setReduced] = useState(() => window.matchMedia('(prefers-reduced-motion: reduce)').matches);
  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);
  return <figure className="login-flow">
    <div className="flow-topline"><span>PUBLIC FILINGS</span><span>CONNECTED INTELLIGENCE</span></div>
    <div className="flow-stage">
      <ParticleTubes stopped={paused || reduced} />
      <div className="flow-core"><svg viewBox="0 0 36 36" aria-hidden="true"><path d="m18 3 14 8v15l-14 8L4 26V11z" /><path d="m9 13 9-5 9 5-9 5z M9 19l9 5 9-5 M9 25l9 5 9-5" /></svg><strong>IPO Roll<span>.</span></strong></div>
    </div>
    <figcaption><span>Illustrated data flow</span>
      <button type="button" className="flow-motion" disabled={reduced} onClick={() => setPaused(!paused)} aria-label={reduced ? 'Animation off for reduced motion' : paused ? 'Play visualization' : 'Pause visualization'}>
        {paused || reduced ? <Play size={12} /> : <Pause size={12} />}{reduced ? 'Motion off' : paused ? 'Play' : 'Pause'}
      </button>
    </figcaption>
  </figure>;
}
