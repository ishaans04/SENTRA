/**
 * Approvals (PRD §13.4).
 *
 * The operator dictates an approval into a plain text box, so Wispr Flow types
 * straight into it. The service reads back the typed decision and condition;
 * only after that read-back is on screen can it be confirmed (INV-7). Each card
 * shows the decision exactly as the ledger has it: status, epoch, condition in
 * words and in its typed form, the runs it authorised and what happened to
 * their calls.
 */

import { useState } from 'react';

import type {
  ActionView,
  DecisionStatus,
  DecisionView,
  RejectedCall,
  RunView,
} from '../../shared/lib/aegisTypes';
import { useAegis } from '../../shared/state/aegisSlice';
import { Button, Panel, Pill } from '../../shared/ui/primitives';

const STATUS_TONE: Record<DecisionStatus, 'mint' | 'amber' | 'red' | 'neutral'> = {
  proposed: 'neutral',
  active: 'mint',
  needs_review: 'amber',
  suspended: 'red',
  withdrawn: 'neutral',
  discarded: 'neutral',
};

const ACTION_TONE = {
  queued: 'amber',
  held: 'red',
  released: 'mint',
  delivered: 'mint',
  cancelled: 'neutral',
} as const;

export const SUGGESTED_APPROVAL =
  'Approve reporting, on the condition that the Reporting Agent only reads from the approved, sanitized report store.';

function RunRow({
  run,
  actions,
  rejected,
}: {
  run: RunView;
  actions: ActionView[];
  rejected: RejectedCall[];
}) {
  return (
    <li className="border-t border-rule-soft py-2 first:border-t-0">
      <div className="flex flex-wrap items-center gap-2 text-[12px] text-ink">
        <span className="font-mono">{run.id}</span>
        <span className="text-muted-deep">epoch {run.epoch}</span>
        <Pill tone={run.status === 'running' ? 'mint' : run.status === 'stale' ? 'red' : 'neutral'}>
          {run.status}
        </Pill>
        {run.fresh_context && <Pill tone="violet">fresh context</Pill>}
      </div>
      {(actions.length > 0 || rejected.length > 0) && (
        <ul className="mt-1.5 flex flex-col gap-1 pl-3">
          {actions.map((action) => (
            <li key={action.id} className="flex flex-wrap items-center gap-2 text-[11.5px]">
              <span className="font-mono text-muted">
                Send {action.id} ({String(action.args.item ?? action.tool)})
              </span>
              <Pill tone={ACTION_TONE[action.status]}>{action.status}</Pill>
            </li>
          ))}
          {rejected.map((call) => (
            <li key={call.event_id} className="flex flex-wrap items-center gap-2 text-[11.5px]">
              <span className="font-mono text-muted">{call.tool}</span>
              <Pill tone="red">rejected</Pill>
              <span className="font-mono text-muted-deep">{call.reason}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

export function DecisionCard({ decision }: { decision: DecisionView }) {
  const snapshot = useAegis((s) => s.snapshot);
  const busy = useAegis((s) => s.busy);
  const command = useAegis((s) => s.decisionCommand);
  const runs = (snapshot?.runs ?? []).filter((r) => r.decision_id === decision.id);
  const alert = (snapshot?.alerts ?? []).find((a) => a.decision_id === decision.id);

  return (
    <article
      data-decision={decision.id}
      aria-label={`Approval ${decision.id}`}
      className={`rule-box border-l-2 bg-ground p-3 ${
        decision.status === 'suspended' ? 'border-l-red' : 'border-l-rule'
      }`}
    >
      <header className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] text-muted">{decision.id}</span>
        <h3 className="m-0 text-[13.5px] font-medium text-ink-bright">{decision.statement}</h3>
        <span className="ml-auto flex items-center gap-2">
          <Pill tone={STATUS_TONE[decision.status]}>{decision.status.replace('_', ' ')}</Pill>
          <span className="tabular font-mono text-[11px] text-muted" data-epoch={decision.epoch}>
            epoch {decision.epoch}
          </span>
        </span>
      </header>

      {decision.dictated_text && (
        <p className="mt-2 mb-0 text-[12px] leading-relaxed text-muted italic">
          “{decision.dictated_text}”
        </p>
      )}

      {decision.conditions.map((condition) => (
        <div key={condition.id} className="mt-2 text-[12px]">
          <p className="m-0 text-ink">
            {condition.id}: {condition.words}
            {condition.last_result && (
              <span
                className={`ml-2 font-mono text-[10.5px] ${
                  condition.last_result === 'HOLDS'
                    ? 'text-mint'
                    : condition.last_result === 'FAILS'
                      ? 'text-red'
                      : 'text-amber'
                }`}
              >
                {condition.last_result}
              </span>
            )}
          </p>
          <code className="mt-1 block font-mono text-[10.5px] text-muted-deep">
            {condition.typed}
          </code>
        </div>
      ))}
      {decision.conditions.length === 0 && (
        <p className="mt-2 mb-0 text-[12px] text-muted-deep">No conditions: a standing approval.</p>
      )}

      <p className="mt-2 mb-0 text-[11px] text-muted-deep">
        {decision.bases
          .map((b, i) => `Basis ${i + 1}${b.accepted ? '' : ' (withdrawn after the finding)'}`)
          .join(' · ')}
        {' · '}Hold queued sends if suspended: {decision.hold_rule ? 'on' : 'off'}
      </p>

      {alert && decision.status === 'suspended' && (
        <p className="mt-2 mb-0 border-l-2 border-red pl-2 text-[11.5px] text-red">{alert.text}</p>
      )}

      {runs.length > 0 && (
        <ul className="mt-2 mb-0 list-none p-0" aria-label={`Runs under ${decision.id}`}>
          {runs.map((run) => (
            <RunRow
              key={run.id}
              run={run}
              actions={(snapshot?.actions ?? []).filter((a) => a.run_id === run.id)}
              rejected={(snapshot?.rejected_calls ?? []).filter((c) => c.run_id === run.id)}
            />
          ))}
        </ul>
      )}

      {(decision.status === 'suspended' || decision.status === 'active') &&
        decision.conditions.length > 0 && (
          <div className="mt-3 flex gap-2">
            {decision.status === 'suspended' && (
              <Button disabled={busy} onClick={() => void command(decision.id, 'renew')}>
                Renew
              </Button>
            )}
            <Button disabled={busy} onClick={() => void command(decision.id, 'withdraw')}>
              Withdraw
            </Button>
          </div>
        )}
    </article>
  );
}

export function ApprovalsPanel() {
  const snapshot = useAegis((s) => s.snapshot);
  const proposal = useAegis((s) => s.proposal);
  const busy = useAegis((s) => s.busy);
  const live = useAegis((s) => s.mode === 'live');
  const interpret = useAegis((s) => s.interpretApproval);
  const confirm = useAegis((s) => s.confirmProposal);
  const reject = useAegis((s) => s.rejectProposal);
  const [text, setText] = useState('');

  const decisions = (snapshot?.decisions ?? []).filter(
    (d) => d.status !== 'discarded' && d.status !== 'proposed',
  );

  return (
    <Panel title="Approvals">
      <div className="flex flex-col gap-3">
        {decisions.map((decision) => (
          <DecisionCard key={decision.id} decision={decision} />
        ))}

        <label className="flex flex-col gap-1.5">
          <span className="label">What are you approving, and on what condition?</span>
          <textarea
            aria-label="Approval"
            value={text}
            rows={3}
            disabled={!live || busy}
            placeholder={SUGGESTED_APPROVAL}
            onChange={(e) => setText(e.target.value)}
            className="rule-box resize-y bg-ground p-2 text-[12.5px] leading-relaxed text-ink placeholder:text-muted-deep"
          />
        </label>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="primary"
            disabled={!live || busy || !text.trim()}
            onClick={() => void interpret(text)}
          >
            Interpret
          </Button>
          <Button disabled={!live || busy} onClick={() => setText(SUGGESTED_APPROVAL)}>
            Use the suggested words
          </Button>
        </div>

        {proposal && (
          <div
            className="rule-box border-l-2 border-l-mint bg-ground p-3"
            aria-label="Approval read-back"
          >
            <pre className="m-0 font-mono text-[11px] leading-relaxed whitespace-pre-wrap text-ink">
              {proposal.read_back}
            </pre>
            <div className="mt-3 flex gap-2">
              <Button variant="primary" disabled={busy} onClick={() => void confirm()}>
                Confirm
              </Button>
              <Button disabled={busy} onClick={() => void reject()}>
                Cancel
              </Button>
            </div>
          </div>
        )}
      </div>
    </Panel>
  );
}
