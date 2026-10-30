import { useState, type KeyboardEvent, type RefObject } from 'react';

import { BRAND } from '../shared/theme';
import { ASK_SUGGESTIONS, WISPR_URL, answerQuestion, isTyping, type Answer } from './ask';

type Verb = 'ask' | 'tell' | 'remember';

/** Ask → Tell → Remember, with the card's own step marked. */
export function VoiceSteps({ active }: { active: Verb }) {
  return (
    <ol className="cx-steps" aria-label="Ask, tell, remember">
      {(['ask', 'tell', 'remember'] as const).map((v) => (
        <li key={v} aria-current={v === active ? 'step' : undefined}>
          {v.toUpperCase()}
        </li>
      ))}
    </ol>
  );
}

/** Shown once someone types into Ask: speaking is the faster way in. */
export function WisprNudge({ onClose }: { onClose: () => void }) {
  return (
    <div className="cx-nudge" role="status">
      <span className="cx-nudge-text">
        <b>Faster to say it than type it.</b>{' '}
        <span>Hold your Wispr Flow key and ask out loud.</span>{' '}
        <a href={WISPR_URL} target="_blank" rel="noopener noreferrer">
          Try Wispr Flow ↗
        </a>
      </span>
      <button type="button" className="cx-nudge-close" aria-label="Close tip" onClick={onClose}>
        ✕
      </button>
    </div>
  );
}

export function AskCard({
  beat,
  reply,
  nudgeClosed,
  onCloseNudge,
  onStart,
  onReply,
  inputRef,
}: {
  beat: number;
  reply: Answer | null;
  nudgeClosed: boolean;
  onCloseNudge: () => void;
  onStart: () => void;
  onReply: (a: Answer) => void;
  inputRef: RefObject<HTMLTextAreaElement | null>;
}) {
  const [text, setText] = useState('');
  const [typed, setTyped] = useState(false);
  const question = text.trim();

  const submit = () => {
    if (question) onReply(answerQuestion(question, beat));
  };
  const ask = (q: string) => {
    setText(q);
    onStart();
    onReply(answerQuestion(q, beat));
  };
  const onKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (isTyping(e)) setTyped(true);
    if (e.key === 'Enter' && !e.shiftKey) {
      // Ctrl/⌘+Enter elsewhere confirms the read-back; here it only asks.
      e.preventDefault();
      e.stopPropagation();
      submit();
    }
  };

  const chips = !reply ? ASK_SUGGESTIONS.slice(0, 3) : reply.intent === null ? ASK_SUGGESTIONS : [];

  return (
    <article className="cx-card cx-tell cx-ask" style={{ gap: 12 }}>
      <VoiceSteps active="ask" />
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          gap: 10,
          flexWrap: 'wrap',
        }}
      >
        <span style={{ font: '600 14px var(--font-sans)' }}>Ask {BRAND}</span>
        <span className="cx-sub" style={{ fontSize: 10.5 }}>
          ask out loud with Wispr Flow, or type
        </span>
      </div>
      {typed && !nudgeClosed && <WisprNudge onClose={onCloseNudge} />}
      <textarea
        ref={inputRef}
        value={text}
        onChange={(e) => setText(e.target.value)}
        onFocus={onStart}
        onKeyDown={onKeyDown}
        rows={2}
        aria-label={`Ask ${BRAND} a question`}
        placeholder="How did this happen?"
      />
      <div className="cx-ask-row">
        <div className="cx-chips">
          {chips.map((q) => (
            <button key={q} type="button" className="cx-chip" onClick={() => ask(q)}>
              {q}
            </button>
          ))}
        </div>
        <button
          type="button"
          className="cx-ask-go"
          aria-label="Ask the question"
          disabled={!question}
          onClick={submit}
        >
          Ask ↵
        </button>
      </div>
      {reply && (
        <div className="cx-answer" aria-live="polite">
          {reply.text}
        </div>
      )}
      <span style={{ font: '400 11.5px/1.45 var(--font-sans)', color: 'var(--mute)' }}>
        Answers come only from this session’s ledger. Asking changes nothing.
      </span>
    </article>
  );
}
