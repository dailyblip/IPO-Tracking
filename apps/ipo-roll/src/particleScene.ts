// Original procedural scene: no footage, copied assets, remote requests or live data.
export const SCENE_WIDTH = 900, SCENE_HEIGHT = 430;
type Vec = [number, number, number];
const TAU = Math.PI * 2;
const channels: Vec[][] = [
  [[-620, -205, 70], [-270, -260, 110], [-255, 25, 50], [-128, 14, 0]],
  [[-600, 55, 240], [-330, 160, 220], [-230, -15, 60], [-115, 55, 0]],
  [[-380, 320, -200], [-310, 150, -220], [-230, -75, -50], [-95, -70, -25]],
  [[116, -48, 0], [270, -100, 150], [250, -275, 280], [620, -165, 330]],
  [[124, 30, 0], [260, 60, -50], [350, -80, -180], [640, 10, -120]],
  [[90, 88, 0], [260, 160, 90], [325, 265, 100], [650, 255, 150]],
];
function cubic(c: Vec[], t: number): Vec {
  const u = 1 - t;
  return [0, 1, 2].map(k => u ** 3 * c[0][k] + 3 * u * u * t * c[1][k] + 3 * u * t * t * c[2][k] + t ** 3 * c[3][k]) as Vec;
}
const channelSamples = channels.map(c => Array.from({ length: 241 }, (_, i) => cubic(c, i / 240)));
const sphere = Array.from({ length: 1700 }, (_, i) => {
  const y = 1 - 2 * (i + .5) / 1700, r = Math.sqrt(1 - y * y), a = i * 2.399963;
  return [Math.cos(a) * r * 128, y * 128, Math.sin(a) * r * 128] as Vec;
});
const palettes = ['#72efda', '#7eb4ff', '#d0fff5'];
const glyphs = ['0', '1', 'S', '4', 'A', '·'];

export function createScenePainter(ctx: CanvasRenderingContext2D) {
  // Small cached glyph atlases supply the light bloom without costly live filters.
  const atlas = palettes.map(color => glyphs.map(glyph => {
    const image = document.createElement('canvas'); image.width = image.height = 48;
    const c = image.getContext('2d')!;
    const glow = c.createRadialGradient(24, 24, 0, 24, 24, 23);
    glow.addColorStop(0, color + '55'); glow.addColorStop(.35, color + '20'); glow.addColorStop(1, color + '00');
    c.fillStyle = glow; c.fillRect(0, 0, 48, 48);
    c.font = '500 23px monospace'; c.textAlign = 'center'; c.textBaseline = 'middle';
    c.fillStyle = color; c.fillText(glyph, 24, 25);
    return image;
  }));
  const haze = document.createElement('canvas'); haze.width = SCENE_WIDTH; haze.height = SCENE_HEIGHT;
  const h = haze.getContext('2d')!;
  for (const [x, y, color] of [[490, 214, '39,160,151'], [280, 350, '32,95,116'], [780, 130, '57,94,165']] as const) {
    const g = h.createRadialGradient(x, y, 0, x, y, 255);
    g.addColorStop(0, `rgba(${color},.16)`); g.addColorStop(.5, `rgba(${color},.045)`); g.addColorStop(1, `rgba(${color},0)`);
    h.fillStyle = g; h.fillRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT);
  }

  return (time: number) => {
    ctx.clearRect(0, 0, SCENE_WIDTH, SCENE_HEIGHT);
    ctx.drawImage(haze, 0, 0);
    const yaw = -.12 + Math.sin(time * .09) * .15, pitch = .09 + Math.cos(time * .075) * .065;
    const cy = Math.cos(yaw), sy = Math.sin(yaw), cp = Math.cos(pitch), sp = Math.sin(pitch);
    const project = (x: number, y: number, z: number) => {
      const xx = x * cy + z * sy, zz = z * cy - x * sy;
      const yy = y * cp - zz * sp, depth = zz * cp + y * sp;
      const scale = 700 / (760 + depth);
      return { x: 478 + xx * scale, y: 215 + yy * scale, scale, depth };
    };
    const mark = (x: number, y: number, z: number, size: number, color: number, glyph: number, light: number) => {
      const p = project(x, y, z), s = size * p.scale;
      if (p.x < -30 || p.x > 930 || p.y < -30 || p.y > 460) return;
      ctx.globalAlpha = Math.min(.95, light * Math.max(.22, 1 - (p.depth + 100) / 650));
      ctx.drawImage(atlas[color][glyph], p.x - s / 2, p.y - s / 2, s, s);
    };
    ctx.globalCompositeOperation = 'lighter';
    // Foreground and distant dust add parallax without competing with the text.
    for (let j = 0; j < 140; j++) {
      const x = ((j * 97.37) % 1250) - 625, y = ((j * 61.17) % 540) - 270, z = (j * 39.19) % 600 - 270;
      mark(x + Math.sin(time * .06 + j) * 8, y, z, j % 5 ? 5 : 12, 1, 5, .22);
    }
    channelSamples.forEach((samples, channel) => {
      const color = channel < 3 ? 0 : 1;
      // Twisted filament rails reveal the volume, rather than flat connector lines.
      for (let strand = 0; strand < 10; strand++) {
        ctx.beginPath();
        samples.forEach((p, k) => {
          const theta = strand / 10 * TAU + k * .022 + channel;
          const q = project(p[0], p[1] + Math.sin(theta) * 19, p[2] + Math.cos(theta) * 19);
          if (k) ctx.lineTo(q.x, q.y); else ctx.moveTo(q.x, q.y);
        });
        ctx.globalAlpha = .055; ctx.lineWidth = .6; ctx.strokeStyle = palettes[color]; ctx.stroke();
        for (let j = 0; j < 46; j++) {
          const u = (j / 46 + time * .045 + strand * .003 + channel * .16) % 1;
          const p = samples[Math.floor(u * 240)];
          const theta = strand / 10 * TAU + u * 5.28 + channel;
          // Traveling pulses illuminate contiguous bands of character streams.
          const pulse = Math.pow((Math.sin(u * 21 - time * .7 + channel) + 1) / 2, 7);
          mark(p[0], p[1] + Math.sin(theta) * 19, p[2] + Math.cos(theta) * 19,
            5 + pulse * 4, pulse > .8 ? 2 : color, (j + strand * 3) % glyphs.length, .22 + pulse * .75);
        }
      }
    });
    // The spherical shell turns independently from the slow camera orbit.
    const spin = time * .045, cs = Math.cos(spin), ss = Math.sin(spin);
    sphere.forEach(([x, y, z], i) => {
      const xx = x * cs + z * ss, zz = z * cs - x * ss;
      const wave = Math.pow((Math.sin(y * .025 + time * .75) + 1) / 2, 10);
      const band = Math.abs(y) < 12;
      mark(xx, y, zz, band ? 5 : 6.5 + wave * 2, wave > .6 ? 2 : i % 7 ? 0 : 1,
        i % glyphs.length, (zz < 0 ? .72 : .22) + wave * .22);
    });
    // Thin orbital arcs and passing light beads give a readable silhouette.
    for (let ring = 0; ring < 3; ring++) {
      ctx.beginPath();
      for (let j = 0; j <= 180; j++) {
        const a = j / 180 * TAU, r = 145 + ring * 13;
        const p = project(Math.cos(a) * r, Math.sin(a) * r * (.20 + ring * .25), Math.sin(a) * r * .8);
        if (j) ctx.lineTo(p.x, p.y); else ctx.moveTo(p.x, p.y);
      }
      ctx.globalAlpha = .14; ctx.strokeStyle = palettes[ring % 2]; ctx.lineWidth = .7; ctx.stroke();
      const a = time * (.18 + ring * .03) + ring * 2, r = 145 + ring * 13;
      mark(Math.cos(a) * r, Math.sin(a) * r * (.20 + ring * .25), Math.sin(a) * r * .8, 16, 2, 5, 1);
    }
    ctx.globalAlpha = 1; ctx.globalCompositeOperation = 'source-over';
  };
}
