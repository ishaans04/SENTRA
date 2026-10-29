import { useRef, useState } from 'react';

import { clamp01, useScrollFrame } from '../shared/scroll';

const SECTIONS = [
  { id: 'how', label: 'The problem' },
  { id: 'does', label: 'What it does' },
  { id: 'voice', label: 'Just say it' },
  { id: 'difference', label: 'The difference' },
  { id: 'why', label: 'Why not an LLM' },
  { id: 'honest', label: 'Honest by design' },
] as const;

/** A hairline under the nav that fills as you read down the page. */
export function ScrollProgress() {
  const bar = useRef<HTMLDivElement>(null);
  useScrollFrame(() => {
    const el = bar.current;
    if (!el) return;
    const max = document.documentElement.scrollHeight - window.innerHeight;
    el.style.transform = `scaleX(${max > 0 ? clamp01(window.scrollY / max) : 0})`;
  });
  return (
    <div className="ld-progress" aria-hidden="true">
      <div ref={bar} />
    </div>
  );
}

/**
 * Soft colour fields behind the content, so long stretches of paper never
 * read as blank. They drift with scroll and stay out of the hero.
 */
export function Ambient() {
  const root = useRef<HTMLDivElement>(null);
  useScrollFrame(() => {
    const el = root.current;
    if (!el) return;
    const y = window.scrollY;
    const vh = window.innerHeight;
    el.style.opacity = String(clamp01((y - vh * 0.45) / (vh * 0.5)));
    const blobs = el.children;
    for (let i = 0; i < blobs.length; i++) {
      const b = blobs[i] as HTMLElement;
      const dy = Math.sin(y / 900 + i * 2.1) * 120;
      const dx = Math.cos(y / 1300 + i * 1.3) * 60;
      b.style.transform = `translate3d(${dx}px, ${dy}px, 0)`;
    }
  });
  return (
    <div ref={root} className="ld-ambient" aria-hidden="true">
      <span className="blob-blue" />
      <span className="blob-amber" />
      <span className="blob-green" />
    </div>
  );
}

/** Floating section index on wide screens; click a label to jump there. */
export function SectionRail() {
  const [active, setActive] = useState(-1);
  const [shown, setShown] = useState(false);
  const [dark, setDark] = useState(false);
  useScrollFrame(() => {
    const vh = window.innerHeight;
    const band = document.querySelector('.ld-why-panel')?.getBoundingClientRect();
    const over = !!band && band.top < vh / 2 && band.bottom > vh / 2;
    setDark((d) => (d === over ? d : over));
    let idx = -1;
    SECTIONS.forEach((s, i) => {
      const el = document.getElementById(s.id);
      if (el && el.getBoundingClientRect().top <= vh * 0.45) idx = i;
    });
    const cta = document.getElementById('start');
    const pastCta = !!cta && cta.getBoundingClientRect().top < vh * 0.6;
    const show = window.scrollY > vh * 0.7 && !pastCta;
    setActive((a) => (a === idx ? a : idx));
    setShown((s) => (s === show ? s : show));
  });
  return (
    <nav
      className={`ld-rail${shown ? ' is-shown' : ''}${dark ? ' is-dark' : ''}`}
      aria-label="Sections"
    >
      {SECTIONS.map((s, i) => (
        <a
          key={s.id}
          href={`#${s.id}`}
          className={i === active ? 'is-active' : i < active ? 'is-past' : ''}
          aria-current={i === active ? 'true' : undefined}
          onClick={(e) => {
            e.preventDefault();
            document.getElementById(s.id)?.scrollIntoView({ behavior: 'smooth' });
          }}
        >
          <span className="ld-rail-label">{s.label}</span>
          <span className="ld-rail-dot" />
        </a>
      ))}
    </nav>
  );
}
