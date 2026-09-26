// Original procedural illustration: public-source signals become organized research.
// No live records, remote assets, video or external rendering dependencies.
export const SCENE_WIDTH = 900, SCENE_HEIGHT = 430;
const TAU = Math.PI * 2;
type Point = { x: number; y: number };
const colors = ['#43e8cb', '#63adff', '#d5fff5'];
const noise = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };
const paths = [
  [[-50, 49], [202, 12], [242, 171], [434, 174]],
  [[-60, 207], [150, 250], [282, 205], [434, 215]],
  [[-40, 397], [183, 428], [227, 266], [434, 256]],
  [[570, 174], [687, 173], [748, 127], [960, 127]],
  [[570, 215], [697, 215], [790, 217], [960, 217]],
  [[570, 256], [687, 258], [748, 307], [960, 307]],
];
// Resample curves by distance, avoiding particle acceleration through sharp bends.
const tubes = paths.map(c => {
  const raw = Array.from({ length: 401 }, (_, i) => {
    const t = i / 400, u = 1 - t;
    return { x: u ** 3 * c[0][0] + 3 * u * u * t * c[1][0] + 3 * u * t * t * c[2][0] + t ** 3 * c[3][0],
      y: u ** 3 * c[0][1] + 3 * u * u * t * c[1][1] + 3 * u * t * t * c[2][1] + t ** 3 * c[3][1] };
  });
  const distances = [0];
  for (let i = 1; i < raw.length; i++) distances.push(distances[i - 1] + Math.hypot(raw[i].x - raw[i - 1].x, raw[i].y - raw[i - 1].y));
  let cursor = 1;
  return Array.from({ length: 221 }, (_, i) => {
    const d = i / 220 * distances[400];
    while (cursor < 400 && distances[cursor] < d) cursor++;
    const f = (d - distances[cursor - 1]) / (distances[cursor] - distances[cursor - 1]);
    return { x: raw[cursor - 1].x + (raw[cursor].x - raw[cursor - 1].x) * f,
      y: raw[cursor - 1].y + (raw[cursor].y - raw[cursor - 1].y) * f };
  });
});
function position(samples: Point[], u: number, offset: number) {
  const k = Math.min(219, Math.floor(u * 220)), f = u * 220 - k, a = samples[k], b = samples[k + 1];
  const dx = b.x - a.x, dy = b.y - a.y, length = Math.hypot(dx, dy);
  return { x: a.x + dx * f - dy / length * offset, y: a.y + dy * f + dx / length * offset };
}

export function createScenePainter(ctx: CanvasRenderingContext2D) {
  const lights = colors.map(color => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 40;
    const c = canvas.getContext('2d')!, g = c.createRadialGradient(20, 20, 0, 20, 20, 20);
    g.addColorStop(0, '#eafff7'); g.addColorStop(.08, color); g.addColorStop(.23, color + '66'); g.addColorStop(1, color + '00');
    c.fillStyle = g; c.fillRect(0, 0, 40, 40); return canvas;
  });
  const backdrop = document.createElement('canvas'); backdrop.width = 900; backdrop.height = 430;
  const bg = backdrop.getContext('2d')!;
  for (const [x, y, radius, color] of [[460, 216, 240, '33,193,170'], [722, 219, 280, '49,105,190']] as const) {
    const g = bg.createRadialGradient(x, y, 0, x, y, radius);
    g.addColorStop(0, `rgba(${color},.16)`); g.addColorStop(.5, `rgba(${color},.045)`); g.addColorStop(1, `rgba(${color},0)`);
    bg.fillStyle = g; bg.fillRect(0, 0, 900, 430);
  }
  function trace(points: Point[]) {
    ctx.beginPath(); points.forEach((p, i) => { if (i) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y); });
  }
  function dot(x: number, y: number, size: number, color: number, alpha: number) {
    ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
    ctx.drawImage(lights[color], x - size / 2, y - size / 2, size, size);
  }
  return (time: number) => {
    ctx.clearRect(0, 0, 900, 430); ctx.drawImage(backdrop, 0, 0);
    ctx.globalCompositeOperation = 'lighter';
    // Distant light and sparse source fragments resolve into the incoming tubes.
    for (let i = 0; i < 170; i++) {
      const x = (noise(i) * 910 + time * 6) % 910;
      dot(x, noise(i + 200) * 430, i % 17 ? 2 : 8, x < 500 ? 0 : 1, .12 + noise(i + 90) * .18);
    }
    tubes.forEach((samples, channel) => {
      const incoming = channel < 3, color = incoming ? 0 : 1;
      const radius = incoming ? 19 : 13;
      // Multiple fine lit surfaces imply a transparent, round conduit.
      for (const [width, alpha] of [[radius * 2.7, .025], [radius * 2, .045], [radius * 1.3, .035]]) {
        trace(samples); ctx.strokeStyle = colors[color]; ctx.lineWidth = width; ctx.globalAlpha = alpha; ctx.stroke();
      }
      for (let strand = 0; strand < 18; strand++) {
        const phase = strand / 18 * TAU;
        const filament = samples.map((_, k) => {
          const u = k / 220, taper = incoming ? .6 + .4 * (1 - u) : .8 + .2 * u;
          return position(samples, u, Math.sin(phase + u * 1.2) * radius * taper);
        });
        trace(filament); ctx.strokeStyle = colors[color]; ctx.globalAlpha = .045 + Math.max(0, Math.cos(phase)) * .065; ctx.lineWidth = .55; ctx.stroke();
        for (let j = 0; j < 57; j++) {
          const seed = channel * 1100 + strand * 57 + j;
          // Incoming swarms are irregular; outgoing packets have deliberate spacing.
          const u = (j / 57 + time * (incoming ? .060 : .082) + (incoming ? noise(seed) * .017 : strand % 3 * .002)) % 1;
          const angle = phase + u * 1.2;
          const taper = incoming ? .6 + .4 * (1 - u) : .8 + .2 * u;
          const jitter = incoming ? Math.sin(time * .6 + seed) * 2.5 * (1 - u) : 0;
          const p = position(samples, u, Math.sin(angle) * radius * taper + jitter);
          const depth = (Math.cos(angle) + 1) / 2;
          const pulse = Math.pow((Math.cos(u * TAU * 2 - time * .95 + channel) + 1) / 2, 12);
          const edgeFade = Math.min(1, u * 12, (1 - u) * 12);
          dot(p.x, p.y, 2.1 + depth * 2.5 + pulse * 5, pulse > .65 ? 2 : color,
            (.2 + depth * .35 + pulse * .45) * edgeFade);
        }
      }
      // A glass edge and a moving light capsule give each tube a readable silhouette.
      for (const side of [-1, 1]) {
        trace(samples.map((_, k) => position(samples, k / 220, side * radius * (incoming ? 1 - .4 * k / 220 : .8 + .2 * k / 220))));
        ctx.globalAlpha = side < 0 ? .3 : .1; ctx.lineWidth = .7; ctx.strokeStyle = colors[color]; ctx.stroke();
      }
      const u = (time * .11 + channel * .31) % 1, p = position(samples, u, 0);
      dot(p.x, p.y, 36, color, .65); dot(p.x, p.y, 9, 2, .8);
    });
    // The fixed processing core occludes the connections, making the flow readable.
    ctx.globalCompositeOperation = 'source-over'; ctx.globalAlpha = 1;
    const polygon = (points: number[][], fill: string | CanvasGradient, stroke: string) => {
      ctx.beginPath(); points.forEach(([x, y], i) => { if (i) ctx.lineTo(x, y); else ctx.moveTo(x, y); }); ctx.closePath();
      ctx.fillStyle = fill; ctx.fill(); ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke();
    };
    const side = ctx.createLinearGradient(580, 120, 606, 296); side.addColorStop(0, '#285773'); side.addColorStop(.5, '#102c42'); side.addColorStop(1, '#091b2b');
    polygon([[581, 134], [603, 115], [603, 278], [581, 297]], side, '#5da9cd55');
    polygon([[423, 134], [445, 115], [603, 115], [581, 134]], '#24464f', '#76dbcc66');
    const face = ctx.createLinearGradient(423, 134, 581, 297);
    face.addColorStop(0, '#1a383f'); face.addColorStop(.38, '#102730'); face.addColorStop(1, '#071720');
    ctx.beginPath(); ctx.roundRect(423, 134, 158, 163, 12); ctx.fillStyle = face; ctx.fill();
    const rim = ctx.createLinearGradient(423, 134, 581, 297);
    rim.addColorStop(0, '#b1fff0'); rim.addColorStop(.45, '#4ad5ba99'); rim.addColorStop(1, '#68afffcc');
    ctx.strokeStyle = rim; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath(); ctx.roundRect(431, 142, 142, 147, 8); ctx.strokeStyle = '#84dbc823'; ctx.lineWidth = .7; ctx.stroke();
    // Interior circuits stay behind the wordmark's quiet central area.
    ctx.strokeStyle = '#66c9cb33'; ctx.lineWidth = .65;
    for (let row = 0; row < 4; row++) {
      const y = 153 + row * 39;
      ctx.beginPath(); ctx.moveTo(432, y); ctx.lineTo(443, y); ctx.lineTo(451, y + 8); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(572, y); ctx.lineTo(561, y); ctx.lineTo(553, y + 8); ctx.stroke();
    }
    ctx.globalCompositeOperation = 'lighter';
    for (let channel = 0; channel < 3; channel++) {
      const y = 174 + channel * 41;
      dot(423, y, 22, 0, .55 + Math.sin(time * 1.1 - channel) * .15);
      dot(582, y, 20, 1, .55 + Math.sin(time * 1.1 - channel - .5) * .15);
    }
    // Scanning lights suggest processing without rotating the entire structure.
    const scan = (time * .12) % 1;
    dot(437 + scan * 130, 134, 24, 0, .7);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  };
}
