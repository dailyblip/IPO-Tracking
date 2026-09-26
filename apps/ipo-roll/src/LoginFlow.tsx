import { useEffect, useRef, useState } from 'react';
import { Pause, Play } from 'lucide-react';
import { createScenePainter, SCENE_WIDTH as W, SCENE_HEIGHT as H } from './particleScene.js';

function ParticleTubes({ stopped }: { stopped: boolean }) {
  const ref = useRef<HTMLCanvasElement>(null);
  const clock = useRef(0);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return;
    let frame = 0, last = 0, visible = true, disposed = false;
    const render = createScenePainter(ctx);
    function paint() { render(clock.current); }
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
