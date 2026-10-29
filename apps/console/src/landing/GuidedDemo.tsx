import { memo, useCallback, useEffect, useRef, useState, type ReactNode } from 'react';

import { Brand } from '../shared/Brand';
import { useTimers } from '../shared/hooks';
import { navigate } from '../shared/route';
import { BRAND, C } from '../shared/theme';
import { useVoice } from '../shared/useVoice';
import { VoiceCardDemo } from './VoiceCard';
import './landing.css';

const STEPS = [
  [
    'Meet the team',
    'Two AI agents share the work. Support helps customers. Reporting sends a weekly report to partners. You approved that on one condition.',
  ],
  [
    'Something new shows up',
    'Support starts saving notes to a shared notepad. That’s allowed. Nobody planned for it, though.',
  ],
  [
    'The pieces line up',
    'Reporting reads the notepad too. Private customer details now have a possible way out — through four steps that were each allowed.',
  ],
  [
    'The reason is gone',
    `You approved Reporting because it only read approved summaries. That’s no longer true, and a report is about to go out. So ${BRAND} pauses it.`,
  ],
  [
    `Tell ${BRAND} what to do`,
    `Speak normally with Wispr Flow, or just tap the mic here. ${BRAND} repeats it back as clear steps. Nothing happens until you say yes.`,
  ],
  [
    'Fixing only what’s broken',
    'One small change at a time. Everything that wasn’t affected keeps working.',
  ],
  [
    'All clear',
    'The leak path is closed. A fresh report went out safely. Support never stopped working.',
  ],
] as const;

const FIX = [
  ['Stopped the old report', 'It had already read the notepad, so it can’t be trusted.'],
  ['Cut its access to the notepad', 'Only that one link. Support can still use its notes.'],
  ['Blocked a late send', 'The old report tried to send anyway. It was turned away.'],
  ['Rebuilt the report from approved summaries', 'A fresh start, with only the safe information.'],
  [
    'Kept Priya’s edit',
    'She changed the draft after the AI did. Her version stays — she’s asked to review.',
  ],
] as const;

type NodeId = 'cust' | 'support' | 'summ' | 'notepad' | 'report' | 'out';
type Shape = 'store' | 'agent' | 'odd' | 'out';

const DN: Record<
  NodeId,
  { name: string; note: string; x: number; y: number; g: Shape; about: string }
> = {
  cust: {
    name: 'Customer info',
    note: 'Private',
    x: 110,
    y: 120,
    g: 'store',
    about: 'Private customer details. Only the Support agent is meant to read this.',
  },
  support: {
    name: 'Support agent',
    note: 'Helps customers',
    x: 360,
    y: 120,
    g: 'agent',
    about: 'Answers customers. Allowed to read customer info and write cleaned-up summaries.',
  },
  summ: {
    name: 'Approved summaries',
    note: 'Safe to share',
    x: 640,
    y: 120,
    g: 'store',
    about: 'Cleaned-up summaries. The only place Reporting is supposed to read from.',
  },
  notepad: {
    name: 'Shared notepad',
    note: 'Not in the plan',
    x: 470,
    y: 420,
    g: 'odd',
    about: 'A scratch space Support started using. Nobody planned for it.',
  },
  report: {
    name: 'Reporting agent',
    note: 'Sends weekly reports',
    x: 860,
    y: 280,
    g: 'agent',
    about:
      'Builds and sends the weekly report. You approved it because it only reads approved summaries.',
  },
  out: {
    name: 'Outside world',
    note: 'Partners, email, web',
    x: 860,
    y: 490,
    g: 'out',
    about: 'Anywhere outside your company. Once something is sent, it can’t be unsent.',
  },
};
const IDS = Object.keys(DN) as NodeId[];

const DE: [string, NodeId, NodeId][] = [
  ['a', 'cust', 'support'],
  ['b', 'support', 'summ'],
  ['c', 'summ', 'report'],
  ['d', 'report', 'out'],
  ['e', 'support', 'notepad'],
  ['f', 'notepad', 'report'],
];

const dPath = (a: NodeId, b: NodeId) => {
  const A = DN[a];
  const B = DN[b];
  if (A.y === B.y) return `M${A.x} ${A.y} L${B.x} ${B.y}`;
  const m = (A.y + B.y) / 2;
  return `M${A.x} ${A.y} C${A.x} ${m}, ${B.x} ${m}, ${B.x} ${B.y}`;
};
const mid = (a: NodeId, b: NodeId) => [(DN[a].x + DN[b].x) / 2, (DN[a].y + DN[b].y) / 2];

const EDGE = 'oklch(0.80 0.008 80)';
const PACKET = 'oklch(0.70 0.01 75)';

const isRisk = (st: number, sub: number) => st >= 3 && (st < 6 || (st === 6 && sub < 2));

function Edges({ st, sub }: { st: number; sub: number }) {
  const out: ReactNode[] = [];
  const risk = isRisk(st, sub);
  const cutF = (st === 6 && sub >= 2) || st === 7;
  const fresh = (st === 6 && sub >= 4) || st === 7;
  const paused = st >= 4 && st < 7;
  const packets = (key: string, d: string, color: string, n: number, dur: number) => {
    for (let i = 0; i < n; i++)
      out.push(
        <circle key={key + i} r={3.6} fill={color}>
          <animateMotion
            dur={`${dur}s`}
            repeatCount="indefinite"
            path={d}
            begin={`${(-i * dur) / n}s`}
          />
        </circle>,
      );
  };
  const halo = (id: string, color: string, opacity: number) => {
    const e = DE.find((x) => x[0] === id)!;
    out.push(
      <path
        key={id + 'h'}
        d={dPath(e[1], e[2])}
        fill="none"
        stroke={color}
        strokeOpacity={opacity}
        strokeWidth={14}
        strokeLinecap="round"
      />,
    );
  };
  if (risk) ['a', 'e', 'f', 'd'].forEach((id) => halo(id, C.red, 0.12));
  if (fresh) halo('c', C.green, 0.12);

  DE.forEach(([id, a, b]) => {
    if (id === 'e' && st < 2) return;
    if (id === 'f' && st < 3) return;
    const d = dPath(a, b);
    let stroke: string = EDGE;
    let w = 1.5;
    let dash: string | undefined;
    let n = 2;
    let pc: string = PACKET;
    let march = false;
    let dur = 3.4;
    if (id === 'e' || id === 'f') {
      stroke = C.amberLine;
      dash = '5 6';
      pc = C.amberLine;
      dur = 2.6;
    }
    if (risk && ['a', 'e', 'f', 'd'].includes(id)) {
      stroke = C.red;
      w = 2;
      march = true;
      pc = C.red;
      n = 3;
    }
    if (id === 'd' && (paused || st === 3)) n = 0;
    if (id === 'f' && cutF) {
      stroke = EDGE;
      dash = '2 7';
      n = 0;
      march = false;
      w = 1.5;
    }
    if (id === 'e' && st >= 6 && !risk) {
      stroke = 'oklch(0.74 0.14 75 / .5)';
      pc = 'oklch(0.74 0.14 75 / .6)';
      n = 1;
    }
    if (id === 'c' && fresh) {
      stroke = C.green;
      w = 2;
      pc = C.green;
      n = 3;
    }
    if (id === 'c' && st === 3) n = 0;
    if (id === 'd' && st === 7) {
      stroke = C.green;
      w = 2;
      pc = C.green;
      n = 3;
    }
    out.push(
      <path
        key={id}
        d={d}
        fill="none"
        stroke={stroke}
        strokeWidth={w}
        strokeDasharray={march ? '8 8' : dash}
        strokeLinecap="round"
        style={march ? { animation: 'march .6s linear infinite' } : { transition: 'stroke .6s' }}
      />,
    );
    if (n) packets(id + 'p', d, pc, n, dur);
  });
  if (cutF) {
    const [x, y] = mid('notepad', 'report');
    out.push(
      <g
        key="x"
        stroke={C.ink}
        strokeWidth={2}
        strokeLinecap="round"
        style={{ transformOrigin: `${x}px ${y}px`, animation: 'popIn .4s both' }}
      >
        <line x1={x - 9} y1={y - 9} x2={x + 9} y2={y + 9} />
        <line x1={x - 9} y1={y + 9} x2={x + 9} y2={y - 9} />
      </g>,
    );
  }
  return (
    <svg
      viewBox="0 0 1000 580"
      style={{
        position: 'absolute',
        inset: 0,
        width: '100%',
        height: '100%',
        zIndex: 2,
        overflow: 'visible',
      }}
      aria-hidden="true"
    >
      {out}
    </svg>
  );
}

const MARK_TONE = {
  amber: [C.amber, C.amberBg, 'oklch(0.74 0.14 75 / .5)'],
  red: [C.red, C.redBg, 'oklch(0.56 0.19 30 / .45)'],
  blue: [C.blue, C.blueBg, 'oklch(0.48 0.13 262 / .4)'],
  ink: [C.ink, C.card, C.rule],
  green: [C.green, C.greenBg, 'oklch(0.5 0.11 155 / .4)'],
} as const;

const DemoMap = memo(function DemoMap({
  st,
  sub,
  sel,
  onSelect,
}: {
  st: number;
  sub: number;
  sel: NodeId | null;
  onSelect: (id: NodeId | null) => void;
}) {
  const risk = isRisk(st, sub);
  const marks: { pt: number[]; text: string; tone: keyof typeof MARK_TONE; anim?: string }[] = [];
  const mE = mid('support', 'notepad');
  const mF = mid('notepad', 'report');
  const mD = mid('report', 'out');
  const mC = mid('summ', 'report');
  if (st === 2) marks.push({ pt: [mE[0] - 70, mE[1]], text: 'New connection', tone: 'amber' });
  if (st >= 3 && st <= 5)
    marks.push({ pt: [mF[0] - 30, mF[1] + 38], text: 'Possible leak path', tone: 'red' });
  if (st === 4 || st === 5 || (st === 6 && sub < 1))
    marks.push({ pt: [mD[0] + 72, mD[1] + 4], text: '❚❚  Paused', tone: 'blue' });
  if (st === 6 && sub >= 2)
    marks.push({ pt: [mF[0], mF[1] + 30], text: 'Access cut', tone: 'ink' });
  if (st === 6 && sub === 3)
    marks.push({
      pt: [mD[0] + 90, mD[1] + 4],
      text: 'Late send blocked',
      tone: 'red',
      anim: 'pop .3s both, shake .5s .3s',
    });
  if (st === 6 && sub === 4)
    marks.push({ pt: [mC[0] - 40, mC[1] - 30], text: 'Fresh start from safe data', tone: 'green' });

  return (
    <div className="gd-map">
      <div className="gd-map-dots" />
      <Edges st={st} sub={sub} />
      {marks.map((m) => {
        const [color, bg, border] = MARK_TONE[m.tone];
        return (
          <span
            key={m.text}
            className="gd-mark"
            style={{
              left: `${m.pt[0] / 10}%`,
              top: `${m.pt[1] / 5.8}%`,
              color,
              background: bg,
              border: `1px solid ${border}`,
              animation: m.anim ?? 'pop .45s both',
            }}
          >
            {m.text}
          </span>
        );
      })}
      {IDS.map((id) => {
        const n = DN[id];
        let color: string = C.mute;
        let note = n.note;
        let noteColor: string = C.mute;
        let glow = 'none';
        let fill: string = C.card;
        if (id === 'notepad') {
          color = C.amberLine;
          noteColor = C.amber;
        }
        if (risk && ['cust', 'support', 'notepad', 'report', 'out'].includes(id)) {
          color = C.red;
          glow = '0 0 0 6px oklch(0.56 0.19 30 / .1), 0 0 24px oklch(0.56 0.19 30 / .22)';
          fill = C.redBg;
        }
        if (id === 'report') {
          if (st === 4 || st === 5 || (st === 6 && sub < 1)) {
            note = 'Report paused';
            noteColor = C.blue;
            color = risk ? C.red : C.blue;
          }
          if (st === 6 && sub >= 1 && sub < 4) {
            note = 'Old report stopped';
            noteColor = C.ink;
            color = C.mute;
            glow = 'none';
            fill = C.card;
          }
          if ((st === 6 && sub >= 4) || st === 7) {
            note = st === 7 ? 'New report sent safely' : 'Building a new report';
            noteColor = C.green;
            color = C.green;
            glow = '0 0 24px oklch(0.5 0.11 155 / .22)';
            fill = C.greenBg;
          }
        }
        if (id === 'notepad' && ((st === 6 && sub >= 2) || st === 7)) {
          note = 'Reporting can’t read it now';
          color = 'oklch(0.74 0.14 75 / .6)';
          glow = 'none';
          fill = C.card;
        }
        if (id === 'summ' && ((st === 6 && sub >= 5) || st === 7)) {
          note = 'Priya’s edit kept';
          noteColor = C.green;
          color = C.green;
          glow = '0 0 20px oklch(0.5 0.11 155 / .2)';
        }
        if (id === 'support' && st === 7) {
          note = 'Never stopped';
          noteColor = C.green;
        }
        if (id === 'out' && st === 7) color = C.green;
        if (sel === id)
          glow = glow === 'none' ? `0 0 0 2px ${C.ink}` : `${glow}, 0 0 0 2px ${C.ink}`;
        const radius = n.g === 'agent' ? '50%' : '12px';
        return (
          <button
            key={id}
            type="button"
            className="gd-node"
            aria-label={`${n.name}: ${note}`}
            onClick={() => onSelect(sel === id ? null : id)}
            style={{
              left: `${n.x / 10}%`,
              top: `${n.y / 5.8}%`,
              opacity: id === 'notepad' && st < 2 ? 0 : 1,
            }}
          >
            <span
              className="gd-node-shape"
              style={{
                borderRadius: radius,
                border: `1.5px ${n.g === 'odd' ? 'dashed' : 'solid'} ${color}`,
                background: fill,
                boxShadow: glow,
                transform: n.g === 'out' ? 'rotate(45deg)' : 'none',
              }}
            >
              <span style={{ borderRadius: radius, background: color }} />
            </span>
            <span
              style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3 }}
            >
              <span className="gd-node-name">{n.name}</span>
              <span className="gd-node-note" style={{ color: noteColor }}>
                {note}
              </span>
            </span>
          </button>
        );
      })}
      {sel && (
        <div className="gd-about">
          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              gap: 12,
              alignItems: 'baseline',
            }}
          >
            <span style={{ font: '600 15px var(--font-sans)' }}>{DN[sel].name}</span>
            <button
              type="button"
              aria-label="Close"
              onClick={() => onSelect(null)}
              style={{
                border: 0,
                background: 'transparent',
                color: C.mute,
                cursor: 'pointer',
                font: '500 13px var(--font-sans)',
              }}
            >
              ✕
            </button>
          </div>
          <span style={{ font: '400 14px/1.5 var(--font-sans)', color: 'var(--ink-2)' }}>
            {DN[sel].about}
          </span>
        </div>
      )}
    </div>
  );
});

export function GuidedDemo() {
  const [step, setStep] = useState(1);
  const [sub, setSub] = useState(0);
  const [sel, setSel] = useState<NodeId | null>(null);
  const { after, clear } = useTimers();
  const stepRef = useRef(step);
  stepRef.current = step;

  const goStepRef = useRef<(n: number) => void>(() => {});
  const voice = useVoice(
    useCallback(() => {
      if (stepRef.current === 5) goStepRef.current(6);
    }, []),
  );

  const goStep = (raw: number) => {
    const n = Math.max(1, Math.min(7, raw));
    clear();
    setStep(n);
    setSub(n > 6 ? 5 : 0);
    setSel(null);
    if (n <= 5) voice.reset();
    else voice.finish();
    if (n === 6) [1, 2, 3, 4, 5].forEach((i) => after(500 + (i - 1) * 1400, () => setSub(i)));
  };
  goStepRef.current = goStep;

  const next = () => {
    if (step === 5) {
      if (voice.phase === 'typed') voice.confirm();
      else if (voice.phase === 'idle') voice.start();
      return;
    }
    if (step === 6 && sub < 5) return;
    if (step < 7) goStep(step + 1);
  };
  const keyNext = useRef(next);
  keyNext.current = next;

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight') keyNext.current();
      else if (e.key === 'ArrowLeft') goStepRef.current(stepRef.current - 1);
      else if (e.key === 'Escape') navigate('home');
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  const st = step;
  const [title, body] = STEPS[st - 1];
  const nextOff = (st === 6 && sub < 5) || st === 7;
  const nextLabel =
    st === 5
      ? voice.phase === 'idle'
        ? 'Speak →'
        : voice.phase === 'typed'
          ? 'Yes, do it →'
          : 'Listening…'
      : st === 6
        ? sub < 5
          ? 'Working…'
          : 'See the result →'
        : 'Next →';
  const noLonger = st >= 4 && st <= 5;

  return (
    <div className="gd">
      <header className="gd-head">
        <button
          type="button"
          onClick={() => navigate('home')}
          style={{ border: 0, background: 'transparent', cursor: 'pointer', padding: 0 }}
          aria-label={`${BRAND} home`}
        >
          <Brand />
        </button>
        <div style={{ flex: 1, maxWidth: 520, display: 'flex', gap: 6 }}>
          {STEPS.map(([t], i) => (
            <button
              key={t}
              type="button"
              title={t}
              aria-label={`Step ${i + 1}: ${t}`}
              onClick={() => goStep(i + 1)}
              style={{
                flex: 1,
                height: 22,
                border: 0,
                padding: 0,
                background: 'transparent',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
              }}
            >
              <span
                style={{
                  display: 'block',
                  width: '100%',
                  height: 3,
                  borderRadius: 3,
                  background:
                    i + 1 < st ? 'oklch(0.48 0.13 262 / .45)' : i + 1 === st ? C.blue : C.rule,
                  transition: 'background .5s',
                }}
              />
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 14 }}>
          <span
            className="mono hide-sm"
            style={{ fontSize: 11, color: C.mute, letterSpacing: '.06em' }}
          >
            MADE-UP DATA
          </span>
          <button
            type="button"
            className="btn-ghost"
            style={{ height: 34, padding: '0 14px', fontSize: 13, whiteSpace: 'nowrap' }}
            onClick={() => navigate('home')}
          >
            Exit demo
          </button>
        </div>
      </header>

      <div className="gd-body">
        <div
          style={{
            flex: '1 1 440px',
            minWidth: 0,
            position: 'relative',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
          }}
        >
          <DemoMap st={st} sub={sub} sel={sel} onSelect={setSel} />
          <span
            style={{
              display: 'block',
              alignSelf: 'flex-start',
              font: '400 12px var(--font-sans)',
              color: C.mute,
            }}
          >
            Tip: click anything on the map to learn what it is.
          </span>
        </div>

        <div className="gd-panel">
          <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }} key={st}>
            <span
              className="mono"
              style={{
                fontSize: 12,
                lineHeight: 1,
                fontWeight: 500,
                letterSpacing: '.14em',
                color: C.blue,
              }}
            >
              STEP 0{st} OF 07
            </span>
            <h2
              style={{
                margin: 0,
                font: '600 clamp(32px,3.2vw,46px)/1.02 var(--font-display)',
                letterSpacing: '-.035em',
                textWrap: 'balance',
              }}
            >
              {title}
            </h2>
            <p
              style={{
                margin: 0,
                font: '400 17px/1.55 var(--font-sans)',
                color: 'var(--ink-2)',
                textWrap: 'pretty',
              }}
            >
              {body}
            </p>
          </div>

          {(st === 1 || st === 4) && (
            <div
              className="gd-card"
              style={{
                borderColor: noLonger ? 'oklch(0.56 0.19 30 / .4)' : C.rule,
                transition: 'border-color .5s',
                animation: 'up .5s both',
              }}
            >
              <div
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  gap: 10,
                }}
              >
                <span
                  className="mono"
                  style={{ fontSize: 11, letterSpacing: '.1em', color: C.mute }}
                >
                  YOUR APPROVAL
                </span>
                <span
                  className="mono"
                  style={{
                    fontSize: 11,
                    lineHeight: 1,
                    fontWeight: 500,
                    letterSpacing: '.06em',
                    padding: '6px 9px',
                    borderRadius: 999,
                    color: noLonger ? C.red : C.blue,
                    background: noLonger ? C.redBg : C.blueBg,
                    transition: 'all .5s',
                  }}
                >
                  {noLonger ? 'NO LONGER TRUE' : 'APPROVED'}
                </span>
              </div>
              <span
                style={{
                  font: '500 19px/1.4 var(--font-display)',
                  letterSpacing: '-.01em',
                  color: noLonger ? C.mute : C.ink,
                  transition: 'color .5s',
                }}
              >
                “Reporting can send reports — because it only reads approved summaries.”
              </span>
              {noLonger && (
                <span
                  style={{
                    font: '400 14px/1.5 var(--font-sans)',
                    color: C.red,
                    animation: 'up .4s both',
                  }}
                >
                  Not true anymore: Reporting read the shared notepad.
                </span>
              )}
            </div>
          )}

          {st === 4 && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 14,
                padding: '16px 18px',
                borderRadius: 16,
                background: 'oklch(0.48 0.13 262 / .06)',
                border: '1px solid oklch(0.48 0.13 262 / .3)',
                animation: 'up .5s .3s both',
              }}
            >
              <span
                style={{
                  width: 34,
                  height: 34,
                  flex: 'none',
                  borderRadius: '50%',
                  background: C.blue,
                  color: C.paper,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  font: '700 11px var(--font-sans)',
                  letterSpacing: -1,
                  animation: 'ringSm 1.6s infinite',
                }}
              >
                ❚❚
              </span>
              <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                <span style={{ font: '600 15px var(--font-sans)' }}>Weekly report — paused</span>
                <span style={{ font: '400 13px var(--font-sans)', color: C.mute }}>
                  Caught before it was sent. Nothing left.
                </span>
              </span>
            </div>
          )}

          {st === 2 && (
            <div
              style={{
                padding: '16px 18px',
                borderRadius: 16,
                background: C.amberBg,
                border: '1px solid oklch(0.74 0.14 75 / .5)',
                font: '400 15px/1.5 var(--font-sans)',
                color: 'oklch(0.42 0.09 70)',
                animation: 'up .5s .2s both',
              }}
            >
              {BRAND} noticed a new connection. Nothing is wrong yet — no data has gone anywhere.
            </div>
          )}

          {st === 3 && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 14,
                animation: 'up .5s both',
              }}
            >
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
                {['Customer info', 'Support', 'Shared notepad', 'Reporting', 'Outside'].map(
                  (t, i) => (
                    <span
                      key={t}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        gap: 6,
                        animation: `popIn .4s ${i * 0.12}s both`,
                      }}
                    >
                      <span
                        style={{
                          font: '500 13px/1 var(--font-sans)',
                          padding: '8px 11px',
                          borderRadius: 999,
                          background: C.redBg,
                          border: '1px solid oklch(0.56 0.19 30 / .35)',
                          color: C.red,
                        }}
                      >
                        {t}
                      </span>
                      {i < 4 && <span style={{ color: C.red, fontSize: 13 }}>→</span>}
                    </span>
                  ),
                )}
              </div>
              <span style={{ font: '400 14px/1.5 var(--font-sans)', color: C.mute }}>
                This is a possible path, not proof that anything leaked.
              </span>
            </div>
          )}

          {st === 5 && <VoiceCardDemo voice={voice} />}

          {st === 6 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {FIX.map(([t, sb], i) => {
                const done = sub > i;
                const now = sub === i;
                return (
                  <div
                    key={t}
                    style={{
                      display: 'flex',
                      gap: 14,
                      alignItems: 'flex-start',
                      padding: '12px 0',
                      borderBottom: `1px solid ${C.ruleSoft}`,
                      opacity: done || now ? 1 : 0.3,
                      transition: 'opacity .5s',
                    }}
                  >
                    <span
                      style={{
                        width: 22,
                        height: 22,
                        flex: 'none',
                        marginTop: 1,
                        borderRadius: '50%',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        font: '700 11px var(--font-sans)',
                        color: C.paper,
                        background: done
                          ? i === 2
                            ? C.red
                            : i === 4
                              ? C.amberLine
                              : C.green
                          : 'transparent',
                        border: done ? 0 : now ? `2px dotted ${C.blue}` : `1.5px solid ${C.rule}`,
                        animation: now && !done ? 'spin 1.2s linear infinite' : 'none',
                        transition: 'background .4s',
                      }}
                    >
                      {done ? (i === 4 ? '!' : '✓') : ''}
                    </span>
                    <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <span style={{ font: '600 15px/1.35 var(--font-sans)' }}>{t}</span>
                      <span
                        style={{
                          font: '400 13.5px/1.45 var(--font-sans)',
                          color: done ? C.mute : C.faint,
                        }}
                      >
                        {sb}
                      </span>
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          {st === 7 && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10 }}>
                {[
                  'Leak path closed',
                  'Old report never sent',
                  'New report sent safely',
                  'Support and Priya’s work untouched',
                ].map((t, i) => (
                  <div
                    key={t}
                    style={{
                      padding: 16,
                      borderRadius: 16,
                      background: C.greenBg,
                      border: '1px solid oklch(0.5 0.11 155 / .25)',
                      display: 'flex',
                      flexDirection: 'column',
                      gap: 8,
                      animation: `up .5s ${i * 0.1}s both`,
                    }}
                  >
                    <span style={{ font: '700 14px var(--font-sans)', color: C.green }}>✓</span>
                    <span style={{ font: '500 14px/1.35 var(--font-sans)' }}>{t}</span>
                  </div>
                ))}
              </div>
              <div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}>
                <button
                  type="button"
                  className="btn-primary"
                  style={{ height: 46, padding: '0 20px', fontSize: 15 }}
                  onClick={() => goStep(1)}
                >
                  ↺ Watch again
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  style={{ height: 46, padding: '0 20px', fontSize: 15 }}
                  onClick={() => navigate('console')}
                >
                  Open the full console →
                </button>
                <button
                  type="button"
                  className="btn-ghost"
                  style={{ height: 46, padding: '0 20px', fontSize: 15 }}
                  onClick={() => navigate('home')}
                >
                  Back to home
                </button>
              </div>
            </div>
          )}

          <div
            style={{
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
              gap: 12,
              paddingTop: 8,
            }}
          >
            <button
              type="button"
              className="btn-ghost"
              disabled={st === 1}
              onClick={() => goStep(st - 1)}
              style={{
                flex: 'none',
                whiteSpace: 'nowrap',
                height: 46,
                padding: '0 18px',
                fontSize: 15,
                opacity: st === 1 ? 0.35 : 1,
              }}
            >
              ← Back
            </button>
            <span style={{ font: '400 12px var(--font-sans)', color: C.mute, textAlign: 'center' }}>
              ← → keys
            </span>
            <button
              type="button"
              className="btn-primary"
              disabled={nextOff}
              onClick={next}
              style={{
                flex: 'none',
                whiteSpace: 'nowrap',
                height: 46,
                padding: '0 22px',
                fontSize: 15,
                background: st === 5 ? C.blue : C.ink,
                opacity: nextOff ? 0.35 : 1,
              }}
            >
              {nextLabel}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
