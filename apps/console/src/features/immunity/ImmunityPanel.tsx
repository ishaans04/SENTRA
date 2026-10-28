/**
 * Immunity memory.
 *
 * After a finding is contained, HIVE records the abstract precondition pattern
 * that produced it — never the node names, so what is remembered transfers to
 * another estate. Patterns enter as drafts and stay there. Promotion to shadow
 * and then active is a person's decision, taken one step at a time, because a
 * system that quietly turns one incident into a standing rule is exactly the
 * opaque behaviour this project argues against.
 */

import type { ImmunityPattern } from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';
import { Button, Empty, Panel, Pill } from '../../shared/ui/primitives';

const STAGES: ImmunityPattern['lifecycle'][] = ['draft', 'shadow', 'active'];

const STAGE_MEANING: Record<ImmunityPattern['lifecycle'], string> = {
  draft: 'Recorded and awaiting review. Takes no part in analysis.',
  shadow: 'Reported when matched, but never acted on.',
  active: 'Matched and acted on under the same containment constraints.',
};

function NextStep({ pattern }: { pattern: ImmunityPattern }) {
  const promote = useConsole((s) => s.promotePattern);
  const next =
    pattern.lifecycle === 'draft' ? 'shadow' : pattern.lifecycle === 'shadow' ? 'active' : null;

  if (!next) {
    return <Button onClick={() => void promote(pattern.id, 'shadow')}>Return to shadow</Button>;
  }
  return (
    <Button variant="primary" onClick={() => void promote(pattern.id, next)}>
      Promote to {next}
    </Button>
  );
}

export function ImmunityPanel() {
  const patterns = useConsole((s) => s.immunity);

  return (
    <Panel
      title="Immunity memory"
      aside={<span className="label">{patterns.length} recorded</span>}
    >
      {!patterns.length ? (
        <Empty
          title="Nothing learned yet."
          body="Contain a finding and HIVE records the abstract pattern behind it here, as a draft for review."
        />
      ) : (
        <ul className="m-0 list-none p-0">
          {patterns.map((pattern) => (
            <li key={pattern.id} className="border-b border-rule pb-4 last:border-0 last:pb-0">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <span className="label">{pattern.rule_id}</span>
                  <h3 className="mt-1 font-display text-[14px] leading-snug text-ink">
                    {pattern.title}
                  </h3>
                </div>
                <Pill tone={pattern.lifecycle === 'active' ? 'mint' : 'neutral'}>
                  {pattern.lifecycle}
                </Pill>
              </div>

              {/* The review ladder, shown as a ladder so the gate is obvious. */}
              <ol className="mt-3 flex list-none items-center gap-1 p-0">
                {STAGES.map((stage, index) => {
                  const reached = STAGES.indexOf(pattern.lifecycle) >= index;
                  return (
                    <li key={stage} className="flex flex-1 items-center gap-1">
                      <span
                        className={`h-[3px] flex-1 ${reached ? 'bg-mint' : 'bg-rule'}`}
                        aria-hidden
                      />
                      <span
                        className={`font-mono text-[9px] tracking-[0.12em] uppercase ${
                          reached ? 'text-mint' : 'text-muted-deep'
                        }`}
                      >
                        {stage}
                      </span>
                    </li>
                  );
                })}
              </ol>
              <p className="m-0 mt-2 text-[11.5px] leading-relaxed text-muted-deep">
                {STAGE_MEANING[pattern.lifecycle]}
              </p>

              <div className="mt-3">
                <span className="label">Preconditions</span>
                <ul className="m-0 mt-1.5 list-none p-0">
                  {pattern.abstract_preconditions.map((precondition) => (
                    <li
                      key={precondition}
                      className="flex gap-2 py-[3px] text-[12px] leading-snug text-muted"
                    >
                      <span aria-hidden className="text-muted-deep">
                        ·
                      </span>
                      {precondition}
                    </li>
                  ))}
                </ul>
              </div>

              <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                <span className="tabular text-[10.5px] text-muted-deep">
                  {pattern.evidence_basis.length} evidence events
                </span>
                <NextStep pattern={pattern} />
              </div>
            </li>
          ))}
        </ul>
      )}
    </Panel>
  );
}
