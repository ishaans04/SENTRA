import {
  Fragment,
  useEffect,
  useRef,
  useState,
  type CSSProperties,
  type MouseEvent,
  type ReactNode,
} from 'react';

import { Brand } from '../shared/Brand';
import { useSeen, useTimers } from '../shared/hooks';
import { spotlight } from '../shared/pointer';
import { navigate } from '../shared/route';
import { BRAND, C, REPO_URL } from '../shared/theme';
import { useVoice } from '../shared/useVoice';
import {
  PIN_QUERY,
  clamp01,
  pinProgress,
  scrollToProgress,
  useMedia,
  useScrollFrame,
} from '../shared/scroll';
import { startHero, type Pointer } from './heroCanvas';
import { Ambient, ScrollProgress, SectionRail } from './ScrollChrome';
import { VoiceCardHome } from './VoiceCard';
import { WhySentra } from './WhySentra';
import './landing.css';
import './motion.css';

const PROB = [
  'Support reads customer details',
  'Support saves notes to a shared notepad',
  'Reporting reads that notepad',
  'Reporting sends a report outside',
];

const TABS = [
  [
    'Notice',
    'It sees when safe steps add up to something unsafe — and shows you exactly which ones.',
  ],
  [
    'Pause',
    'It remembers why you approved each job. When that reason stops being true, it pauses just that job.',
  ],
  ['Repair', 'It redoes the work the right way, and never overwrites a change a person made.'],
] as const;

const JOBS = [
  'Answer customer emails',
  'Sort new support tickets',
  'Update help articles',
  'Weekly partner report',
  'Summarize feedback',
  'Draft release notes',
  'Tidy old files',
  'Priya’s draft',
];

const toDemo = () => navigate('demo');
const toConsole = () => navigate('console');

function scrollToHow(e: MouseEvent) {
  e.preventDefault();
  document.getElementById('how')?.scrollIntoView({ behavior: 'smooth' });
}

/** True while the dark band sits under the given viewport line. */
function overDark(y: number) {
  const r = document.querySelector('.ld-why-panel')?.getBoundingClientRect();
  return !!r && r.top < y && r.bottom > y;
}

function Nav() {
  const ref = useRef<HTMLElement>(null);
  useScrollFrame(() => ref.current?.classList.toggle('is-dark', overDark(36)));
  return (
    <nav ref={ref} className="ld-nav">
      <Brand />
      <div className="ld-nav-links">
        <a href="#how" className="ld-nav-link hide-sm" onClick={scrollToHow}>
          How it works
        </a>
        <a
          href="#/console"
          className="ld-nav-link"
          onClick={(e) => {
            e.preventDefault();
            toConsole();
          }}
        >
          Console
        </a>
        <button type="button" className="ld-nav-cta" onClick={toDemo}>
          Try the demo
        </button>
      </div>
      <ScrollProgress />
    </nav>
  );
}

function Hero() {
  const secRef = useRef<HTMLElement>(null);
  const cvRef = useRef<HTMLCanvasElement>(null);
  const pointer = useRef<Pointer | null>(null);

  useEffect(() => {
    const cv = cvRef.current;
    if (!cv) return;
    const still = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches ?? false;
    return startHero(cv, () => pointer.current, !still);
  }, []);

  const onMove = (e: MouseEvent<HTMLElement>) => {
    const el = secRef.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const x = e.clientX - r.left;
    const y = e.clientY - r.top;
    el.style.setProperty('--mx', `${x}px`);
    el.style.setProperty('--my', `${y}px`);
    pointer.current = { x, y };
  };

  // The spaces between words are for screen readers; flex layout ignores them.
  const words = (list: string[], from: number) =>
    list.map((w, i) => (
      <Fragment key={w}>
        {i > 0 && ' '}
        <span style={{ animationDelay: `${from + i * 0.1}s` }}>{w}</span>
      </Fragment>
    ));

  return (
    <section
      ref={secRef}
      className="ld-hero"
      onMouseMove={onMove}
      onMouseLeave={() => (pointer.current = null)}
    >
      <canvas ref={cvRef} aria-hidden="true" />
      <div className="ld-hero-veil" />
      <div className="ld-hero-copy">
        <span className="ld-hero-eyebrow">FOR PEOPLE WHO WORK WITH AI AGENTS</span>
        <h1>
          <span>{words(['Stop', 'what', 'went', 'wrong.'], 0.2)}</span>{' '}
          <span className="ld-dim">{words(['Keep', 'everything', 'else.'], 0.75)}</span>
        </h1>
        <p className="ld-hero-lede">
          Each of your AI agents follows its own rules. Sometimes, together, they don’t. {BRAND}{' '}
          notices, pauses only the work that’s affected, and helps you put it right.
        </p>
        <div className="ld-hero-actions">
          <button
            type="button"
            className="btn-primary"
            style={{ height: 54, padding: '0 26px', fontSize: 16 }}
            onClick={toDemo}
          >
            Watch it happen <span style={{ fontSize: 18 }}>→</span>
          </button>
          <a
            href="#how"
            className="btn-ghost"
            style={{ height: 54, padding: '0 24px', fontSize: 16 }}
            onClick={scrollToHow}
          >
            How it works
          </a>
        </div>
      </div>
      <span className="ld-hero-hint">
        Each dot is an agent or something it uses. Move your cursor.
      </span>
    </section>
  );
}

/** Scroll progress at which each card lights, and at which the route closes. */
const PROB_AT = [0.06, 0.24, 0.42, 0.6, 0.8];

function Problem() {
  const pinned = useMedia(PIN_QUERY);
  const scene = useRef<HTMLElement>(null);
  const fill = useRef<HTMLDivElement>(null);
  const hint = useRef<HTMLSpanElement>(null);
  const [ref, seen] = useSeen<HTMLDivElement>();
  const [prob, setProb] = useState(0);
  const { after, clear } = useTimers();

  // Without room to pin, the steps play on a timer once the section is seen.
  const run = () => {
    clear();
    setProb(0);
    [1, 2, 3, 4, 5].forEach((n, i) => after(350 + i * 650 + (n === 5 ? 300 : 0), () => setProb(n)));
  };
  const runRef = useRef(run);
  runRef.current = run;
  useEffect(() => {
    if (seen && !pinned) runRef.current();
  }, [seen, pinned]);

  // Pinned, scrolling drives the steps and draws the line beneath them.
  useScrollFrame(() => {
    const s = scene.current;
    if (!pinned || !s) return;
    const p = pinProgress(s);
    const n = PROB_AT.filter((at) => p >= at).length;
    setProb((v) => (v === n ? v : n));
    if (fill.current) fill.current.style.transform = `scaleX(${clamp01(p / PROB_AT[4])})`;
    if (hint.current) hint.current.style.opacity = String(1 - clamp01(p / 0.12));
  });

  const replay = () => {
    if (pinned && scene.current) scrollToProgress(scene.current, 0);
    else run();
  };

  const red = prob >= 5;
  const lit = Math.min(prob, 4);
  return (
    <section
      id="how"
      ref={scene}
      className={pinned ? 'ld-prob-scene' : 'ld-sec'}
      style={pinned ? undefined : { gap: 56, paddingTop: 'clamp(90px,14vh,160px)' }}
    >
      <div className={pinned ? 'ld-prob-sticky' : 'ld-prob-flow'}>
        <div className="ld-prob-head">
          <div ref={ref} className={`ld-sec-head ld-reveal${seen ? ' is-seen' : ''}`}>
            <span className="ld-eyebrow">01 — THE PROBLEM</span>
            <h2 className="ld-h2">
              Every step was allowed. <span className="ld-dim">That’s the problem.</span>
            </h2>
          </div>
          {pinned && (
            <div className={`ld-prob-meter${red ? ' is-red' : ''}`} aria-hidden="true">
              <span key={lit} className="ld-prob-meter-n">
                0{lit}
              </span>
              <span className="ld-prob-meter-of">{red ? 'steps, linked' : 'of 04 steps'}</span>
            </div>
          )}
        </div>
        <div className="ld-prob-grid">
          {PROB.map((text, i) => {
            const on = prob > i;
            const newest = on && !red && prob === i + 1;
            return (
              <div
                key={text}
                className={`ld-prob-card${newest ? ' is-newest' : ''}`}
                onMouseMove={spotlight}
                style={{
                  opacity: on ? 1 : 0.15,
                  transform: on ? (newest ? 'translateY(-6px)' : 'none') : 'translateY(16px)',
                  borderColor: red ? 'oklch(0.56 0.19 30 / .5)' : on ? C.rule : C.ruleSoft,
                  boxShadow: red
                    ? '0 0 40px -14px oklch(0.56 0.19 30 / .45)'
                    : newest
                      ? '0 22px 40px -24px oklch(0.23 0.012 70 / .35)'
                      : 'none',
                }}
              >
                <span className="mono" style={{ fontSize: 13, color: C.mute }}>
                  0{i + 1}
                </span>
                <span style={{ font: '500 21px/1.3 var(--font-sans)', textWrap: 'pretty' }}>
                  {text}
                </span>
                <span
                  className="ld-chip"
                  style={{
                    color: red ? C.red : C.green,
                    background: red ? C.redBg : C.greenBg,
                  }}
                >
                  {red ? '✓ Allowed · but linked' : '✓ Allowed'}
                </span>
              </div>
            );
          })}
          <div className="ld-prob-track">
            {pinned ? (
              <div ref={fill} className={red ? 'is-red' : 'is-drawing'} />
            ) : (
              <div style={{ transform: red ? 'scaleX(1)' : 'scaleX(0)' }} />
            )}
          </div>
          {pinned && (
            <span ref={hint} className="ld-prob-hint">
              Scroll to follow the four steps ↓
            </span>
          )}
        </div>
        <div
          className="ld-prob-result"
          style={{ opacity: red ? 1 : 0, transform: red ? 'none' : 'translateY(16px)' }}
        >
          <p
            style={{
              margin: 0,
              maxWidth: 760,
              font: '500 clamp(28px,3.2vw,44px)/1.15 var(--font-display)',
              letterSpacing: '-.025em',
              textWrap: 'balance',
            }}
          >
            Put together, private customer details now have{' '}
            <span style={{ color: C.red }}>a way out.</span>
          </p>
          <div
            style={{
              display: 'flex',
              flexDirection: 'column',
              gap: 12,
              alignItems: 'flex-start',
              maxWidth: 320,
            }}
          >
            <span style={{ font: '400 16px/1.5 var(--font-sans)', color: C.mute }}>
              Nobody broke a rule. No one meant harm. Checking each agent on its own would never
              catch it.
            </span>
            <button type="button" className="ld-link-btn" onClick={replay}>
              ↺ Play it again
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}

function NoticeStage() {
  const dot = (delay: number, shape: 'agent' | 'store' | 'odd' | 'out') => (
    <span
      style={{
        width: 22,
        height: 22,
        flex: 'none',
        borderRadius: shape === 'agent' ? '50%' : shape === 'odd' ? 4 : 0,
        border: `1.5px ${shape === 'odd' ? 'dashed' : 'solid'} ${shape === 'odd' ? C.amberLine : C.line}`,
        transform: shape === 'out' ? 'rotate(45deg)' : 'none',
        background: C.card,
        animation: `toRedDot .4s ${delay}s forwards`,
      }}
    />
  );
  const link = (delay: number) => (
    <span
      style={{ flex: 1, height: 2, background: C.rule, animation: `toRed .4s ${delay}s forwards` }}
    />
  );
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: 460,
        display: 'flex',
        flexDirection: 'column',
        gap: 30,
        alignItems: 'center',
      }}
    >
      <div style={{ display: 'flex', alignItems: 'center', width: '100%' }}>
        {dot(0.3, 'agent')}
        {link(0.6)}
        {dot(0.9, 'agent')}
        {link(1.2)}
        {dot(1.5, 'odd')}
        {link(1.8)}
        {dot(2.1, 'agent')}
        {link(2.4)}
        {dot(2.7, 'out')}
      </div>
      <div
        className="mono"
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          width: '100%',
          fontSize: 11,
          color: C.mute,
        }}
      >
        <span>customer info</span>
        <span>support</span>
        <span>notepad</span>
        <span>reporting</span>
        <span>outside</span>
      </div>
      <span
        className="mono"
        style={{
          fontSize: 13,
          lineHeight: 1,
          fontWeight: 500,
          letterSpacing: '.06em',
          padding: '10px 14px',
          borderRadius: 999,
          color: C.red,
          background: C.redBg,
          border: '1px solid oklch(0.56 0.19 30 / .4)',
          animation: 'popIn .5s 3s both',
        }}
      >
        FOUND IT — HERE ARE THE 4 STEPS
      </span>
    </div>
  );
}

function PauseStage() {
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: 400,
        display: 'flex',
        flexDirection: 'column',
        gap: 18,
      }}
    >
      <div className="ld-mini-card" style={{ animation: 'up .6s both' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span style={{ font: '600 18px var(--font-sans)' }}>Weekly partner report</span>
          <span
            style={{
              width: 30,
              height: 30,
              borderRadius: '50%',
              background: C.blue,
              color: C.paper,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              font: '700 11px var(--font-sans)',
              letterSpacing: -1,
              animation: 'popIn .4s 1.7s both, ringSm 1.6s 2.1s infinite',
            }}
          >
            ❚❚
          </span>
        </div>
        <div style={{ height: 6, borderRadius: 6, background: C.ruleSoft, overflow: 'hidden' }}>
          <div
            style={{
              height: '100%',
              background: C.blue,
              borderRadius: 6,
              animation: 'fill70 1.6s cubic-bezier(.3,.6,.4,1) both',
            }}
          />
        </div>
        <span className="mono" style={{ fontSize: 13, color: C.mute }}>
          sending to partners…
        </span>
      </div>
      <span
        style={{
          alignSelf: 'center',
          font: '500 13px/1.4 var(--font-sans)',
          color: C.blue,
          textAlign: 'center',
          animation: 'up .6s 2.2s both',
        }}
      >
        Paused before it left — the reason you approved it is no longer true.
      </span>
    </div>
  );
}

function RepairStage() {
  const bars = (widths: number[], color: string) =>
    widths.map((w) => (
      <span key={w} className="ld-skel" style={{ width: `${w}%`, background: color }} />
    ));
  return (
    <div
      style={{
        position: 'relative',
        width: '100%',
        maxWidth: 440,
        display: 'grid',
        gridTemplateColumns: '1fr 1fr',
        gap: 14,
      }}
    >
      <div
        className="ld-mini-card"
        style={{ padding: 20, gap: 12, animation: 'up .5s both, fadeOut .8s 1.6s forwards' }}
      >
        <span className="mono" style={{ fontSize: 11, color: C.mute, letterSpacing: '.06em' }}>
          AI’S OLD VERSION
        </span>
        {bars([90, 70, 80], C.rule)}
      </div>
      <div
        className="ld-mini-card"
        style={{ padding: 20, gap: 12, animation: 'up .5s .2s both, toGreen .6s 1.8s forwards' }}
      >
        <span className="mono" style={{ fontSize: 11, color: C.green, letterSpacing: '.06em' }}>
          PRIYA’S EDIT
        </span>
        {bars([85, 60, 75], 'oklch(0.5 0.11 155 / .3)')}
      </div>
      <span
        style={{
          gridColumn: '1 / -1',
          justifySelf: 'center',
          font: '500 13px/1.4 var(--font-sans)',
          color: C.green,
          animation: 'up .6s 2.3s both',
        }}
      >
        Report rebuilt the right way. Her change stays.
      </span>
    </div>
  );
}

/** Tilts a panel a few degrees towards the pointer. */
function tilt(e: MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  const x = (e.clientX - r.left) / r.width - 0.5;
  const y = (e.clientY - r.top) / r.height - 0.5;
  el.style.transform = `perspective(1100px) rotateX(${-y * 4}deg) rotateY(${x * 5}deg)`;
}

function untilt(e: MouseEvent<HTMLElement>) {
  e.currentTarget.style.transform = '';
}

/**
 * Drifts its content against the scroll by `depth` (positive floats up as
 * you scroll down), with a gentle idle bob on top.
 */
function Float({
  depth,
  className,
  children,
}: {
  depth: number;
  className?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useScrollFrame(() => {
    const el = ref.current;
    if (!el) return;
    const r = el.getBoundingClientRect();
    const offset = r.top + r.height / 2 - window.innerHeight / 2;
    // Capped, so a chip drifts near its card but never across what it labels.
    const y = Math.max(-28, Math.min(28, -offset * depth));
    el.style.transform = `translate3d(0, ${y.toFixed(1)}px, 0)`;
  });
  return (
    <div ref={ref} className={className} aria-hidden="true">
      <span className="ld-bob">{children}</span>
    </div>
  );
}

const CTA_MARKERS = [
  { text: 'route closes · #12', tone: 'red', x: 9, y: 20, d: 18 },
  { text: 'HELD · H-2', tone: 'blue', x: 84, y: 16, d: -24 },
  { text: '✕ send rejected · epoch 3 < 4', tone: 'red', x: 6, y: 70, d: -14 },
  { text: 'CONFIRMED #16', tone: 'blue', x: 86, y: 64, d: 22 },
  { text: 'r-0413 ✓ delivered', tone: 'green', x: 20, y: 90, d: 12 },
  { text: 'PRESERVED · Priya’s edit', tone: 'green', x: 76, y: 88, d: -18 },
] as const;

/** Moves the closing section's floating markers with the pointer. */
function ctaMove(e: MouseEvent<HTMLElement>) {
  const el = e.currentTarget;
  const r = el.getBoundingClientRect();
  el.style.setProperty('--cx', ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
  el.style.setProperty('--cy', ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
}

/** Labels from the console's map, floating around the closing headline. */
function CtaMarkers() {
  return (
    <div className="ld-cta-markers" aria-hidden="true">
      {CTA_MARKERS.map((m, i) => (
        <span
          key={m.text}
          className={`ld-cta-marker tone-${m.tone}`}
          style={
            {
              left: `${m.x}%`,
              top: `${m.y}%`,
              '--d': m.d,
              animationDelay: `${i * 0.7}s`,
            } as CSSProperties
          }
        >
          {m.text}
        </span>
      ))}
    </div>
  );
}

function Verbs() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  const [tab, setTab] = useState(0);
  // Bumped on every click so the auto-advance timer restarts from zero.
  const [cycle, setCycle] = useState(0);

  useEffect(() => {
    if (!seen) return;
    const id = window.setInterval(() => setTab((t) => (t + 1) % 3), 5600);
    return () => window.clearInterval(id);
  }, [seen, cycle]);

  return (
    <section id="does" className="ld-band">
      <div className="ld-sec" style={{ gap: 48 }}>
        <div ref={ref} className={`ld-sec-head ld-reveal${seen ? ' is-seen' : ''}`}>
          <span className="ld-eyebrow">02 — WHAT {BRAND} DOES</span>
          <h2 className="ld-h2">Three things. Done carefully.</h2>
        </div>
        <div
          style={{
            display: 'flex',
            flexWrap: 'wrap',
            gap: 'clamp(28px,5vw,72px)',
            alignItems: 'stretch',
          }}
        >
          <div
            style={{
              flex: '1 1 340px',
              display: 'flex',
              flexDirection: 'column',
              justifyContent: 'center',
              gap: 6,
            }}
          >
            {TABS.map(([word, body], i) => {
              const on = tab === i;
              return (
                <button
                  key={word}
                  type="button"
                  className="ld-tab"
                  aria-pressed={on}
                  onClick={() => {
                    setTab(i);
                    setCycle((c) => c + 1);
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'baseline', gap: 16 }}>
                    <span className="mono" style={{ fontSize: 12, color: on ? C.blue : C.faint }}>
                      0{i + 1}
                    </span>
                    <span
                      className="ld-tab-word"
                      style={{ color: on ? C.ink : 'oklch(0.84 0.008 80)' }}
                    >
                      {word}
                    </span>
                  </span>
                  <span
                    className="ld-tab-body"
                    style={{ maxHeight: on ? 120 : 0, opacity: on ? 1 : 0 }}
                  >
                    {body}
                  </span>
                  <span className="ld-tab-bar">
                    <span
                      key={`${i}-${tab}-${cycle}`}
                      style={{ animation: on && seen ? 'fill 5.6s linear both' : 'none' }}
                    />
                  </span>
                </button>
              );
            })}
          </div>
          <div className="ld-stage" onMouseMove={tilt} onMouseLeave={untilt}>
            <div className="ld-dots-bg" />
            <span className="ld-stage-tag mono">{['NOTICE', 'PAUSE', 'REPAIR'][tab]} · LIVE</span>
            {tab === 0 && <NoticeStage key={`n${cycle}`} />}
            {tab === 1 && <PauseStage key={`p${cycle}`} />}
            {tab === 2 && <RepairStage key={`r${cycle}`} />}
          </div>
        </div>
      </div>
    </section>
  );
}

function VoiceSection() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  const voice = useVoice();
  return (
    <section id="voice" className="ld-sec">
      <div
        ref={ref}
        className={`ld-reveal${seen ? ' is-seen' : ''}`}
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: 'clamp(32px,6vw,96px)',
          alignItems: 'center',
        }}
      >
        <div
          style={{
            flex: '1 1 360px',
            display: 'flex',
            flexDirection: 'column',
            gap: 22,
            maxWidth: 520,
          }}
        >
          <span className="ld-eyebrow">03 — YOU STAY IN CHARGE</span>
          <h2 className="ld-h2">Just say it.</h2>
          <p
            style={{
              margin: 0,
              font: '400 18px/1.55 var(--font-sans)',
              color: 'var(--ink-2)',
              textWrap: 'pretty',
            }}
          >
            Talk to {BRAND} the way you’d talk to a teammate, using Wispr Flow. It repeats your
            words back as clear steps. Nothing happens until you say yes.
          </p>
        </div>
        <div className="ld-float-wrap">
          <Float depth={0.12} className="ld-float-chip chip-a">
            <span className="ld-chip-dot" style={{ background: C.blue }} /> Wispr Flow ready
          </Float>
          <Float depth={-0.08} className="ld-float-chip chip-b">
            ✓ Read back as exact steps
          </Float>
          <Float depth={0.18} className="ld-float-chip chip-c">
            Nothing runs until you say yes
          </Float>
          <VoiceCardHome voice={voice} />
        </div>
      </div>
    </section>
  );
}

function Compare() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  const [mode, setMode] = useState<'off' | 'on'>('on');
  const [comp, setComp] = useState(2);
  const { after, clear } = useTimers();

  const pick = (m: 'off' | 'on') => {
    clear();
    setMode(m);
    setComp(0);
    if (m === 'on') {
      after(1000, () => setComp(1));
      after(2400, () => setComp(2));
    }
  };

  const off = mode === 'off';
  const greenBar =
    'linear-gradient(90deg,oklch(0.5 0.11 155 / .15),oklch(0.5 0.11 155 / .7),oklch(0.5 0.11 155 / .15))';
  const blueBar =
    'linear-gradient(90deg,oklch(0.48 0.13 262 / .15),oklch(0.48 0.13 262 / .8),oklch(0.48 0.13 262 / .15))';

  return (
    <section id="difference" className="ld-band">
      <div className="ld-sec" style={{ gap: 40 }}>
        <div
          ref={ref}
          className={`ld-reveal${seen ? ' is-seen' : ''}`}
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-end',
            gap: 28,
            flexWrap: 'wrap',
          }}
        >
          <div className="ld-sec-head" style={{ maxWidth: 720 }}>
            <span className="ld-eyebrow">04 — THE DIFFERENCE</span>
            <h2 className="ld-h2">
              Pull one thread. <span className="ld-dim">Not the plug.</span>
            </h2>
          </div>
          <div className="ld-seg" role="group" aria-label="Compare responses">
            <span
              className="ld-seg-pill"
              style={{
                background: off ? C.ink : C.blue,
                transform: off ? 'translateX(0)' : 'translateX(100%)',
              }}
            />
            <button
              type="button"
              aria-pressed={off}
              style={{ color: off ? C.paper : C.mute }}
              onClick={() => pick('off')}
            >
              Shut everything down
            </button>
            <button
              type="button"
              aria-pressed={!off}
              style={{ color: off ? C.mute : C.paper }}
              onClick={() => pick('on')}
            >
              Use {BRAND}
            </button>
          </div>
        </div>
        <div className="ld-jobs">
          {JOBS.map((name, i) => {
            const isRep = i === 3;
            const isPriya = i === 7;
            let status = 'Still running';
            let color: string = C.green;
            let bar = greenBar;
            let anim = 'shimmer 2.4s linear infinite';
            let border: string = C.rule;
            let op = 1;
            let dotAnim = 'breath 1.8s infinite';
            if (off) {
              status = 'Stopped';
              color = C.faint;
              bar = `linear-gradient(${C.ruleSoft},${C.ruleSoft})`;
              anim = 'none';
              op = 0.5;
              dotAnim = 'none';
            } else if (isRep) {
              if (comp === 0) {
                status = 'Paused';
                color = C.blue;
                bar = 'linear-gradient(oklch(0.48 0.13 262 / .5),oklch(0.48 0.13 262 / .5))';
                anim = 'none';
                border = 'oklch(0.48 0.13 262 / .4)';
                dotAnim = 'none';
              } else if (comp === 1) {
                status = 'Redoing safely…';
                color = C.blue;
                bar = blueBar;
                border = 'oklch(0.48 0.13 262 / .4)';
              } else {
                status = 'Redone ✓';
                border = 'oklch(0.5 0.11 155 / .35)';
              }
            } else if (isPriya) status = 'Kept as she left it';
            return (
              <div
                key={name}
                className="ld-job"
                onMouseMove={spotlight}
                style={{
                  border: `1px solid ${border}`,
                  opacity: op,
                  transition: `all .6s ${off ? i * 0.05 : 0}s`,
                }}
              >
                <span style={{ font: '500 16px/1.3 var(--font-sans)' }}>{name}</span>
                <div className="ld-job-track">
                  <div style={{ backgroundImage: bar, animation: anim }} />
                </div>
                <span
                  className="mono"
                  style={{
                    display: 'flex',
                    alignItems: 'center',
                    gap: 8,
                    fontSize: 12,
                    fontWeight: 500,
                    letterSpacing: '.04em',
                    color,
                    transition: 'color .5s',
                  }}
                >
                  <span
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: '50%',
                      background: color,
                      animation: dotAnim,
                    }}
                  />
                  {status}
                </span>
              </div>
            );
          })}
        </div>
        <div className="ld-compare-foot">
          <p
            style={{
              margin: 0,
              font: '500 clamp(22px,2.4vw,32px)/1.3 var(--font-display)',
              letterSpacing: '-.02em',
              color: off ? C.mute : C.ink,
              transition: 'color .4s',
            }}
          >
            {off
              ? 'Everything stops. Hours of good work, interrupted.'
              : 'One report paused and redone. Everything else keeps going.'}
          </p>
          <div className={`ld-meter${off ? ' is-off' : ''}`} aria-live="polite">
            <span className="ld-meter-n">{off ? 0 : comp === 2 ? 8 : 7}</span>
            <span className="ld-meter-of">
              / 8 jobs
              <br />
              still working
            </span>
          </div>
        </div>
      </div>
    </section>
  );
}

function Honest() {
  const [ref, seen] = useSeen<HTMLElement>();
  const items = [
    [
      'A warning isn’t proof.',
      `${BRAND} says “this could leak,” not “this leaked.” It shows you exactly why.`,
    ],
    [
      'You approve the big moves.',
      'It only acts where you’ve allowed it to, and asks before changing anything important.',
    ],
    [
      'Some things can’t be undone.',
      `An email that’s already sent stays sent. ${BRAND} tells you that plainly, instead of pretending.`,
    ],
  ];
  return (
    <section
      id="honest"
      ref={ref}
      className={`ld-sec ld-reveal${seen ? ' is-seen' : ''}`}
      style={{ gap: 44 }}
    >
      <div className="ld-sec-head" style={{ maxWidth: 'none' }}>
        <span className="ld-eyebrow">06 — HONEST BY DESIGN</span>
        <h2 className="ld-h2">It tells you what it doesn’t know.</h2>
      </div>
      <div className="ld-honest">
        {items.map(([t, b]) => (
          <div key={t} onMouseMove={spotlight}>
            <span className="ld-honest-title">{t}</span>
            <span className="ld-honest-body">{b}</span>
          </div>
        ))}
      </div>
    </section>
  );
}

/** Marks each section offscreen while it is out of view (see motion.css). */
function usePauseOffscreen() {
  useEffect(() => {
    if (typeof IntersectionObserver === 'undefined') return;
    const io = new IntersectionObserver(
      (entries) =>
        entries.forEach((e) => e.target.classList.toggle('is-offscreen', !e.isIntersecting)),
      { rootMargin: '120px 0px' },
    );
    document.querySelectorAll('.ld > section').forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, []);
}

export function Landing() {
  usePauseOffscreen();
  return (
    <div className="ld">
      <Ambient />
      <Nav />
      <SectionRail />
      <Hero />
      <Problem />
      <Verbs />
      <VoiceSection />
      <Compare />
      <WhySentra />
      <Honest />
      <section id="start" className="ld-cta" onMouseMove={ctaMove}>
        <CtaMarkers />
        <h2
          style={{
            margin: 0,
            font: '600 clamp(44px,7vw,108px)/.95 var(--font-display)',
            letterSpacing: '-.045em',
            maxWidth: 1000,
            textWrap: 'balance',
          }}
        >
          See the whole story in two minutes.
        </h2>
        <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', justifyContent: 'center' }}>
          <button
            type="button"
            className="btn-primary"
            style={{ height: 60, padding: '0 32px', fontSize: 17 }}
            onClick={toDemo}
          >
            Start the demo →
          </button>
          <button
            type="button"
            className="btn-ghost"
            style={{ height: 60, padding: '0 28px', fontSize: 17 }}
            onClick={toConsole}
          >
            Open the console
          </button>
        </div>
        <span style={{ font: '400 13px var(--font-sans)', color: C.mute }}>
          No sign-up. Uses made-up data.
        </span>
      </section>
      <footer className="ld-footer">
        <span>{BRAND}</span>
        <div style={{ display: 'flex', gap: 22 }}>
          {REPO_URL && (
            <a href={REPO_URL} style={{ color: C.mute }}>
              Source on GitHub
            </a>
          )}
          <span>Built with Wispr Flow</span>
        </div>
      </footer>
    </div>
  );
}
