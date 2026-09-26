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
    let frame = 0, last = 0, visible = true, disposed = false, sceneHeight = H;
    const render = createScenePainter(ctx);
    function paint() { render(clock.current, sceneHeight); }
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
      const bounds = canvas!.getBoundingClientRect();
      const width = Math.max(1, bounds.width), height = Math.max(1, bounds.height);
      const dpr = Math.min(window.devicePixelRatio || 1, 2, 2400 / width);
      canvas!.width = Math.round(width * dpr); canvas!.height = Math.round(height * dpr);
      const scale = canvas!.width / W;
      sceneHeight = canvas!.height / scale;
      ctx!.setTransform(scale, 0, 0, scale, 0, 0); paint();
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
    <div className="flow-stage">
      <ParticleTubes stopped={paused || reduced} />
    </div>
    <figcaption><span>Illustrated data flow</span>
      <button type="button" className="flow-motion" disabled={reduced} onClick={() => setPaused(!paused)} aria-label={reduced ? 'Animation off for reduced motion' : paused ? 'Play visualization' : 'Pause visualization'}>
        {paused || reduced ? <Play size={12} /> : <Pause size={12} />}{reduced ? 'Motion off' : paused ? 'Play' : 'Pause'}
      </button>
    </figcaption>
  </figure>;
}
