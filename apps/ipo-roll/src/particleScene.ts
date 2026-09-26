// Original, local procedural illustration. No live data, footage or remote assets.
export const SCENE_WIDTH = 900, SCENE_HEIGHT = 430;
const TAU = Math.PI * 2;
const colors = ['#39dcc6', '#5598ff', '#bcfff1'];
const random = (i: number) => { const x = Math.sin(i * 127.1 + 311.7) * 43758.5453; return x - Math.floor(x); };

export function createScenePainter(ctx: CanvasRenderingContext2D) {
  const sprites = colors.map(color => {
    const canvas = document.createElement('canvas'); canvas.width = canvas.height = 40;
    const c = canvas.getContext('2d')!;
    const g = c.createRadialGradient(20, 20, 0, 20, 20, 20);
    g.addColorStop(0, '#f0fffbee'); g.addColorStop(.10, color + 'ee');
    g.addColorStop(.25, color + '55'); g.addColorStop(1, color + '00');
    c.fillStyle = g; c.fillRect(0, 0, 40, 40); return canvas;
  });
  // Cache the atmosphere; animation uses bounded point/line counts.
  const atmosphere = document.createElement('canvas'); atmosphere.width = 900; atmosphere.height = 430;
  const a = atmosphere.getContext('2d')!;
  for (const [x, y, radius, color] of [[500, 210, 270, '23,176,164'], [665, 245, 240, '45,91,214'], [270, 145, 210, '14,88,111']] as const) {
    const g = a.createRadialGradient(x, y, 0, x, y, radius);
    g.addColorStop(0, `rgba(${color},.20)`); g.addColorStop(.5, `rgba(${color},.065)`); g.addColorStop(1, `rgba(${color},0)`);
    a.fillStyle = g; a.fillRect(0, 0, 900, 430);
  }
  return (time: number) => {
    ctx.clearRect(0, 0, 900, 430); ctx.drawImage(atmosphere, 0, 0);
    const tilt = -.24 + Math.sin(time * .08) * .035, ct = Math.cos(tilt), st = Math.sin(tilt);
    // Tilted optical plane supplies depth without moving the interface or text.
    const project = (x: number, y: number, z = 0) => {
      const depth = y * .65 + z * .3, scale = 760 / (800 + depth);
      const px = x * scale, py = (y * .52 - z) * scale;
      return { x: 520 + px * ct - py * st, y: 218 + px * st + py * ct, scale };
    };
    const dot = (x: number, y: number, size: number, color: number, alpha: number) => {
      if (x < -20 || x > 920 || y < -20 || y > 450) return;
      ctx.globalAlpha = Math.max(0, Math.min(1, alpha));
      ctx.drawImage(sprites[color], x - size / 2, y - size / 2, size, size);
    };
    ctx.globalCompositeOperation = 'lighter';
    for (let i = 0; i < 160; i++) {
      const x = random(i) * 900, y = random(i + 301) * 430;
      dot(x + Math.sin(time * .12 + i) * 6, y, i % 13 ? 2 : 8, i % 2, .12 + random(i + 91) * .23);
    }
    // Broad spiral currents tighten into the central lens.
    const ribbon = (u: number, lane: number, arm: number) => {
      const radius = 161 + 420 * u * u;
      const angle = arm * Math.PI + u * 3.45 + .25;
      const r = radius + lane * (4 + 15 * u);
      return project(Math.cos(angle) * r, Math.sin(angle) * r,
        Math.sin(u * 7 + arm * Math.PI) * 13 * u + lane * 2);
    };
    for (let arm = 0; arm < 2; arm++) {
      for (let lane = -9; lane <= 9; lane++) {
        ctx.beginPath();
        for (let k = 0; k <= 110; k++) {
          const p = ribbon(k / 110, lane / 3, arm);
          if (k) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
        }
        ctx.strokeStyle = colors[arm]; ctx.globalAlpha = .14; ctx.lineWidth = .65; ctx.stroke();
        for (let j = 0; j < 82; j++) {
          const u = (j / 82 - time * .026 + lane * .0017 + 1000) % 1;
          const p = ribbon(u, lane / 3, arm);
          const pulse = Math.pow((Math.cos(u * 25 + time * 1.2 + arm) + 1) / 2, 14);
          const fade = Math.min(1, (1 - u) * 5);
          dot(p.x, p.y, (3.4 + pulse * 6) * p.scale, pulse > .7 ? 2 : arm, (.5 + pulse * .5) * fade);
        }
      }
    }
    // Dense elliptical light lattice and brighter near-side layers frame a dark eye.
    for (let layer = 0; layer < 24; layer++) {
      const radius = 155 + layer * 2.7;
      ctx.beginPath();
      for (let j = 0; j <= 132; j++) {
        const theta = j / 132 * TAU;
        const p = project(Math.cos(theta) * radius, Math.sin(theta) * radius, Math.sin(layer / 24 * Math.PI) * 23);
        if (j) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
      }
      ctx.strokeStyle = colors[layer % 3 === 0 ? 1 : 0];
      ctx.globalAlpha = .08; ctx.lineWidth = .65; ctx.stroke();
      for (let j = 0; j < 132; j++) {
        const theta = j / 132 * TAU + time * (.10 + layer * .0005) + layer * .031;
        const p = project(Math.cos(theta) * radius, Math.sin(theta) * radius, Math.sin(layer / 24 * Math.PI) * 23);
        const bright = Math.pow((Math.sin(theta - time * .23) + 1) / 2, 8);
        const edge = Math.sin(layer / 24 * Math.PI);
        dot(p.x, p.y, (3.3 + bright * 4.6) * p.scale, j % 9 ? (Math.cos(theta) > 0 ? 1 : 0) : 2,
          .3 + edge * .3 + bright * .4);
      }
    }
    // Continuous inner rim keeps the silhouette readable at phone scale.
    for (let layer = 0; layer < 3; layer++) {
      ctx.beginPath();
      for (let j = 0; j <= 160; j++) {
        const theta = j / 160 * TAU, p = project(Math.cos(theta) * (150 + layer * 3), Math.sin(theta) * (150 + layer * 3));
        if (j) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
      }
      ctx.strokeStyle = layer === 0 ? '#b8fff1' : '#49dfd2';
      ctx.globalAlpha = layer === 0 ? .7 : .22; ctx.lineWidth = layer === 0 ? 1.15 : .7; ctx.stroke();
    }
    // Restrained traveling anamorphic flare; no flashes or sudden brightness changes.
    const angle = time * .16 + 2.1, flare = project(Math.cos(angle) * 157, Math.sin(angle) * 157, 5);
    dot(flare.x, flare.y, 48, 0, .85); dot(flare.x, flare.y, 13, 2, 1);
    const beam = ctx.createLinearGradient(flare.x - 135, 0, flare.x + 135, 0);
    beam.addColorStop(0, '#52e6da00'); beam.addColorStop(.5, '#b9fff0bb'); beam.addColorStop(1, '#5299ff00');
    ctx.globalAlpha = .55; ctx.fillStyle = beam; ctx.fillRect(flare.x - 135, flare.y, 270, .7);
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  };
}
