import type { MouseEvent } from 'react';

/** Moves a card's soft highlight (its --sx/--sy) to follow the pointer. */
export function spotlight(e: MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty('--sx', `${e.clientX - r.left}px`);
  el.style.setProperty('--sy', `${e.clientY - r.top}px`);
}
