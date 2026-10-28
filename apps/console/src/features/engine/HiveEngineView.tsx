/**
 * The HIVE engine view: the original HIVE console, replaying HIVE's own
 * recorded scenarios (support estate PS-001, software delivery PS-002), with
 * the immunity ladder and the Swarm Lab. It is off the judge path (PRD §13.2)
 * and reached from the view switch in the header.
 */

import { useEffect } from 'react';

import { useConsole } from '../../shared/state/store';
import { Panel, Problem } from '../../shared/ui/primitives';
import { ArchitecturePanel } from '../architecture/ArchitecturePanel';
import { ContainmentPanel, FindingPanel } from '../findings/FindingPanel';
import { ImmunityPanel } from '../immunity/ImmunityPanel';
import { SwarmLab } from '../lab/SwarmLab';
import { EventStream } from '../replay/EventStream';
import { Transport } from '../replay/Transport';
import { TopologyLegend, TopologyMap } from '../topology/TopologyMap';

function ScenarioPicker() {
  const scenarios = useConsole((s) => s.scenarios);
  const scenarioId = useConsole((s) => s.scenarioId);
  const busy = useConsole((s) => s.busy);
  const select = useConsole((s) => s.selectScenario);

  if (scenarios.length < 2) return null;

  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label="Scenario">
      {scenarios.map((scenario) => {
        const active = scenario.id === scenarioId;
        return (
          <button
            key={scenario.id}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={busy}
            onClick={() => void select(scenario.id)}
            title={scenario.summary}
            className={`rounded-[2px] border px-3 py-1.5 text-left transition-colors disabled:opacity-50 ${
              active ? 'border-mint/60 bg-mint/10' : 'border-rule hover:border-ink/25'
            }`}
          >
            <span
              className={`block font-mono text-[10px] tracking-[0.14em] uppercase ${
                active ? 'text-mint' : 'text-muted-deep'
              }`}
            >
              {scenario.rule_id}
            </span>
            <span className={`block text-[12.5px] ${active ? 'text-ink' : 'text-muted'}`}>
              {scenario.name}
            </span>
          </button>
        );
      })}
    </div>
  );
}

export function HiveEngineView() {
  const ready = useConsole((s) => s.ready);
  const problem = useConsole((s) => s.problem);
  const scenario = useConsole((s) => s.scenarios.find((s2) => s2.id === s.scenarioId));
  const dismiss = useConsole((s) => s.dismissProblem);

  useEffect(() => {
    void useConsole.getState().boot();
  }, []);

  return (
    <>
      {!ready && <p className="label">Connecting to the analysis engine</p>}
      {problem && (
        <div className="mb-6">
          <Problem message={problem.message} hint={problem.hint} onDismiss={dismiss} />
        </div>
      )}
      {ready && (
        <>
          {/* Statement of the thesis. One sentence, then straight to evidence. */}
          <section className="mb-8 max-w-[70ch]">
            <h1 className="font-display text-[clamp(28px,4vw,46px)] leading-[1.02] font-semibold tracking-[-0.022em] text-ink-bright uppercase">
              Security for what happens between agents.
            </h1>
            <p className="mt-4 text-[14px] leading-relaxed text-muted">
              Every action below is one its actor is permitted to take. Composed, they form a route
              from restricted customer data to a destination outside the estate that nobody designed
              and no single-agent policy can see. Step through it and watch the moment it closes.
            </p>
          </section>

          <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
            <ScenarioPicker />
            {scenario && (
              <p className="m-0 max-w-[58ch] text-[12.5px] leading-relaxed text-muted-deep">
                {scenario.summary}
              </p>
            )}
          </div>

          <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_400px]">
            {/* Primary column: time, then topology, then the lab. */}
            <div className="flex min-w-0 flex-col gap-6">
              <Panel title="Replay">
                <Transport />
              </Panel>

              <section id="estate" className="rule-box bg-surface" aria-label="Interaction map">
                <header className="flex flex-wrap items-center justify-between gap-4 border-b border-rule-soft px-4 py-3">
                  <h2 className="label !text-muted">Interaction map</h2>
                  <TopologyLegend />
                </header>
                <div className="h-[560px] p-2">
                  <TopologyMap />
                </div>
              </section>

              <ContainmentPanel />

              <SwarmLab />
            </div>

            {/* Secondary column: the decision surface. */}
            <div className="flex min-w-0 flex-col gap-6">
              <FindingPanel />
              <Panel title="Observation ledger" flush>
                <EventStream />
              </Panel>
              <ArchitecturePanel />
              <ImmunityPanel />
            </div>
          </div>
        </>
      )}{' '}
    </>
  );
}
