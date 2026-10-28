/**
 * The observation ledger, as the operator sees it.
 *
 * Every row is a real entry from the append-only log the analysis reads. Rows
 * a finding cites are marked as evidence, which is the link between "HIVE says
 * there is a risk" and "here is precisely what it saw" — the thing that makes a
 * finding checkable rather than assertive.
 */

import { useEffect, useRef } from 'react';

import type { ObservationEvent } from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';

function phaseOf(event: ObservationEvent): string {
  const phase = event.context.phase;
  return typeof phase === 'string' ? phase : '';
}

export function EventStream() {
  const state = useConsole((s) => s.state);
  const cursor = useConsole((s) => s.cursor);
  const findings = useConsole((s) => s.findings);
  const selectedId = useConsole((s) => s.selectedFindingId);
  const seek = useConsole((s) => s.seek);
  const activeRow = useRef<HTMLLIElement | null>(null);

  const finding = findings.find((f) => f.id === selectedId) ?? findings[0] ?? null;
  const evidence = new Set(finding?.evidence_event_ids ?? []);

  // Keep the current event in view by scrolling the list itself. scrollIntoView
  // would walk up and scroll the page too, yanking the map out of sight every
  // time the replay advances.
  useEffect(() => {
    const row = activeRow.current;
    const list = row?.parentElement;
    if (!row || !list) return;
    const top = row.offsetTop - list.offsetTop;
    const bottom = top + row.offsetHeight;
    if (top < list.scrollTop) list.scrollTop = top;
    else if (bottom > list.scrollTop + list.clientHeight) {
      list.scrollTop = bottom - list.clientHeight;
    }
  }, [cursor]);

  const timeline = state?.timeline ?? [];

  return (
    <ol className="m-0 max-h-[330px] list-none overflow-y-auto p-0">
      {timeline.map((event) => {
        // A control HIVE issued is appended above the scenario's sequence band,
        // so it is always "replayed" once it exists — it is the record of an
        // action already taken, not a future step.
        const isControl = event.action === 'block';
        const replayed = isControl || event.sequence <= cursor;
        const isCurrent = !isControl && event.sequence === cursor;
        const isEvidence = evidence.has(event.event_id);
        const phase = phaseOf(event);

        return (
          <li
            key={event.event_id}
            ref={isCurrent ? activeRow : null}
            aria-current={isCurrent ? 'step' : undefined}
            className={`border-b border-rule-soft last:border-0 ${
              isCurrent ? 'bg-mint/[0.06]' : ''
            }`}
          >
            <button
              type="button"
              onClick={() => void seek(event.sequence)}
              className="flex w-full items-baseline gap-3 px-4 py-2 text-left transition-colors hover:bg-ink/[0.03]"
            >
              <span
                className={`tabular shrink-0 text-[10px] ${
                  isControl ? 'text-mint' : replayed ? 'text-muted' : 'text-muted-deep/40'
                }`}
              >
                {isControl ? '··' : String(event.sequence).padStart(2, '0')}
              </span>

              <span
                aria-hidden
                className={`mt-[5px] size-1.5 shrink-0 rounded-full ${
                  isControl
                    ? 'bg-mint'
                    : !replayed
                      ? 'bg-rule'
                      : isEvidence
                        ? 'bg-red'
                        : phase === 'emergence'
                          ? 'bg-amber'
                          : 'bg-muted-deep'
                }`}
              />

              <span
                className={`min-w-0 flex-1 font-mono text-[11px] leading-relaxed ${
                  replayed ? 'text-ink-soft' : 'text-muted-deep/40'
                }`}
              >
                <span className={replayed ? 'text-ink' : ''}>{event.actor}</span>{' '}
                <span className="text-muted-deep">{event.action}</span>{' '}
                <span className={replayed ? 'text-ink' : ''}>{event.target}</span>
              </span>

              {isControl ? (
                <span className="label shrink-0 !text-mint !tracking-[0.1em]">control</span>
              ) : (
                isEvidence &&
                replayed && (
                  <span className="label shrink-0 !text-red !tracking-[0.1em]">evidence</span>
                )
              )}
            </button>
          </li>
        );
      })}
      {!timeline.length && (
        <li className="px-4 py-6 text-[13px] text-muted">The ledger is empty.</li>
      )}
    </ol>
  );
}
