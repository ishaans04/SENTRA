import { useEffect, useRef, useState } from 'react';

/**
 * One scroll/resize listener for the whole page, throttled to one call per
 * animation frame. Scroll effects subscribe here and write styles directly,
 * so scrolling never re-renders React unless a component asks it to.
 */
type Frame = () => void;
const frames = new Set<Frame>();
let queued = false;

function run() {
  queued = false;
  frames.forEach((f) => f());
}

function schedule() {
  if (queued) return;
  queued = true;
  requestAnimationFrame(run);
}

export function onScrollFrame(f: Frame): () => void {
  if (frames.size === 0) {
    window.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule, { passive: true });
  }
  frames.add(f);
  f();
  return () => {
    frames.delete(f);
    if (frames.size === 0) {
      window.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
    }
  };
}

/** Calls f on every scroll frame while the component is mounted. */
export function useScrollFrame(f: Frame): void {
  const ref = useRef(f);
  useEffect(() => {
    ref.current = f;
  });
  useEffect(() => onScrollFrame(() => ref.current()), []);
}

export const clamp01 = (x: number) => (x < 0 ? 0 : x > 1 ? 1 : x);

/**
 * How far a tall, pinned section has been scrolled through: 0 when its top
 * reaches the top of the viewport, 1 when its bottom reaches the bottom.
 */
export function pinProgress(el: Element): number {
  const r = el.getBoundingClientRect();
  const travel = r.height - window.innerHeight;
  return travel <= 0 ? (r.top <= 0 ? 1 : 0) : clamp01(-r.top / travel);
}

/** Scrolls the window so a pinned section sits at progress p. */
export function scrollToProgress(el: HTMLElement, p: number): void {
  const top = el.getBoundingClientRect().top + window.scrollY;
  const travel = el.offsetHeight - window.innerHeight;
  window.scrollTo({ top: top + Math.max(0, travel) * p, behavior: 'smooth' });
}

export function useMedia(query: string): boolean {
  const get = () => typeof window !== 'undefined' && !!window.matchMedia?.(query).matches;
  const [on, setOn] = useState(get);
  useEffect(() => {
    const mq = window.matchMedia?.(query);
    if (!mq) return;
    const fn = () => setOn(mq.matches);
    fn();
    mq.addEventListener('change', fn);
    return () => mq.removeEventListener('change', fn);
  }, [query]);
  return on;
}

/** Pinned scroll scenes need room: a wide, tall viewport and motion allowed. */
export const PIN_QUERY =
  '(min-width: 900px) and (min-height: 680px) and (prefers-reduced-motion: no-preference)';
