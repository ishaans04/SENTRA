/**
 * Replay transport.
 *
 * The scrubber is the spine of the demonstration: it lets anyone reach the
 * exact moment a risk appears and step back across it. Positions are absolute
 * ledger sequence numbers, and moving to one replays from the start, so what
 * you see at a position is always what the engine derives from the evidence
 * rather than a cached frame.
 */

import { useEffect, useRef } from 'react';

import { Button } from '../../shared/ui/primitives';
import { useConsole } from '../../shared/state/store';

const TICK_MS = 1100;

export function Transport() {
  const cursor = useConsole((s) => s.cursor);
  const state = useConsole((s) => s.state);
  const playing = useConsole((s) => s.playing);
  const busy = useConsole((s) => s.busy);
  const findings = useConsole((s) => s.findings);
  const { play, pause, step, seek, runToEnd, restart } = useConsole.getState();

  const last = state?.last_sequence ?? 0;
  const atEnd = cursor >= last && last > 0;
  const timer = useRef<number | null>(null);

  // The play loop stops itself at the end of the ledger rather than spinning.
  useEffect(() => {
    if (!playing) return;
    if (atEnd) {
      pause();
      return;
    }
    timer.current = window.setTimeout(() => void step(), TICK_MS);
    return () => {
      if (timer.current) window.clearTimeout(timer.current);
    };
  }, [playing, atEnd, cursor, step, pause]);

  const detectedAt = findings[0]?.detected_at_sequence ?? null;
  const current = state?.timeline.find((event) => event.sequence === cursor) ?? null;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Button
          onClick={() => (playing ? pause() : play())}
          variant={playing ? 'quiet' : 'primary'}
          disabled={busy || (atEnd && !playing)}
          pressed={playing}
        >
          {playing ? 'Pause' : 'Play'}
        </Button>
        <Button onClick={() => void step()} disabled={busy || atEnd}>
          Step
        </Button>
        <Button onClick={() => void runToEnd()} disabled={busy || atEnd}>
          Run to end
        </Button>
        <Button onClick={() => void restart()} disabled={busy}>
          Restart
        </Button>

        <div className="ml-auto flex items-center gap-3">
          <span className="tabular text-[11px] text-muted">
            {String(cursor).padStart(2, '0')} / {String(last).padStart(2, '0')}
          </span>
          {busy && (
            <span className="label !text-mint" role="status">
              working
            </span>
          )}
        </div>
      </div>

      {/* Scrubber. Each tick is an event; the marker shows where risk appears. */}
      <div>
        <label htmlFor="replay-position" className="sr-only">
          Replay position
        </label>
        <input
          id="replay-position"
          type="range"
          min={0}
          max={last}
          step={1}
          value={cursor}
          disabled={busy || last === 0}
          onChange={(event) => void seek(Number(event.target.value))}
          className="h-1 w-full cursor-pointer appearance-none rounded bg-rule accent-mint disabled:cursor-not-allowed"
          aria-valuetext={
            current
              ? `Event ${cursor}: ${current.actor} ${current.action} ${current.target}`
              : 'Start'
          }
        />
        <div className="mt-2 flex items-start justify-between gap-6">
          <p className="m-0 max-w-[62ch] text-[12.5px] leading-relaxed text-muted">
            {current ? (
              <>
                <span className="tabular text-ink">{current.actor}</span>{' '}
                <span className="text-muted-deep">{current.action}</span>{' '}
                <span className="tabular text-ink">{current.target}</span>
                {typeof current.context.note === 'string' && (
                  <span className="block pt-1 text-muted-deep italic">{current.context.note}</span>
                )}
              </>
            ) : (
              'The estate is at rest. Nothing has been observed yet.'
            )}
          </p>
          {detectedAt !== null && detectedAt > 0 && (
            <span className="label shrink-0 !text-red">risk closed at event {detectedAt}</span>
          )}
        </div>
      </div>
    </div>
  );
}
