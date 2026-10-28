/**
 * Recovery (PRD §13.5, §13.6).
 *
 * "Tell AEGIS" is a plain multi-line box, opened with Ctrl+K and submitted with
 * Ctrl+Enter, so a dictated instruction lands in it exactly as Wispr Flow
 * types it. The plan comes back as a read-back; nothing runs until the
 * operator confirms it, by button or by saying "Confirm". Each step then shows
 * its real result. A conflict offers only "Keep the human version" or "Leave
 * for review": overwriting a person's edit is not offered.
 */

import { useEffect, useRef, useState } from 'react';

import type { ConflictView, FinalRecord, Snapshot } from '../../shared/lib/aegisTypes';
import { currentPlan, useAegis } from '../../shared/state/aegisSlice';
import { Button, Panel, Pill } from '../../shared/ui/primitives';

export const SUGGESTED_RECOVERY =
  'Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work.';

const HINTS = [
  SUGGESTED_RECOVERY,
  'Cancel the reporting run and keep the support work.',
  'Confirm',
];

const STEP_LABEL: Record<string, string> = {
  CANCEL_RUN: 'Cancel run',
  HOLD_ACTION: 'Hold send',
  APPLY_CONTROL: 'Apply control',
  REVOKE_ACCESS: 'Revoke access',
  COMPENSATE: 'Correct what it wrote',
  REBUILD: 'Rebuild',
  ESCALATE: 'Escalate',
};

const RESULT_TONE = {
  succeeded: 'mint',
  conflict: 'amber',
  failed: 'red',
  escalated: 'red',
} as const;

function ConflictCard({ conflict, snapshot }: { conflict: ConflictView; snapshot: Snapshot }) {
  const busy = useAegis((s) => s.busy);
  const resolve = useAegis((s) => s.resolveConflict);
  const item = snapshot.items.find((i) => i.id === conflict.item);
  return (
    <article
      aria-label={`Conflict on ${conflict.item}`}
      className="rule-box border-l-2 border-l-amber bg-ground p-3"
    >
      <header className="flex items-center gap-2">
        <Pill tone="amber">conflict</Pill>
        <span className="font-mono text-[11.5px] text-ink">{conflict.item}</span>
        <span className="ml-auto text-[11px] text-muted-deep">
          {conflict.status.replace(/_/g, ' ')}
        </span>
      </header>
      <p className="mt-2 mb-0 text-[12px] leading-relaxed text-muted">{conflict.detail}</p>
      {item && (
        <p className="mt-2 mb-0 text-[11.5px] text-muted-deep">
          Current version {item.version}, written by {item.writer}: “{item.content}”
        </p>
      )}
      {conflict.status === 'open' && (
        <div className="mt-3 flex flex-wrap gap-2">
          <Button
            variant="primary"
            disabled={busy}
            onClick={() => void resolve(conflict.id, 'keep_human')}
          >
            Keep the human version
          </Button>
          <Button disabled={busy} onClick={() => void resolve(conflict.id, 'leave_for_review')}>
            Leave for review
          </Button>
        </div>
      )}
    </article>
  );
}

export function RecordView({ record }: { record: FinalRecord }) {
  return (
    <section aria-label="Final record" className="rule-box border-l-2 border-l-mint bg-ground p-3">
      <h3 className="label !text-mint">Final record</h3>
      <ul className="mt-2 mb-0 flex list-none flex-col gap-1 p-0 text-[12.5px] text-ink">
        {record.summary.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {record.conflicts.length > 0 && (
        <ul className="mt-2 mb-0 flex list-none flex-col gap-1 p-0 text-[12px] text-amber">
          {record.conflicts.map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
      )}
      {record.approval && (
        <p className="mt-3 mb-0 text-[11px] leading-relaxed text-muted-deep">
          Approval {record.approval.id}: {record.approval.statement}. Evidence:{' '}
          {record.finding?.rule_id} citing {record.finding?.cited_events.join(', ')}. Controls:{' '}
          {record.plan.controls.join(', ') || 'none'}. Interpreted by {record.plan.interpreted_by}.
        </p>
      )}
    </section>
  );
}

export function RecoveryPanel() {
  const snapshot = useAegis((s) => s.snapshot);
  const busy = useAegis((s) => s.busy);
  const live = useAegis((s) => s.mode === 'live');
  const interpret = useAegis((s) => s.interpretRecovery);
  const correct = useAegis((s) => s.correctRecovery);
  const confirm = useAegis((s) => s.confirmRecovery);
  const abandon = useAegis((s) => s.abandonRecovery);
  const [text, setText] = useState('');
  const [correcting, setCorrecting] = useState(false);
  const box = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
        event.preventDefault();
        box.current?.focus();
      }
    };
    document.addEventListener('keydown', onKey);
    return () => document.removeEventListener('keydown', onKey);
  }, []);

  const plan = currentPlan(snapshot);
  const steps = (snapshot?.steps ?? []).filter((s) => s.plan_id === plan?.id);
  const checks = (snapshot?.checks ?? []).filter((c) => c.plan_id === plan?.id);
  const conflicts = (snapshot?.conflicts ?? []).filter((c) => c.plan_id === plan?.id);
  const pending = plan?.status === 'read_back';

  const submit = () => {
    if (!text.trim()) return;
    void (correcting && plan ? correct(text) : interpret(text));
    setCorrecting(false);
    setText('');
  };

  return (
    <Panel title="Recovery">
      <div className="flex flex-col gap-3">
        <label className="flex flex-col gap-1.5">
          <span className="label">
            Tell AEGIS <span className="text-muted-deep">(Ctrl+K, then Ctrl+Enter)</span>
          </span>
          <textarea
            ref={box}
            aria-label="Tell AEGIS"
            value={text}
            rows={4}
            disabled={!live || busy}
            placeholder={pending ? 'Say "Confirm", or dictate a correction.' : SUGGESTED_RECOVERY}
            onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => {
              if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                submit();
              }
            }}
            className="rule-box resize-y bg-ground p-2 text-[12.5px] leading-relaxed text-ink placeholder:text-muted-deep"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" disabled={!live || busy || !text.trim()} onClick={submit}>
            {correcting ? 'Interpret correction' : 'Interpret'}
          </Button>
          <Button disabled={!live || busy} onClick={() => setText(SUGGESTED_RECOVERY)}>
            Use the suggested words
          </Button>
        </div>
        <details className="text-[11.5px] text-muted-deep">
          <summary className="cursor-pointer">Phrasings I understand</summary>
          <ul className="mt-1 mb-0 pl-4">
            {HINTS.map((hint) => (
              <li key={hint}>{hint}</li>
            ))}
          </ul>
        </details>

        {plan?.status === 'invalid' && (
          <div role="alert" className="rule-box border-l-2 border-l-red bg-ground p-3 text-[12px]">
            <p className="m-0 text-red">
              I can't establish a safe automatic recovery for this. Here is what I found:
            </p>
            <ul className="mt-1 mb-0 pl-4 text-muted">
              {plan.errors.map((error) => (
                <li key={error}>{error}</li>
              ))}
            </ul>
          </div>
        )}

        {plan && plan.read_back && (
          <div
            aria-label="Recovery read-back"
            className="rule-box border-l-2 border-l-mint bg-ground p-3"
          >
            <div className="mb-2 flex items-center gap-2">
              <span className="font-mono text-[11px] text-muted">{plan.id}</span>
              <Pill tone={pending ? 'amber' : 'mint'}>{plan.status.replace(/_/g, ' ')}</Pill>
            </div>
            <pre className="m-0 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
              {plan.read_back}
            </pre>
            {pending && (
              <div className="mt-3 flex flex-wrap gap-2">
                <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
                  Confirm
                </Button>
                <Button
                  disabled={busy}
                  onClick={() => {
                    setCorrecting(true);
                    box.current?.focus();
                  }}
                >
                  Correct
                </Button>
                <Button disabled={busy} onClick={() => void abandon()}>
                  Cancel
                </Button>
              </div>
            )}
          </div>
        )}

        {steps.length > 0 && (
          <ol aria-label="Recovery steps" className="m-0 flex list-none flex-col gap-1.5 p-0">
            {steps.map((step) => (
              <li key={step.event_id} className="flex flex-wrap items-baseline gap-2 text-[12px]">
                <Pill tone={RESULT_TONE[step.kind]}>{step.kind}</Pill>
                <span className="text-ink">{STEP_LABEL[step.step.kind] ?? step.step.kind}</span>
                <span className="text-muted-deep">{step.detail}</span>
              </li>
            ))}
          </ol>
        )}

        {snapshot &&
          conflicts.map((conflict) => (
            <ConflictCard key={conflict.id} conflict={conflict} snapshot={snapshot} />
          ))}

        {checks.length > 0 && (
          <section aria-label="Verification" className="rule-box bg-ground p-3">
            <h3 className="label">Verification</h3>
            <ul className="mt-2 mb-0 flex list-none flex-col gap-1.5 p-0">
              {checks.map((check) => (
                <li
                  key={check.event_id}
                  className="flex flex-wrap items-baseline gap-2 text-[12px]"
                >
                  <Pill tone={check.passed ? 'mint' : 'red'}>
                    {check.passed ? 'passed' : 'failed'}
                  </Pill>
                  <span className="font-mono text-ink">{check.name.replace(/_/g, ' ')}</span>
                  <span className="text-muted-deep">{check.detail}</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        {snapshot?.record && <RecordView record={snapshot.record} />}
      </div>
    </Panel>
  );
}
