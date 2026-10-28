/**
 * The judge path (PRD §13.2, §13.8): one visitor's live sandbox.
 *
 * The map is HIVE's, drawn from this session's graph; the red path is exactly
 * the route the finding names. Approvals and Recovery sit beside it, the alert
 * under it, and the ledger shows every call, rejected ones included.
 */

import { useEffect } from 'react';

import { useEventStream } from '../../shared/api/useEventStream';
import { useAegis } from '../../shared/state/aegisSlice';
import { Panel, Problem } from '../../shared/ui/primitives';
import { ApprovalsPanel } from '../approvals/ApprovalsPanel';
import { AlertBanner } from '../recovery/AlertBanner';
import { RecoveryPanel } from '../recovery/RecoveryPanel';
import { LedgerTable } from '../story/LedgerTable';
import { StoryControls } from '../story/StoryControls';
import { TopologyCanvas, TopologyLegend } from '../topology/TopologyMap';

export function HaegisView() {
  const mode = useAegis((s) => s.mode);
  const snapshot = useAegis((s) => s.snapshot);
  const problem = useAegis((s) => s.problem);
  const dismiss = useAegis((s) => s.dismissProblem);

  useEffect(() => {
    void useAegis.getState().boot();
  }, []);
  useEventStream(mode === 'live' ? (snapshot?.session_id ?? null) : null);

  const finding = snapshot?.findings[0] ?? null;

  return (
    <>
      <section className="mb-6 max-w-[78ch]">
        <h1 className="font-display text-[clamp(26px,3.4vw,40px)] leading-[1.05] font-semibold tracking-[-0.02em] text-ink-bright uppercase">
          When the reason for an approval stops being true.
        </h1>
        <p className="mt-3 text-[14px] leading-relaxed text-muted">
          Approve the reporting agent on a condition. Watch HIVE find a route nobody declared, the
          approval behind the run fall away, and the gateway hold and reject its calls. Then tell
          AEGIS how to recover, in your own words, and check what it actually did. Dictate with
          Wispr Flow or type: both work.
        </p>
      </section>

      {mode === 'connecting' && <p className="label">Starting your sandbox</p>}
      {mode === 'recorded' && (
        <p className="mb-6 text-[13px] text-amber">
          The live sandbox is not reachable from here. The recorded replay of this storyline plays
          the same events with commands disabled.
        </p>
      )}
      {problem && (
        <div className="mb-6">
          <Problem message={problem} onDismiss={dismiss} />
        </div>
      )}

      {snapshot && (
        <div className="flex flex-col gap-6">
          <Panel title="Storyline">
            <StoryControls />
          </Panel>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_420px]">
            <div className="flex min-w-0 flex-col gap-6">
              <section id="estate" className="rule-box bg-surface" aria-label="Interaction map">
                <header className="flex flex-wrap items-center justify-between gap-4 border-b border-rule-soft px-4 py-3">
                  <h2 className="label !text-muted">
                    Interaction map
                    {finding && (
                      <span className="ml-3 !text-red">{finding.rule_id} possible route</span>
                    )}
                  </h2>
                  <TopologyLegend />
                </header>
                <div className="h-[520px] p-2">
                  <TopologyCanvas
                    architecture={snapshot.architecture}
                    graph={snapshot.graph}
                    finding={finding}
                  />
                </div>
              </section>
              <AlertBanner />
              <Panel title="Session ledger" flush>
                <LedgerTable />
              </Panel>
            </div>

            <div className="flex min-w-0 flex-col gap-6">
              <ApprovalsPanel />
              <RecoveryPanel />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
