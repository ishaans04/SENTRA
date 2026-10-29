import { useEffect, useState } from 'react';

import { useSeen, useTimers } from '../shared/hooks';
import { spotlight } from '../shared/pointer';
import { navigate } from '../shared/route';
import { BRAND } from '../shared/theme';
import './why.css';

const SITUATION =
  'Reporting just read a notepad full of customer details. Its weekly report goes out in a minute.';

const LLM_REPLY =
  'That does sound concerning. You may want to review the Reporting agent’s permissions and check whether the report contains anything sensitive before it’s sent. Would you like some tips on data governance?';

const SENTRA_STEPS = [
  { tone: 'red', text: 'Route found: customer data can now reach the outside', ev: '#12' },
  { tone: 'red', text: 'Approval D-07 no longer holds — the reason you gave is gone', ev: '#13' },
  { tone: 'blue', text: 'Weekly report held at the gateway, before it left', ev: '#14' },
  { tone: 'mute', text: 'Waiting for your words. Nothing else runs until you confirm.', ev: '' },
] as const;

/** The three things the lede promises a model can't: one box each. */
const DIFFERENCES = [
  {
    title: 'It sees the whole system',
    llm: 'Sees one conversation at a time.',
    us: 'Watches how every agent connects, so it catches risks no single step shows.',
  },
  {
    title: 'It remembers why you said yes',
    llm: 'Forgets the reason behind an approval once the chat ends.',
    us: 'Stores every approval with its condition, and re-checks it on each new event.',
  },
  {
    title: 'It acts, not just advises',
    llm: 'Can suggest what to do. Can’t stop anything.',
    us: 'Sits at the gateway every agent passes through: it holds sends and rejects stale calls.',
  },
];

const REASONS = [
  {
    glyph: 'ledger',
    title: 'Audit-ready by default',
    body: 'Every approval, hold and fix lands in one ledger you can replay, event by event.',
  },
  {
    glyph: 'switch',
    title: 'Works with the model off',
    body: 'Use Gemini for freer wording, or switch it off. What gets blocked never depends on a model.',
  },
  {
    glyph: 'thread',
    title: 'The smallest possible fix',
    body: 'It pauses the one affected job and keeps the rest of your agents working.',
  },
  {
    glyph: 'gate',
    title: 'Sits in front of the tools you have',
    body: 'A gateway in front of your existing MCP tool servers. Your agents don’t need rebuilding.',
  },
] as const;

function AskBoth() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  const [chars, setChars] = useState(0);
  const [steps, setSteps] = useState(0);
  const [round, setRound] = useState(0);
  const { after, clear } = useTimers();

  useEffect(() => {
    if (!seen) return;
    clear();
    setChars(0);
    setSteps(0);
    let n = 0;
    const id = window.setInterval(() => {
      n += 3;
      setChars(Math.min(n, LLM_REPLY.length));
      if (n >= LLM_REPLY.length) window.clearInterval(id);
    }, 24);
    SENTRA_STEPS.forEach((_, i) => after(500 + i * 700, () => setSteps(i + 1)));
    return () => window.clearInterval(id);
  }, [seen, round, after, clear]);

  const llmDone = chars >= LLM_REPLY.length;
  const usDone = steps >= SENTRA_STEPS.length;

  return (
    <div ref={ref} className={`ld-ask ld-reveal${seen ? ' is-seen' : ''}`}>
      <div className="ld-ask-situation">
        <span className="ld-why-label">THE SITUATION</span>
        <p>{SITUATION}</p>
        <button type="button" className="ld-why-link" onClick={() => setRound((r) => r + 1)}>
          ↺ Ask both again
        </button>
      </div>
      <div className="ld-ask-panes">
        <div className="ld-pane" onMouseMove={spotlight}>
          <div className="ld-pane-head">
            <span>A general AI assistant</span>
            <span className="ld-pane-tag">ILLUSTRATIVE</span>
          </div>
          <div className="ld-bubble">
            {LLM_REPLY.slice(0, chars)}
            {!llmDone && <span className="caret" style={{ background: 'currentColor' }} />}
          </div>
          <span className={`ld-pane-foot is-bad${llmDone ? ' is-in' : ''}`}>
            ✕ Nothing was stopped. The report still goes out.
          </span>
        </div>
        <div className="ld-pane is-us" onMouseMove={spotlight}>
          <div className="ld-pane-head">
            <span>{BRAND}</span>
            <span className="ld-pane-tag">FROM THE RECORDED SESSION</span>
          </div>
          <div className="ld-steps">
            {SENTRA_STEPS.map((s, i) => (
              <div key={s.text} className={`ld-step tone-${s.tone}${steps > i ? ' is-in' : ''}`}>
                <span className="ld-step-dot" />
                <span className="ld-step-text">{s.text}</span>
                {s.ev && <span className="ld-step-ev">{s.ev}</span>}
              </div>
            ))}
          </div>
          <span className={`ld-pane-foot is-good${usDone ? ' is-in' : ''}`}>
            ✓ Stopped in time. Support kept working.
          </span>
        </div>
      </div>
    </div>
  );
}

function Differences() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  return (
    <div ref={ref} className="ld-reasons-wrap">
      <h3 className="ld-why-h3">Three differences that matter at work.</h3>
      <div className="ld-reasons ld-diffs">
        {DIFFERENCES.map((d, i) => (
          <article
            key={d.title}
            className={`ld-reason ld-diff${seen ? ' is-seen' : ''}`}
            style={{ transitionDelay: `${i * 0.1}s` }}
            onMouseMove={spotlight}
          >
            <span className="ld-diff-num">0{i + 1}</span>
            <span className="ld-reason-title">{d.title}</span>
            <div className="ld-diff-row is-llm">
              <span className="ld-diff-who">A plain LLM</span>
              <span className="ld-diff-mark">✕</span>
              <span>{d.llm}</span>
            </div>
            <div className="ld-diff-row is-us">
              <span className="ld-diff-who">{BRAND}</span>
              <span className="ld-diff-mark">✓</span>
              <span>{d.us}</span>
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}

function Reasons() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  return (
    <div ref={ref} className="ld-reasons-wrap">
      <h3 className="ld-why-h3">Why teams choose it.</h3>
      <div className="ld-reasons">
        {REASONS.map((r, i) => (
          <div
            key={r.title}
            className={`ld-reason${seen ? ' is-seen' : ''}`}
            style={{ transitionDelay: `${i * 0.1}s` }}
            onMouseMove={spotlight}
          >
            <span className={`ld-glyph glyph-${r.glyph}`} aria-hidden="true">
              <i />
              <i />
              <i />
            </span>
            <span className="ld-reason-title">{r.title}</span>
            <span className="ld-reason-body">{r.body}</span>
          </div>
        ))}
      </div>
      <button type="button" className="ld-why-cta" onClick={() => navigate('console')}>
        See every step in the console →
      </button>
    </div>
  );
}

export function WhySentra() {
  const [ref, seen] = useSeen<HTMLDivElement>();
  return (
    <section id="why" className="ld-why">
      <div className="ld-why-panel">
        <div className="ld-why-glow" aria-hidden="true" />
        <div ref={ref} className={`ld-sec-head ld-reveal${seen ? ' is-seen' : ''}`}>
          <span className="ld-why-label">05 — WHY NOT JUST AN LLM?</span>
          <h2 className="ld-h2">
            A chatbot gives advice. <span className="ld-why-dim">{BRAND} holds the line.</span>
          </h2>
          <p className="ld-why-lede">
            Language models are brilliant with words. Keeping a company’s agents safe takes things a
            model can’t promise on its own: a view of the whole system, a memory of why you said
            yes, and the power to actually stop something.
          </p>
        </div>
        <AskBoth />
        <Differences />
        <Reasons />
      </div>
    </section>
  );
}
