/**
 * Storyline controls (PRD §13.8): Play, Step and Reset, and where the story is.
 *
 * Play advances one beat at a time and pauses at the beats where the operator
 * acts (the approval, the human edit, the dictated recovery), so a judge can
 * dictate or type at each one before going on.
 */

import { useEffect, useRef, useState } from 'react';

import { useAegis } from '../../shared/state/aegisSlice';
import { Button } from '../../shared/ui/primitives';

/** Beats after which Play stops so the operator can act. */
const PAUSE_AFTER = new Set([0, 4, 8]);
const BEAT_MS = 1400;

export function StoryControls() {
  const snapshot = useAegis((s) => s.snapshot);
  const busy = useAegis((s) => s.busy);
  const live = useAegis((s) => s.mode === 'live');
  const step = useAegis((s) => s.step);
  const reset = useAegis((s) => s.reset);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const atEnd = snapshot?.at_end ?? false;
  const beat = snapshot?.beat ?? -1;

  useEffect(() => {
    if (!playing || busy) return;
    if (atEnd) {
      setPlaying(false);
      return;
    }
    timer.current = setTimeout(async () => {
      await step();
      const now = useAegis.getState().snapshot?.beat ?? -1;
      if (PAUSE_AFTER.has(now)) setPlaying(false);
    }, BEAT_MS);
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [playing, busy, atEnd, beat, step]);

  const next = snapshot?.storyline.find((b) => !b.done);
  const current = snapshot?.storyline.filter((b) => b.done).at(-1);

  return (
    <div className="flex flex-wrap items-center gap-3">
      <Button
        variant="primary"
        disabled={!live || atEnd}
        pressed={playing}
        onClick={() => setPlaying((p) => !p)}
      >
        {playing ? 'Pause' : 'Play'}
      </Button>
      <Button disabled={!live || busy || atEnd} onClick={() => void step()}>
        Step
      </Button>
      <Button
        disabled={!live || busy}
        onClick={() => {
          setPlaying(false);
          void reset();
        }}
      >
        Reset
      </Button>
      <p className="m-0 text-[12px] text-muted" aria-live="polite">
        {current ? `Beat ${current.n}: ${current.title}.` : 'Not started.'}
        {next ? ` Next: ${next.title}.` : ' The story is finished.'}
      </p>
    </div>
  );
}
