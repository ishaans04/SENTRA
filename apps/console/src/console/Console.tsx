import {
  memo,
  useCallback,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type RefObject,
} from 'react';

import { Brand } from '../shared/Brand';
import { navigate } from '../shared/route';
import { BRAND, C, MOD_KEY } from '../shared/theme';
import {
  CHAPTERS,
  CHECKS,
  DICTATION,
  EVENTS,
  LAST_BEAT,
  REMEMBER_BEAT,
  REMEMBER_DICTATION,
  VERIFIED_BEAT,
  NODE_IDS,
  NODES,
  NOTE,
  OPERATOR_BEAT,
  POS,
  RECOVER_BEAT,
  TONE,
  CASE_FILE_BEAT,
  ROUTE_BEAT,
  WITHDRAWN_BEAT,
  beatOfEvent,
  chapterFill,
  chapterOf,
  controls,
  decision,
  edgeViews,
  hops,
  isChapterStart,
  markers,
  nodeView,
  observed,
  parse,
  parseOrder,
  recoverySteps,
  runs,
  visibleCount,
  type NodeId,
  type PlanStep,
  type StepState,
} from './story';
import type { Answer } from './ask';
import { AskCard, VoiceSteps } from './AskCard';
import './console.css';
import './glass.css';

const SPEEDS = [0.5, 1, 2] as const;
type Speed = (typeof SPEEDS)[number];

const pad = (n: number) => String(n).padStart(2, '0');

// ---------------------------------------------------------------------------
// The interaction map

const NODE_TONE = {
  base: [C.rule, C.card, '0 1px 2px oklch(0.23 0.012 70 / .05)'],
  red: [C.red, C.redBg, '0 0 0 5px oklch(0.56 0.19 30 / .12)'],
  amber: [C.amberLine, C.amberBg, '0 1px 2px oklch(0.23 0.012 70 / .05)'],
  green: [C.green, C.greenBg, '0 0 0 5px oklch(0.50 0.11 155 / .10)'],
} as const;

const TAG_TONE = {
  green: [C.green, C.greenBg],
  amber: [C.amber, C.amberBg],
  blue: [C.blue, C.blueBg],
  ink: [C.ink, C.card],
} as const;

const MapPanel = memo(function MapPanel({
  beat,
  sel,
  onSelect,
  asked,
}: {
  beat: number;
  sel: NodeId | null;
  onSelect: (id: NodeId | null) => void;
  /** Boxes the latest Ask SENTRA answer is about. */
  asked?: readonly NodeId[];
}) {
  const edges = edgeViews(beat);
  const detail = sel ? { ...NODES[sel], observed: observed(sel, beat) } : null;

  // The map is drawn on a fixed 1000 × 600 canvas and scaled as one piece to
  // the box, so labels and boxes keep their proportions at any window size
  // instead of reflowing into one another.
  const mapRef = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = mapRef.current;
    if (!el) return;
    const fit = () => {
      const w = el.clientWidth;
      if (w > 0) el.style.setProperty('--s', String(w / 1000));
    };
    fit();
    if (typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(fit);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  return (
    <section className="cx-panel">
      <div className="cx-panel-head">
        <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <span className="cx-panel-title">What the agents did</span>
          <span className="cx-sub">interaction map · support/reporting estate</span>
        </div>
        <div
          className="cx-sub"
          style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}
        >
          <Legend line={`1.5px solid ${C.line}`} label="declared" />
          <Legend line={`1.5px dashed ${C.amberLine}`} label="observed, not in manifest" />
          <Legend line={`2px solid ${C.red}`} label="composed route" />
        </div>
      </div>
      <div className="cx-map-scroll">
        <div ref={mapRef} className="cx-map">
          <div className="cx-map-canvas">
            <Zones />
            <svg
              viewBox="0 0 1000 600"
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
              {edges
                .filter((e) => e.halo)
                .map((e) => (
                  <path
                    key={e.id + 'halo'}
                    d={e.d}
                    fill="none"
                    stroke={C.red}
                    strokeOpacity={0.13}
                    strokeWidth={12}
                    strokeLinecap="round"
                  />
                ))}
              {edges.map((e) => (
                <g key={e.id}>
                  <path
                    d={e.d}
                    fill="none"
                    stroke={e.stroke}
                    strokeWidth={e.width}
                    strokeOpacity={e.opacity}
                    strokeDasharray={e.dash}
                    strokeLinecap="round"
                    style={
                      e.march
                        ? { animation: 'march14 .7s linear infinite' }
                        : { transition: 'stroke .5s' }
                    }
                  />
                  {Array.from({ length: e.packets }, (_, i) => (
                    <circle key={i} r={3.4} fill={e.packetColor}>
                      <animateMotion
                        dur={`${e.packetDur}s`}
                        repeatCount="indefinite"
                        path={e.d}
                        begin={`${(-i * e.packetDur) / e.packets}s`}
                      />
                    </circle>
                  ))}
                </g>
              ))}
              {beat >= 11 && (
                <g stroke={C.ink} strokeWidth={2} strokeLinecap="round">
                  <line x1={652} y1={414.5} x2={668} y2={430.5} />
                  <line x1={652} y1={430.5} x2={668} y2={414.5} />
                </g>
              )}
            </svg>
            {markers(beat).map((m) => (
              <span
                key={m.text}
                className="cx-marker"
                style={{
                  left: `${m.x / 10}%`,
                  top: `${m.y / 6}%`,
                  color: m.color,
                  background: m.bg,
                  border: `1px solid ${m.color}`,
                  animation: m.pulse
                    ? 'pop .35s ease both, softBlink 1.4s .4s ease-in-out infinite'
                    : 'pop .35s ease both',
                }}
              >
                {m.text}
              </span>
            ))}
            {NODE_IDS.map((id) => (
              <MapNode
                key={id}
                id={id}
                beat={beat}
                selected={sel === id}
                asked={!!asked?.includes(id)}
                onSelect={onSelect}
              />
            ))}
            {detail && (
              <div className="cx-detail">
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'baseline',
                    gap: 8,
                  }}
                >
                  <span style={{ font: '600 13px var(--font-sans)' }}>{detail.name}</span>
                  <button
                    type="button"
                    onClick={() => onSelect(null)}
                    style={{
                      border: 0,
                      background: 'transparent',
                      cursor: 'pointer',
                      font: '500 11px var(--font-mono)',
                      color: C.mute,
                    }}
                  >
                    close
                  </button>
                </div>
                <span className="cx-sub" style={{ fontSize: 10, letterSpacing: '.04em' }}>
                  {detail.kind}
                </span>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                  <span className="cx-label">DECLARED</span>
                  {detail.declared.map((g) => (
                    <span key={g} style={{ font: '400 12px/1.35 var(--font-sans)' }}>
                      {g}
                    </span>
                  ))}
                </div>
                {detail.observed.length > 0 && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span className="cx-label" style={{ color: C.amber }}>
                      OBSERVED · NOT IN MANIFEST
                    </span>
                    {detail.observed.map((g) => (
                      <span
                        key={g}
                        style={{
                          font: '400 12px/1.35 var(--font-sans)',
                          color: 'oklch(0.45 0.1 70)',
                        }}
                      >
                        {g}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </section>
  );
});

function Legend({ line, label }: { line: string; label: string }) {
  return (
    <span style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
      <span style={{ width: 18, height: 0, borderTop: line }} />
      {label}
    </span>
  );
}

function Zones() {
  const band = (top: string, height: string, background?: string) => (
    <div
      style={{
        position: 'absolute',
        left: 0,
        right: 0,
        top,
        height,
        background,
        borderBottom: `1px solid ${C.ruleSoft}`,
      }}
    />
  );
  return (
    <>
      {band(
        '0',
        '25%',
        'repeating-linear-gradient(135deg,oklch(0.955 0.014 30) 0 1px,transparent 1px 10px)',
      )}
      {band('25%', '45%')}
      {band(
        '70%',
        '15%',
        'repeating-linear-gradient(135deg,oklch(0.95 0.03 85) 0 1px,transparent 1px 8px)',
      )}
      <div
        style={{
          position: 'absolute',
          left: 0,
          right: 0,
          top: '85%',
          height: '15%',
          background: 'radial-gradient(oklch(0.88 0.008 80) 1px,transparent 1.2px) 0 0/12px 12px',
        }}
      />
      <span className="cx-zone-label" style={{ top: 10, color: 'oklch(0.50 0.06 30)' }}>
        RESTRICTED · INTERIOR
      </span>
      <span className="cx-zone-label" style={{ top: 'calc(25% + 10px)', color: C.mute }}>
        INTERNAL · APPROVED STATE
      </span>
      <span className="cx-zone-label" style={{ top: 'calc(70% + 10px)', color: C.amber }}>
        SHARED · UNTRUSTED
      </span>
      <span className="cx-zone-label" style={{ top: 'calc(85% + 10px)', color: C.mute }}>
        EXTERNAL
      </span>
    </>
  );
}

function MapNode({
  id,
  beat,
  selected,
  asked,
  onSelect,
}: {
  id: NodeId;
  beat: number;
  selected: boolean;
  asked: boolean;
  onSelect: (id: NodeId | null) => void;
}) {
  const v = nodeView(id, beat);
  const [border, bg, shadow] = NODE_TONE[v.tone];
  const g = NODES[id].g;
  const [tagColor, tagBg] = v.tag ? TAG_TONE[v.tag[1]] : [C.ink, C.card];
  return (
    <button
      type="button"
      className={asked ? 'cx-node is-asked' : 'cx-node'}
      aria-label={`${v.name}: ${v.sub}`}
      aria-pressed={selected}
      onClick={() => onSelect(selected ? null : id)}
      style={{
        left: `${POS[id][0] / 10}%`,
        top: `${POS[id][1] / 6}%`,
        border: `1px solid ${selected ? C.ink : border}`,
        background: bg,
        boxShadow: selected ? `0 0 0 2px ${C.ink}` : shadow,
        opacity: v.visible ? 1 : 0,
        pointerEvents: v.visible ? 'auto' : 'none',
      }}
    >
      <span style={{ display: 'flex', gap: 7, alignItems: 'center', minWidth: 0 }}>
        <span
          style={{
            width: 8,
            height: 8,
            flex: 'none',
            border: `1.5px ${g === 'scratch' ? 'dashed' : 'solid'} ${
              v.tone === 'red' ? C.red : g === 'scratch' ? C.amberLine : C.ink
            }`,
            borderRadius: g === 'agent' ? '50%' : 1,
            transform: g === 'ext' ? 'rotate(45deg)' : 'none',
          }}
        />
        <span style={{ font: '500 12px/1.15 var(--font-sans)', color: C.ink, minWidth: 0 }}>
          {v.name}
        </span>
      </span>
      <span style={{ font: '400 9.5px/1.25 var(--font-mono)', color: C.mute }}>{v.sub}</span>
      {v.tag && (
        <span
          key={v.tag[0]}
          className="cx-node-tag"
          style={{ color: tagColor, background: tagBg, border: `1px solid ${tagColor}` }}
        >
          {v.tag[0]}
        </span>
      )}
    </button>
  );
}

// ---------------------------------------------------------------------------
// The ledger

const LedgerPanel = memo(function LedgerPanel({
  beat,
  onJump,
  cited,
}: {
  beat: number;
  onJump: (b: number) => void;
  /** Event numbers the latest Ask SENTRA answer cites. */
  cited?: readonly number[];
}) {
  const vis = visibleCount(beat);
  const recent = EVENTS.slice(0, vis)
    .map((e, i) => ({ e, i }))
    .slice(-6)
    .reverse();
  return (
    <section className="cx-panel">
      <div className="cx-panel-head">
        <div style={{ display: 'flex', gap: 10, alignItems: 'baseline', flexWrap: 'wrap' }}>
          <span className="cx-panel-title">One ledger, three lanes</span>
          <span className="cx-sub">
            what people approved · what the gateway enforced · what agents did
          </span>
        </div>
        <span className="cx-sub">click any mark to jump</span>
      </div>
      <div style={{ padding: '10px 16px 6px', display: 'flex', flexDirection: 'column' }}>
        {(
          [
            ['decision', 'DECISIONS'],
            ['gateway', 'GATEWAY'],
            ['agent', 'AGENTS'],
          ] as const
        ).map(([lane, name]) => (
          <div key={lane} className="cx-lane">
            <span className="cx-label" style={{ lineHeight: 1.2, letterSpacing: '.05em' }}>
              {name}
            </span>
            <div className="cx-lane-cells">
              {EVENTS.map((e, i) => {
                const has = e.lane === lane;
                const past = i < vis;
                const cur = i === vis - 1;
                return (
                  <button
                    key={i}
                    type="button"
                    title={`#${pad(i + 1)} ${e.actor} ${e.verb} ${e.target}`}
                    aria-label={`Jump to event ${i + 1}`}
                    tabIndex={has ? 0 : -1}
                    className={has && cited?.includes(i + 1) ? 'is-cited' : undefined}
                    onClick={() => onJump(beatOfEvent(i))}
                    style={{ background: cur ? 'oklch(0.94 0.012 80)' : undefined }}
                  >
                    <span
                      style={{
                        width: cur ? 5 : 3,
                        height: !has ? 0 : cur ? 24 : past ? 15 : 5,
                        background: past ? TONE[e.tone] : C.rule,
                        opacity: has ? 1 : 0,
                      }}
                    />
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </div>
      <div style={{ padding: '6px 16px 12px', display: 'flex', flexDirection: 'column' }}>
        {recent.map(({ e, i }, j) => (
          <div
            key={i}
            className="cx-entry"
            style={{ opacity: 1 - j * 0.12, animation: j === 0 ? 'rise .45s ease both' : 'none' }}
          >
            <span className="mono" style={{ fontSize: 11, fontWeight: 500, color: C.mute }}>
              #{pad(i + 1)}
            </span>
            <span style={{ fontWeight: 500 }}>{e.actor}</span>
            <span className="mono" style={{ fontSize: 11, color: C.mute }}>
              {e.verb}
            </span>
            <span>{e.target}</span>
            <span className="mono" style={{ fontSize: 11, lineHeight: 1.35, color: NOTE[e.tone] }}>
              {e.note}
            </span>
          </div>
        ))}
      </div>
      <div className="cx-keys">
        <span>
          <b>Space</b> play / pause
        </span>
        <span>
          <b>← →</b> step
        </span>
        <span>
          <b>{MOD_KEY} K</b> tell {BRAND}
        </span>
        <span>
          <b>{MOD_KEY} ↵</b> confirm
        </span>
      </div>
    </section>
  );
});

// ---------------------------------------------------------------------------
// The case file

const STEP_LOOK: Record<StepState, { mark: string; dot: string; ring: string; anim: string }> = {
  done: { mark: '✓', dot: C.green, ring: '0', anim: 'none' },
  run: {
    mark: '',
    dot: 'transparent',
    ring: `2px dotted ${C.blue}`,
    anim: 'spin 1s linear infinite',
  },
  wait: { mark: '', dot: 'transparent', ring: `1.5px solid ${C.rule}`, anim: 'none' },
  conflict: { mark: '!', dot: C.amberLine, ring: '0', anim: 'none' },
  skip: { mark: '–', dot: C.rule, ring: '0', anim: 'none' },
};

function DecisionCard({ beat }: { beat: number }) {
  const dec = decision(beat);
  return (
    <article className="cx-card" style={{ animation: 'none' }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}
      >
        <span className="cx-label" style={{ fontSize: 11 }}>
          DECISION D-07
        </span>
        <span
          className="cx-badge"
          style={{ color: dec.color, background: dec.bg, transition: 'all .4s' }}
        >
          {dec.status}
        </span>
      </div>
      <p style={{ margin: 0, font: 'italic 400 19px/1.35 var(--font-serif)', textWrap: 'pretty' }}>
        “Reporting may proceed because the Reporting Agent receives information only from the
        approved, sanitized report store.”
      </p>
      <span className="cx-sub">{dec.meta}</span>
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          gap: 6,
          padding: '10px 12px',
          borderRadius: 9,
          background: C.wash,
        }}
      >
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 10,
            alignItems: 'baseline',
          }}
        >
          <span className="cx-label" style={{ whiteSpace: 'nowrap' }}>
            CONDITION C-07a
          </span>
          <span
            className="mono"
            style={{
              fontSize: 11,
              fontWeight: 500,
              color: dec.condColor,
              transition: 'color .4s',
              textAlign: 'right',
            }}
          >
            {dec.cond}
          </span>
        </div>
        <span className="mono" style={{ fontSize: 12, lineHeight: 1.4 }}>
          reads(Reporting Agent) ⊆ {'{'} Internal Report Store {'}'}
        </span>
        {dec.showBasis && (
          <span
            style={{
              font: '400 12px/1.45 var(--font-sans)',
              color: 'oklch(0.45 0.15 30)',
              animation: 'rise .4s ease both',
            }}
          >
            Checked for another accepted basis: none found. Review required.
          </span>
        )}
      </div>
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span className="cx-label" style={{ marginBottom: 4 }}>
          RUNS UNDER THIS DECISION
        </span>
        {runs(beat).map((r) => (
          <div
            key={r.id}
            className="cx-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '62px minmax(0,1fr)',
              gap: 10,
              padding: '6px 0',
              animation: 'rise .4s ease both',
            }}
          >
            <span className="mono" style={{ fontSize: 12, fontWeight: 500 }}>
              {r.id}
            </span>
            <span
              style={{
                font: '400 12px/1.4 var(--font-sans)',
                color: r.color,
                transition: 'color .4s',
              }}
            >
              {r.state}
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}

function FindingCard({ beat }: { beat: number }) {
  const state =
    beat >= VERIFIED_BEAT
      ? 'contained · verified #23'
      : beat >= 11
        ? 'contained · verifying'
        : 'open · cites #02 #07 #09 #12';
  return (
    <article className="cx-card" style={{ borderColor: C.red, gap: 12 }}>
      <div
        style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 10 }}
      >
        <span className="cx-label" style={{ fontSize: 11, color: C.red }}>
          FINDING · PS-001
        </span>
        <span className="cx-sub">{state}</span>
      </div>
      <span style={{ font: '500 15px/1.35 var(--font-sans)', textWrap: 'pretty' }}>
        Restricted data can reach an external destination through shared state nobody declared.
      </span>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {hops(beat).map((h) => (
          <div
            key={h.i}
            className="cx-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '18px minmax(0,1fr) auto',
              gap: 10,
              alignItems: 'baseline',
              padding: '7px 0',
            }}
          >
            <span className="mono" style={{ fontSize: 11, fontWeight: 500, color: C.mute }}>
              {h.i}
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ font: '400 12.5px/1.3 var(--font-sans)' }}>{h.route}</span>
              <span className="mono" style={{ fontSize: 10.5, color: C.mute }}>
                {h.kind} · evidence {h.ev}
              </span>
            </span>
            <span
              className="cx-badge"
              style={{
                fontSize: 9.5,
                padding: '4px 6px',
                borderRadius: 4,
                color: h.color,
                background: h.bg,
              }}
            >
              {h.flag}
            </span>
          </div>
        ))}
      </div>
      <p
        className="cx-row"
        style={{
          margin: 0,
          font: 'italic 400 14px/1.45 var(--font-serif)',
          color: 'oklch(0.40 0.012 70)',
          paddingTop: 10,
        }}
      >
        A possible route, not proof of a leak. It does not establish that content travelled it, or
        why either agent acted.
      </p>
    </article>
  );
}

function ContainmentCard({ beat }: { beat: number }) {
  const cols = 'minmax(0,1fr) 44px 44px';
  return (
    <article className="cx-card" style={{ gap: 10, animationDelay: '.12s' }}>
      <span className="cx-label" style={{ fontSize: 11 }}>
        CONTAINMENT · 5 PRE-AUTHORISED CONTROLS
      </span>
      <div
        className="cx-label"
        style={{ display: 'grid', gridTemplateColumns: cols, gap: 8, fontSize: 9.5 }}
      >
        <span>CONTROL</span>
        <span style={{ textAlign: 'center' }}>ROUTE</span>
        <span style={{ textAlign: 'center' }}>WORK</span>
      </div>
      {controls(beat).map((k) => (
        <div
          key={k.name}
          style={{
            display: 'grid',
            gridTemplateColumns: cols,
            gap: 8,
            alignItems: 'center',
            padding: '8px 10px',
            margin: '0 -10px',
            borderRadius: 8,
            background: k.bg,
            transition: 'background .4s',
          }}
        >
          <span style={{ display: 'flex', flexDirection: 'column', gap: 3, minWidth: 0 }}>
            <span style={{ font: '400 12.5px/1.3 var(--font-sans)', color: k.textColor }}>
              {k.name}
            </span>
            <span
              className="mono"
              style={{
                fontSize: 10,
                fontWeight: 500,
                letterSpacing: '.04em',
                color: k.verdictColor,
              }}
            >
              {k.verdict}
            </span>
          </span>
          <span style={{ textAlign: 'center', font: '500 13px var(--font-sans)', color: C.green }}>
            ✓
          </span>
          <span
            style={{
              textAlign: 'center',
              font: '500 13px var(--font-sans)',
              color: k.keepsWork ? C.green : C.red,
            }}
          >
            {k.keepsWork ? '✓' : '✕'}
          </span>
        </div>
      ))}
      <span style={{ font: '400 11.5px/1.45 var(--font-sans)', color: C.mute }}>
        Every control is simulated against a copy of the live graph. Two remove the route but sever
        declared work, so they are rejected.
      </span>
    </article>
  );
}

function TellCard({
  beat,
  text,
  touched,
  landed,
  plan,
  modelOff,
  setModelOff,
  onText,
  onConfirm,
  taRef,
}: {
  beat: number;
  text: string;
  touched: boolean;
  landed: boolean;
  plan: PlanStep[] | null;
  modelOff: boolean;
  setModelOff: (v: boolean) => void;
  onText: (t: string) => void;
  onConfirm: () => void;
  taRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const live = parse(text);
  const shown = beat > OPERATOR_BEAT && plan ? plan : live;
  const parsedBy = modelOff
    ? 'parsed by deterministic grammar · model off'
    : touched
      ? 'your words · parsed by the grammar in this replay'
      : 'parsed by Gemini Flash-Lite · grammar fallback';
  return (
    <article className="cx-card cx-tell" style={{ gap: 12 }}>
      <VoiceSteps active="tell" />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ font: '600 14px var(--font-sans)' }}>Tell {BRAND}</span>
        <span className="cx-sub" style={{ fontSize: 10.5 }}>
          dictate with Wispr Flow, or type
        </span>
      </div>
      <textarea
        ref={taRef}
        value={text}
        onChange={(e) => onText(e.target.value)}
        disabled={beat !== OPERATOR_BEAT}
        rows={4}
        aria-label={`Tell ${BRAND} what to do`}
        placeholder="Say what should stop, what should be recovered, and what must be kept."
        style={{ background: landed ? C.amberBg : C.card }}
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            gap: 10,
            alignItems: 'center',
            marginBottom: 6,
            flexWrap: 'wrap',
          }}
        >
          <span className="cx-label">READ-BACK · NOTHING RUNS UNTIL CONFIRMED</span>
          <span className="cx-seg" role="group" aria-label="Interpretation">
            <button type="button" aria-pressed={!modelOff} onClick={() => setModelOff(false)}>
              Gemini
            </button>
            <button type="button" aria-pressed={modelOff} onClick={() => setModelOff(true)}>
              Model off
            </button>
          </span>
        </div>
        <span className="mono" style={{ fontSize: 10, color: C.blue, marginBottom: 4 }}>
          {parsedBy}
        </span>
        {shown.map((s) => (
          <div
            key={s.k}
            className="cx-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '16px minmax(0,1fr)',
              gap: 10,
              padding: '7px 0',
              opacity: s.on ? 1 : 0.4,
              transition: 'opacity .3s',
            }}
          >
            <span
              style={{
                width: 12,
                height: 12,
                marginTop: 2,
                borderRadius: 3,
                border: `1.5px solid ${s.on ? C.blue : C.faint}`,
                background: s.on ? C.blue : 'transparent',
                transition: 'all .3s',
              }}
            />
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ font: '500 12.5px/1.3 var(--font-sans)' }}>{s.label}</span>
              <span className="mono" style={{ fontSize: 10.5, lineHeight: 1.35, color: C.mute }}>
                {s.on ? s.detail : 'not requested'}
              </span>
            </span>
          </div>
        ))}
      </div>
      <span style={{ font: '400 11.5px/1.45 var(--font-sans)', color: C.mute }}>
        Will not block the external send (severs declared reporting), and will not restore old
        snapshots over later human edits.
      </span>
      {beat === OPERATOR_BEAT && (
        <button
          type="button"
          className="cx-confirm"
          disabled={!live.some((s) => s.on)}
          onClick={onConfirm}
        >
          Confirm read-back and run · ↵
        </button>
      )}
      {beat > OPERATOR_BEAT && (
        <span
          className="mono"
          style={{
            fontSize: 11,
            fontWeight: 500,
            color: C.blue,
            padding: '9px 10px',
            borderRadius: 8,
            background: C.blueBg,
          }}
        >
          CONFIRMED #16 · D-07 RENEWED AT EPOCH 4, SCOPED TO r-0413
        </span>
      )}
    </article>
  );
}

function RecoveryCard({ beat, plan }: { beat: number; plan: PlanStep[] }) {
  return (
    <article className="cx-card" style={{ gap: 4 }}>
      <span className="cx-label" style={{ fontSize: 11, marginBottom: 6 }}>
        RECOVERY · THROUGH THE GATEWAY
      </span>
      {recoverySteps(plan, beat).map((s) => {
        const look = STEP_LOOK[s.state];
        return (
          <div
            key={s.k}
            className="cx-row"
            style={{
              display: 'grid',
              gridTemplateColumns: '20px minmax(0,1fr)',
              gap: 10,
              padding: '9px 0',
            }}
          >
            <span
              style={{
                width: 16,
                height: 16,
                borderRadius: '50%',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                font: '600 10px/1 var(--font-sans)',
                color: 'oklch(0.99 0.004 85)',
                border: look.ring,
                background: look.dot,
                animation: look.anim,
                transition: 'background .4s',
              }}
            >
              {look.mark}
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
              <span style={{ font: '500 12.5px/1.3 var(--font-sans)' }}>{s.label}</span>
              <span style={{ font: '400 11.5px/1.4 var(--font-sans)', color: s.subColor }}>
                {s.sub}
              </span>
            </span>
          </div>
        );
      })}
    </article>
  );
}

function RecordCard({
  onRestart,
  onContinue,
}: {
  onRestart: () => void;
  /** Present until the replay has moved on to Remember. */
  onContinue?: () => void;
}) {
  return (
    <article className="cx-card cx-record">
      <span className="cx-label" style={{ fontSize: 11, color: 'oklch(0.75 0.01 80)' }}>
        OUTCOME RECORD · REPLAYABLE
      </span>
      <p style={{ margin: 0, font: '400 21px/1.3 var(--font-serif)', textWrap: 'pretty' }}>
        Affected send cancelled. Unexpected access removed. Report rebuilt from approved sources.
        Support work preserved.
      </p>
      <div style={{ display: 'flex', flexDirection: 'column' }}>
        {CHECKS.map(([label, ev]) => (
          <div
            key={label}
            style={{
              display: 'grid',
              gridTemplateColumns: '16px minmax(0,1fr)',
              gap: 10,
              padding: '8px 0',
              borderTop: '1px solid oklch(0.36 0.01 70)',
            }}
          >
            <span style={{ font: '600 12px var(--font-sans)', color: 'oklch(0.78 0.12 155)' }}>
              ✓
            </span>
            <span style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
              <span style={{ font: '500 12.5px/1.3 var(--font-sans)' }}>{label}</span>
              <span
                className="mono"
                style={{ fontSize: 10.5, lineHeight: 1.4, color: 'oklch(0.75 0.01 80)' }}
              >
                {ev}
              </span>
            </span>
          </div>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {onContinue && (
          <button
            type="button"
            onClick={onContinue}
            style={{
              height: 34,
              padding: '0 14px',
              border: 0,
              background: 'oklch(0.97 0.006 85)',
              color: 'var(--ink)',
              borderRadius: 8,
              cursor: 'pointer',
              font: '500 12px var(--font-sans)',
            }}
          >
            Continue to Remember →
          </button>
        )}
        <button
          type="button"
          onClick={onRestart}
          style={{
            height: 34,
            padding: '0 14px',
            border: '1px solid oklch(0.5 0.01 70)',
            background: 'transparent',
            color: 'oklch(0.97 0.006 85)',
            borderRadius: 8,
            cursor: 'pointer',
            font: '500 12px var(--font-sans)',
          }}
        >
          Replay from the start
        </button>
        <button
          type="button"
          onClick={() => navigate('home')}
          style={{
            height: 34,
            padding: '0 14px',
            border: 0,
            background: 'transparent',
            color: 'oklch(0.75 0.01 80)',
            cursor: 'pointer',
            font: '500 12px var(--font-sans)',
          }}
        >
          Back to home
        </button>
      </div>
      <span style={{ font: '400 11px/1.45 var(--font-sans)', color: 'oklch(0.75 0.01 80)' }}>
        Recorded replay of fictional fixtures, not live operation. Switch the read-back to “Model
        off”: holds, rejections and recovery are identical.
      </span>
    </article>
  );
}

function RememberCard({
  beat,
  text,
  onText,
  onKeep,
}: {
  beat: number;
  text: string;
  onText: (t: string) => void;
  onKeep: () => void;
}) {
  const order = parseOrder(text);
  return (
    <article className="cx-card cx-tell" style={{ gap: 12 }}>
      <VoiceSteps active="remember" />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ font: '600 14px var(--font-sans)' }}>Remember for next time</span>
        <span className="cx-sub" style={{ fontSize: 10.5 }}>
          a standing order · dictate or type
        </span>
      </div>
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        disabled={beat !== REMEMBER_BEAT}
        rows={3}
        aria-label={`Tell ${BRAND} to remember`}
        placeholder="Say what should always hold from now on."
      />
      <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
        <span className="cx-label" style={{ marginBottom: 6 }}>
          READ-BACK · KEPT ONLY WHEN YOU CONFIRM
        </span>
        {order.lines.map((line) => (
          <div
            key={line}
            className="cx-row mono"
            style={{
              padding: '6px 0',
              fontSize: 11,
              lineHeight: 1.4,
              color: order.ok ? C.ink : C.faint,
              transition: 'color .3s',
            }}
          >
            {line}
          </div>
        ))}
      </div>
      <span style={{ font: '400 11.5px/1.45 var(--font-sans)', color: C.mute }}>
        Only your confirmed words write a standing order. Agents have no way to add one.
      </span>
      {beat === REMEMBER_BEAT && (
        <button type="button" className="cx-confirm" disabled={!order.ok} onClick={onKeep}>
          Keep this standing order · ↵
        </button>
      )}
      {beat > REMEMBER_BEAT && (
        <span
          className="mono"
          style={{
            fontSize: 11,
            fontWeight: 500,
            color: C.blue,
            padding: '9px 10px',
            borderRadius: 8,
            background: C.blueBg,
          }}
        >
          CONFIRMED · SO-1 · LOADED INTO EVERY LATER SESSION
        </span>
      )}
    </article>
  );
}

function CaseFileTitle() {
  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'baseline',
        padding: '0 2px',
      }}
    >
      <span className="cx-panel-title">What people approved, and why</span>
      <span className="cx-sub">case file</span>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function Console() {
  const [beat, setBeat] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [text, setText] = useState('');
  const [touched, setTouched] = useState(false);
  const [orderText, setOrderText] = useState('');
  const [orderTouched, setOrderTouched] = useState(false);
  const [sel, setSel] = useState<NodeId | null>(null);
  const [plan, setPlan] = useState<PlanStep[] | null>(null);
  const [landed, setLanded] = useState(false);
  const [speed, setSpeed] = useState<Speed>(1);
  const [modelOff, setModelOff] = useState(false);
  const [glassOpen, setGlassOpen] = useState(false);
  const [record, setRecord] = useState<'none' | 'pop' | 'leaving' | 'docked'>('none');
  // A question belongs to the beat it was asked at; any step clears it.
  const [ask, setAsk] = useState<{ beat: number; reply: Answer | null } | null>(null);
  const [nudgeClosed, setNudgeClosed] = useState(false);

  const headRef = useRef<HTMLElement>(null);
  const glassRef = useRef<HTMLDivElement>(null);
  const taRef = useRef<HTMLTextAreaElement>(null);
  const askRef = useRef<HTMLTextAreaElement>(null);
  const askLive = ask && ask.beat === beat ? ask : null;
  const prevBeat = useRef(beat);
  const prevStage = useRef(beat);

  const curText = (b = beat) => (touched ? text : b >= OPERATOR_BEAT ? DICTATION : '');
  const curOrder = () =>
    orderTouched ? orderText : beat >= REMEMBER_BEAT ? REMEMBER_DICTATION : '';

  const go = (raw: number) => {
    const b = Math.max(0, Math.min(LAST_BEAT, raw));
    if (b > OPERATOR_BEAT && !plan) setPlan(parse(curText(OPERATOR_BEAT)));
    if (b <= OPERATOR_BEAT) setPlan(null);
    setBeat(b);
  };

  const confirm = () => {
    if (beat !== OPERATOR_BEAT) return;
    const p = parse(curText());
    if (!p.some((s) => s.on)) return;
    setPlan(p);
    setBeat(OPERATOR_BEAT + 1);
    setPlaying(true);
  };

  const keep = () => {
    if (beat !== REMEMBER_BEAT || !parseOrder(curOrder()).ok) return;
    setBeat(REMEMBER_BEAT + 1);
    setPlaying(true);
  };

  /** Confirm whatever is waiting for the operator now. */
  const confirmHere = () => (beat === REMEMBER_BEAT ? keep() : confirm());

  const togglePlay = () => {
    if (playing) return setPlaying(false);
    if (beat >= LAST_BEAT) {
      setPlan(null);
      setBeat(0);
      return setPlaying(true);
    }
    if (beat === OPERATOR_BEAT) return confirm();
    if (beat === REMEMBER_BEAT) return keep();
    setPlaying(true);
  };

  const openTell = () => {
    if (beat < OPERATOR_BEAT) {
      setBeat(OPERATOR_BEAT);
      setPlaying(false);
      setPlan(null);
    }
    setGlassOpen(true);
    window.setTimeout(() => taRef.current?.focus({ preventScroll: true }), 420);
  };

  /** Asking pauses the replay, so the answer stays on screen while it is read. */
  const startAsk = () => {
    setPlaying(false);
    setAsk((a) => (a && a.beat === beat ? a : { beat, reply: null }));
  };

  const onReply = (reply: Answer) => {
    setPlaying(false);
    setAsk({ beat, reply });
  };

  const openAsk = () => {
    if (beat < ROUTE_BEAT) {
      setBeat(ROUTE_BEAT);
      setPlan(null);
    }
    setPlaying(false);
    setAsk({ beat: Math.max(beat, ROUTE_BEAT), reply: null });
    setGlassOpen(true);
    window.setTimeout(() => askRef.current?.focus({ preventScroll: true }), 420);
  };

  const restart = () => {
    setPlan(null);
    setTouched(false);
    setText('');
    setOrderTouched(false);
    setOrderText('');
    setBeat(0);
    setPlaying(true);
  };

  /** From the outcome record straight to Remember, with the record docked. */
  const continueToRemember = () => {
    setRecord('docked');
    setPlaying(false);
    go(REMEMBER_BEAT);
  };
  const onContinue = beat < REMEMBER_BEAT ? continueToRemember : undefined;

  const waiting = beat === OPERATOR_BEAT || beat === REMEMBER_BEAT;
  const next = () => (waiting ? confirmHere() : go(beat + 1));

  // Autoplay: chapter openings hold longer than ordinary beats, and the
  // outcome record longest, long enough to read before it moves into the case
  // file. Play then goes on to Remember, and always stops where the operator
  // has to decide and at the end.
  useEffect(() => {
    if (!playing) return;
    const dur = (beat === VERIFIED_BEAT ? 6500 : isChapterStart(beat) ? 3400 : 2200) / speed;
    const id = window.setTimeout(() => {
      if (waiting || beat >= LAST_BEAT) setPlaying(false);
      else setBeat(beat + 1);
    }, dur);
    return () => window.clearTimeout(id);
  }, [beat, playing, speed, waiting]);

  // Arriving at the operator beat with the suggested words: flash the box.
  useEffect(() => {
    const was = prevBeat.current;
    prevBeat.current = beat;
    if (beat === OPERATOR_BEAT && was !== OPERATOR_BEAT && !touched) {
      setLanded(true);
      const id = window.setTimeout(() => setLanded(false), 1200);
      return () => window.clearTimeout(id);
    }
  }, [beat, touched]);

  // The glass case file slides in with the route chapter, and again as each
  // new stage begins (route found, withdrawn, decide, recover), even if it was
  // closed. Before the route chapter the case file sits on the page instead.
  useEffect(() => {
    const was = prevStage.current;
    prevStage.current = beat;
    if (beat < CASE_FILE_BEAT) return setGlassOpen(false);
    const stages = [
      CASE_FILE_BEAT,
      ROUTE_BEAT,
      WITHDRAWN_BEAT,
      OPERATOR_BEAT,
      RECOVER_BEAT,
      REMEMBER_BEAT,
    ];
    if (stages.some((s) => was < s && beat >= s)) setGlassOpen(true);
  }, [beat]);

  // The outcome record pops up mid-screen, then after three seconds moves
  // into the case file. Arriving later than the record, it is already there.
  useEffect(() => {
    if (beat < VERIFIED_BEAT) setRecord('none');
    else if (beat === VERIFIED_BEAT) setRecord((r) => (r === 'none' ? 'pop' : r));
    else setRecord((r) => (r === 'none' ? 'docked' : r));
  }, [beat]);
  useEffect(() => {
    if (record === 'pop') {
      const id = window.setTimeout(() => setRecord('leaving'), 3000);
      return () => window.clearTimeout(id);
    }
    if (record === 'leaving') {
      const id = window.setTimeout(() => {
        setRecord('docked');
        setGlassOpen(true);
      }, 550);
      return () => window.clearTimeout(id);
    }
  }, [record]);

  // Stepping away ends a question, so coming back to its beat (or replaying)
  // starts clean instead of bringing the old answer back.
  useEffect(() => {
    setAsk((a) => (a && a.beat !== beat ? null : a));
  }, [beat]);

  // Keep the card for what is happening now in view, and mark it.
  const focus = askLive
    ? 'ask'
    : beat >= REMEMBER_BEAT
      ? 'remember'
      : record === 'docked'
        ? 'record'
        : beat >= RECOVER_BEAT
          ? 'recovery'
          : beat >= OPERATOR_BEAT
            ? 'tell'
            : beat === ROUTE_BEAT
              ? 'finding'
              : 'decision';
  useEffect(() => {
    const body = glassRef.current;
    if (!glassOpen || !body) return;
    const id = window.setTimeout(() => {
      const card = body.querySelector<HTMLElement>(`[data-card="${focus}"]`);
      if (card) body.scrollTo({ top: card.offsetTop - 12, behavior: 'smooth' });
    }, 140);
    return () => window.clearTimeout(id);
  }, [focus, glassOpen, beat]);

  // The rail sticks below the header, whatever height the header wraps to.
  useEffect(() => {
    const h = headRef.current;
    if (!h || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() =>
      h.parentElement?.style.setProperty('--hdr', `${h.offsetHeight}px`),
    );
    ro.observe(h);
    return () => ro.disconnect();
  }, []);

  const dismiss = () => {
    if (record === 'pop') setRecord('leaving');
    else setGlassOpen(false);
  };
  const keys = useRef({ togglePlay, next, go, openTell, confirmHere, dismiss, beat });
  keys.current = { togglePlay, next, go, openTell, confirmHere, dismiss, beat };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const k = keys.current;
      const t = e.target as HTMLElement | null;
      const inField = !!t && (t.tagName === 'TEXTAREA' || t.tagName === 'INPUT');
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        k.openTell();
        return;
      }
      if (e.key === 'Escape') {
        k.dismiss();
        return;
      }
      if (inField) {
        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
          e.preventDefault();
          k.confirmHere();
        }
        return;
      }
      if (t && t.tagName === 'BUTTON' && e.key === 'Enter') return;
      if (e.key === ' ') {
        e.preventDefault();
        k.togglePlay();
      } else if (e.key === 'ArrowRight') {
        const held = k.beat === OPERATOR_BEAT || k.beat === REMEMBER_BEAT;
        k.go(held ? k.beat : k.beat + 1);
      } else if (e.key === 'ArrowLeft') k.go(k.beat - 1);
      else if (e.key === 'Enter' && (k.beat === OPERATOR_BEAT || k.beat === REMEMBER_BEAT))
        k.confirmHere();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);
  const jump = useCallback((b: number) => keys.current.go(b), []);

  const vis = visibleCount(beat);
  const ch = chapterOf(beat);
  const cur = EVENTS[vis - 1];
  const shownText = curText();
  const activePlan = plan ?? parse(shownText);
  const playLabel = playing
    ? '❚❚  Pause'
    : beat >= LAST_BEAT
      ? '↺  Replay'
      : beat === OPERATOR_BEAT
        ? 'Confirm ↵'
        : beat === REMEMBER_BEAT
          ? 'Keep ↵'
          : '▶  Play';

  return (
    <div className="cx">
      <header ref={headRef} className="cx-head">
        <button
          type="button"
          className="cx-home"
          onClick={() => navigate('home')}
          aria-label={`${BRAND} home`}
        >
          <Brand size={16} />
        </button>
        <div className="cx-transport">
          <button
            type="button"
            className="cx-icon-btn"
            onClick={() => go(beat - 1)}
            title="Previous event (←)"
            aria-label="Previous event"
          >
            ‹
          </button>
          <button
            type="button"
            className={`cx-play${waiting && !playing ? ' is-confirm' : ''}`}
            onClick={togglePlay}
            title="Play / pause (space)"
          >
            {playLabel}
          </button>
          <button
            type="button"
            className="cx-icon-btn"
            onClick={next}
            title="Next event (→)"
            aria-label="Next event"
          >
            ›
          </button>
          <button
            type="button"
            className="cx-speed"
            title="Replay speed"
            aria-label={`Replay speed ${speed}×`}
            onClick={() => setSpeed(SPEEDS[(SPEEDS.indexOf(speed) + 1) % SPEEDS.length])}
          >
            {speed}×
          </button>
        </div>
        <nav className="cx-chapters" aria-label="Chapters">
          {CHAPTERS.map((c, i) => (
            <button
              key={c.short}
              type="button"
              className="cx-chapter"
              onClick={() => go(c.s)}
              aria-current={i === ch ? 'step' : undefined}
            >
              <span
                className="cx-chapter-label"
                style={{ color: i === ch ? C.ink : i < ch ? C.mute : C.faint }}
              >
                {pad(i + 1)} {c.short}
              </span>
              <span className="cx-chapter-track">
                <span
                  style={{
                    width: `${Math.round(chapterFill(i, beat) * 100)}%`,
                    background: i === ch ? C.blue : C.line,
                  }}
                />
              </span>
            </button>
          ))}
        </nav>
        <button type="button" className="cx-tell-btn cx-ask-btn" onClick={openAsk}>
          Ask {BRAND}
        </button>
        <button type="button" className="cx-tell-btn" onClick={openTell}>
          Tell {BRAND} <span className="kbd">{MOD_KEY} K</span>
        </button>
      </header>

      <div className="cx-body">
        <main className="cx-main">
          <div className="cx-narr">
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10, maxWidth: 760 }}>
              <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span
                  className="cx-label"
                  style={{ fontSize: 11, letterSpacing: '.08em', marginRight: 6 }}
                >
                  CHAPTER {pad(ch + 1)} OF {pad(CHAPTERS.length)}
                </span>
                <span className="cx-badge" style={{ border: `1px solid ${C.rule}`, color: C.mute }}>
                  RECORDED SESSION · FICTIONAL DATA
                </span>
                <span className="cx-badge" style={{ background: C.blueBg, color: C.blue }}>
                  {modelOff
                    ? 'INTERPRETATION · GRAMMAR · MODEL OFF'
                    : 'INTERPRETATION · GEMINI FLASH-LITE'}
                </span>
              </div>
              <h1 key={ch}>{CHAPTERS[ch].title}</h1>
              <p>{CHAPTERS[ch].body}</p>
            </div>
            <div
              className="cx-narr-event"
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 6,
                alignItems: 'flex-end',
                textAlign: 'right',
                maxWidth: 300,
              }}
            >
              <span className="cx-label" style={{ fontSize: 11, letterSpacing: '.05em' }}>
                EVENT #{pad(vis)} / {EVENTS.length}
              </span>
              <span style={{ font: '400 13px/1.4 var(--font-sans)', color: NOTE[cur.tone] }}>
                {cur.actor} {cur.verb} {cur.target} — {cur.note}
              </span>
            </div>
          </div>

          <MapPanel beat={beat} sel={sel} onSelect={setSel} asked={askLive?.reply?.nodes} />
          <LedgerPanel beat={beat} onJump={jump} cited={askLive?.reply?.cites} />
        </main>

        {/* Before the route chapter the case file sits on the page. After
            that it lives only in the glass panel, open or closed; the column
            keeps its width so the panel never covers the map. */}
        <aside className="cx-rail">
          {beat < CASE_FILE_BEAT && (
            <>
              <CaseFileTitle />
              <DecisionCard beat={beat} />
            </>
          )}
        </aside>
      </div>

      {beat >= CASE_FILE_BEAT && (
        <aside
          className={`cx-glass${glassOpen ? ' is-open' : ''}`}
          aria-label="Case file"
          aria-hidden={!glassOpen}
          inert={!glassOpen}
        >
          <div className="cx-glass-head">
            <span className="cx-glass-live" aria-hidden="true" />
            <span className="cx-panel-title">Case file</span>
            <span className="cx-sub">
              {pad(ch + 1)} {CHAPTERS[ch].short.toLowerCase()} · event #{pad(vis)}
            </span>
            <button
              type="button"
              className="cx-glass-close"
              aria-label="Close case file"
              title="Close (Esc)"
              onClick={() => setGlassOpen(false)}
            >
              ✕
            </button>
          </div>
          <div ref={glassRef} className="cx-glass-body">
            <CaseFileTitle />
            <div data-card="decision" className={focus === 'decision' ? 'is-focus' : undefined}>
              <DecisionCard beat={beat} />
            </div>
            {beat >= ROUTE_BEAT && (
              <>
                <div data-card="finding" className={focus === 'finding' ? 'is-focus' : undefined}>
                  <FindingCard beat={beat} />
                </div>
                <ContainmentCard beat={beat} />
                <div data-card="ask" className={focus === 'ask' ? 'is-focus' : undefined}>
                  <AskCard
                    beat={beat}
                    reply={askLive?.reply ?? null}
                    nudgeClosed={nudgeClosed}
                    onCloseNudge={() => setNudgeClosed(true)}
                    onStart={startAsk}
                    onReply={onReply}
                    inputRef={askRef}
                  />
                </div>
              </>
            )}
            {beat >= OPERATOR_BEAT && (
              <div data-card="tell" className={focus === 'tell' ? 'is-focus' : undefined}>
                <TellCard
                  beat={beat}
                  text={shownText}
                  touched={touched}
                  landed={landed}
                  plan={plan}
                  modelOff={modelOff}
                  setModelOff={setModelOff}
                  onText={(t) => {
                    setText(t);
                    setTouched(true);
                  }}
                  onConfirm={confirm}
                  taRef={taRef}
                />
              </div>
            )}
            {beat >= RECOVER_BEAT && (
              <div data-card="recovery" className={focus === 'recovery' ? 'is-focus' : undefined}>
                <RecoveryCard beat={beat} plan={activePlan} />
              </div>
            )}
            {record === 'docked' && (
              <div data-card="record" className={focus === 'record' ? 'is-focus' : undefined}>
                <RecordCard onRestart={restart} onContinue={onContinue} />
              </div>
            )}
            {beat >= REMEMBER_BEAT && (
              <div data-card="remember" className={focus === 'remember' ? 'is-focus' : undefined}>
                <RememberCard
                  beat={beat}
                  text={curOrder()}
                  onText={(t) => {
                    setOrderText(t);
                    setOrderTouched(true);
                  }}
                  onKeep={keep}
                />
              </div>
            )}
          </div>
        </aside>
      )}

      {beat >= CASE_FILE_BEAT && !glassOpen && record !== 'pop' && (
        <button type="button" className="cx-glass-tab" onClick={() => setGlassOpen(true)}>
          <span className="cx-glass-live" aria-hidden="true" />
          Case file
        </button>
      )}

      {(record === 'pop' || record === 'leaving') && (
        <div
          className={`cx-record-pop${record === 'leaving' ? ' is-leaving' : ''}`}
          onClick={() => setRecord('leaving')}
        >
          <div
            className="cx-record-pop-card"
            role="dialog"
            aria-label="Outcome record"
            onClick={(e) => e.stopPropagation()}
          >
            <RecordCard onRestart={restart} onContinue={onContinue} />
            <div className="cx-record-pop-foot">
              <span>Moving to the case file</span>
              <span className="cx-record-pop-bar">
                <i />
              </span>
              <button type="button" onClick={() => setRecord('leaving')}>
                Move now
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
