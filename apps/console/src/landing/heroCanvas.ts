import { RGB } from '../shared/theme';

export interface Pointer {
  x: number;
  y: number;
}

/**
 * The hero's agent field: drifting dots linked by faint lines, cursor links in
 * blue, and every ten seconds a red chain of five hops forms, one link is cut,
 * and the rest heal to green. Drawing stops while the canvas is offscreen.
 * Returns a function that tears everything down.
 */
export function startHero(
  cv: HTMLCanvasElement,
  pointer: () => Pointer | null,
  motion: boolean,
): () => void {
  const ctx = cv.getContext('2d');
  if (!ctx) return () => {};

  let seed = 11;
  const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const N = 70;
  const nodes = Array.from({ length: N }, (_, i) => ({
    nx: i < 52 ? 0.34 + rnd() * 0.64 : rnd(),
    ny: 0.08 + rnd() * 0.84,
    ph: rnd() * 6.28,
    amp: 6 + rnd() * 14,
    r: 1.2 + rnd() * 1.4,
  }));

  let W = 0;
  let H = 0;
  const resize = () => {
    const r = cv.getBoundingClientRect();
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    W = r.width;
    H = r.height;
    cv.width = W * dpr;
    cv.height = H * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  };
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(cv);

  let chain: number[] = [];
  let lastCycle = -1;
  const pickChain = (k: number) => {
    const xs = [0.42, 0.55, 0.67, 0.79, 0.92];
    const used = new Set<number>();
    const yc = 0.32 + ((k * 0.37) % 1) * 0.36;
    return xs.map((x, j) => {
      let best = 0;
      let bd = 1e9;
      nodes.forEach((n, i) => {
        if (used.has(i)) return;
        const d = (n.nx - x) ** 2 + (n.ny - (yc + (j % 2 ? 0.08 : -0.06))) ** 2 * 0.6;
        if (d < bd) {
          bd = d;
          best = i;
        }
      });
      used.add(best);
      return best;
    });
  };
  const ease = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x * x * (3 - 2 * x));
  const mix = (a: number[], b: number[], t: number) =>
    a.map((v, i) => Math.round(v + (b[i] - v) * t)).join(',');
  const paths: number[][] = Array.from({ length: 6 }, () => []);
  const RED = RGB.red.split(',').map(Number);
  const GREEN = RGB.green.split(',').map(Number);

  const draw = (t: number) => {
    const s = motion ? t / 1000 : 0;
    ctx.clearRect(0, 0, W, H);
    const P = nodes.map((n) => [
      n.nx * W + Math.sin(s * 0.35 + n.ph) * n.amp,
      n.ny * H + Math.cos(s * 0.28 + n.ph) * n.amp,
    ]);
    const D = Math.max(120, Math.min(W, H) * 0.2);
    // Links fade with distance. They are grouped into a few opacity levels
    // and stroked once per level, not once per link.
    ctx.lineWidth = 1;
    const LEVELS = 6;
    const D2 = D * D;
    for (let k = 0; k < LEVELS; k++) paths[k].length = 0;
    for (let i = 0; i < N; i++)
      for (let j = i + 1; j < N; j++) {
        const dx = P[i][0] - P[j][0];
        const dy = P[i][1] - P[j][1];
        const d2 = dx * dx + dy * dy;
        if (d2 < D2) {
          const k = Math.min(LEVELS - 1, Math.floor((1 - Math.sqrt(d2) / D) * LEVELS));
          paths[k].push(i, j);
        }
      }
    for (let k = 0; k < LEVELS; k++) {
      const list = paths[k];
      if (!list.length) continue;
      ctx.strokeStyle = `rgba(${RGB.line},${((k + 0.5) / LEVELS) * 0.24})`;
      ctx.beginPath();
      for (let n = 0; n < list.length; n += 2) {
        ctx.moveTo(P[list[n]][0], P[list[n]][1]);
        ctx.lineTo(P[list[n + 1]][0], P[list[n + 1]][1]);
      }
      ctx.stroke();
    }

    const m = pointer();
    const near = new Set<number>();
    if (m)
      P.forEach((p, i) => {
        const d = Math.hypot(p[0] - m.x, p[1] - m.y);
        if (d < 190) {
          near.add(i);
          ctx.strokeStyle = `rgba(${RGB.blue},${(1 - d / 190) * 0.45})`;
          ctx.beginPath();
          ctx.moveTo(p[0], p[1]);
          ctx.lineTo(m.x, m.y);
          ctx.stroke();
        }
      });
    P.forEach((p, i) => {
      const on = near.has(i);
      ctx.fillStyle = on ? `rgba(${RGB.blue},.95)` : `rgba(${RGB.mute},.42)`;
      ctx.beginPath();
      ctx.arc(p[0], p[1], on ? nodes[i].r + 1 : nodes[i].r, 0, 6.283);
      ctx.fill();
    });

    if (!motion) return;
    const CY = 10;
    const k = Math.floor(s / CY);
    const c = s % CY;
    if (k !== lastCycle) {
      chain = pickChain(k);
      lastCycle = k;
    }
    const pts = chain.map((i) => P[i]);
    const fade = c > 8.4 ? 1 - ease((c - 8.4) / 1.2) : 1;
    const grow = ease((c - 0.8) / 2.2) * 4;
    const cut = ease((c - 4.6) / 0.9);
    const heal = ease((c - 5.4) / 1.0);
    ctx.save();
    ctx.globalAlpha = fade;
    ctx.lineCap = 'round';
    for (let g = 0; g < 4; g++) {
      const f = Math.max(0, Math.min(1, grow - g));
      if (f <= 0) continue;
      const A = pts[g];
      const B = pts[g + 1];
      const col = g === 2 || heal <= 0 ? RGB.red : mix(RED, GREEN, heal);
      ctx.strokeStyle = `rgba(${col},.95)`;
      ctx.lineWidth = 2;
      ctx.shadowColor = `rgba(${col},.4)`;
      ctx.shadowBlur = 8;
      if (g === 2 && cut > 0) {
        const M = [(A[0] + B[0]) / 2, (A[1] + B[1]) / 2];
        const r = 1 - cut;
        ctx.globalAlpha = fade * (1 - cut * 0.85);
        ctx.beginPath();
        ctx.moveTo(A[0], A[1]);
        ctx.lineTo(A[0] + (M[0] - A[0]) * r, A[1] + (M[1] - A[1]) * r);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(B[0], B[1]);
        ctx.lineTo(B[0] + (M[0] - B[0]) * r, B[1] + (M[1] - B[1]) * r);
        ctx.stroke();
        ctx.globalAlpha = fade * (1 - cut);
        ctx.shadowBlur = 0;
        ctx.strokeStyle = `rgba(${RGB.ink},.7)`;
        ctx.lineWidth = 1.5;
        ctx.beginPath();
        ctx.arc(M[0], M[1], 4 + cut * 22, 0, 6.283);
        ctx.stroke();
        ctx.globalAlpha = fade * ease((c - 5.2) / 0.6) * (c > 7.6 ? 1 - ease((c - 7.6) / 0.6) : 1);
        ctx.fillStyle = `rgb(${RGB.green})`;
        ctx.font = '500 11px "Geist Mono", ui-monospace, monospace';
        ctx.fillText('only this link was cut', M[0] + 14, M[1] - 14);
        ctx.globalAlpha = fade;
      } else {
        ctx.beginPath();
        ctx.moveTo(A[0], A[1]);
        ctx.lineTo(A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f);
        ctx.stroke();
      }
    }
    if (c > 3.0 && c < 4.6) {
      const q = ((c - 3.0) / 1.6) * 4;
      const g = Math.min(3, Math.floor(q));
      const f = q - g;
      const A = pts[g];
      const B = pts[g + 1];
      ctx.shadowBlur = 12;
      ctx.shadowColor = `rgba(${RGB.red},.6)`;
      ctx.fillStyle = `rgb(${RGB.red})`;
      ctx.beginPath();
      ctx.arc(A[0] + (B[0] - A[0]) * f, A[1] + (B[1] - A[1]) * f, 3.2, 0, 6.283);
      ctx.fill();
    }
    ctx.shadowBlur = 0;
    pts.forEach((p, i) => {
      if (grow < i - 0.2) return;
      const red = !(heal > 0 && i !== 2 && i !== 3);
      ctx.fillStyle = `rgb(${red ? RGB.red : RGB.green})`;
      ctx.beginPath();
      ctx.arc(p[0], p[1], 3.6, 0, 6.283);
      ctx.fill();
    });
    ctx.restore();
  };

  let raf = 0;
  let visible = true;
  const loop = (t: number) => {
    draw(t);
    raf = visible ? requestAnimationFrame(loop) : 0;
  };
  const io = new IntersectionObserver(([e]) => {
    visible = e.isIntersecting;
    if (visible && !raf) raf = requestAnimationFrame(loop);
  });
  io.observe(cv);
  raf = requestAnimationFrame(loop);

  return () => {
    cancelAnimationFrame(raf);
    io.disconnect();
    ro.disconnect();
  };
}
