import { useCallback, useEffect, useRef, useState } from 'react';

export const DICTATION =
  'Stop this report, cut its access to the notepad, and rebuild it from approved summaries. Keep the support work.';

export const VOICE_ITEMS = [
  'Stop the weekly report',
  'Cut Reporting’s access to the notepad',
  'Rebuild the report from approved summaries',
  'Leave Support’s work and people’s edits alone',
];

export type VoicePhase = 'idle' | 'listening' | 'typed' | 'confirmed';

interface VoiceState {
  phase: VoicePhase;
  chars: number;
  /** How many read-back items have ticked off after confirming. */
  done: number;
}

const IDLE: VoiceState = { phase: 'idle', chars: 0, done: 0 };

/**
 * A simulated dictation: listen, type the words out, read them back as steps,
 * then tick the steps off once confirmed. State is local to whoever uses it,
 * so typing re-renders only that card.
 */
export function useVoice(onConfirmed?: () => void) {
  const [s, setS] = useState<VoiceState>(IDLE);
  const typer = useRef<number | undefined>(undefined);
  const timers = useRef<number[]>([]);
  const confirmedCb = useRef(onConfirmed);
  useEffect(() => {
    confirmedCb.current = onConfirmed;
  }, [onConfirmed]);

  const stop = useCallback(() => {
    window.clearInterval(typer.current);
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  }, []);
  useEffect(() => stop, [stop]);

  const later = (ms: number, fn: () => void) => {
    timers.current.push(window.setTimeout(fn, ms));
  };

  const reset = useCallback(() => {
    stop();
    setS(IDLE);
  }, [stop]);

  const start = useCallback(() => {
    stop();
    setS({ phase: 'listening', chars: 0, done: 0 });
    later(900, () => {
      typer.current = window.setInterval(() => {
        setS((p) => {
          const n = p.chars + 2;
          if (n >= DICTATION.length) {
            window.clearInterval(typer.current);
            return { ...p, chars: DICTATION.length, phase: 'typed' };
          }
          return { ...p, chars: n };
        });
      }, 28);
    });
  }, [stop]);

  const confirm = useCallback(() => {
    stop();
    setS((p) => ({ ...p, phase: 'confirmed', done: 0 }));
    [1, 2, 3, 4].forEach((i) => later(i * 380, () => setS((p) => ({ ...p, done: i }))));
    later(4 * 380 + 900, () => confirmedCb.current?.());
  }, [stop]);

  /** Jump straight to the finished state, as when stepping past the voice beat. */
  const finish = useCallback(() => {
    stop();
    setS({ phase: 'confirmed', chars: DICTATION.length, done: 4 });
  }, [stop]);

  return { ...s, text: DICTATION.slice(0, s.chars), start, confirm, reset, finish };
}

export type Voice = ReturnType<typeof useVoice>;
