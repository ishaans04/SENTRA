/**
 * The console shell.
 *
 * Layout follows the order an operator actually works in: what am I looking at
 * and is it safe, where in time am I, what does the estate look like now, what
 * is wrong, and what should I do. The map gets the most space because it is the
 * argument; everything else supports it.
 */

import { useEffect } from 'react';

import { ArchitecturePanel } from '../features/architecture/ArchitecturePanel';
import { ContainmentPanel, FindingPanel } from '../features/findings/FindingPanel';
import { ImmunityPanel } from '../features/immunity/ImmunityPanel';
import { SwarmLab } from '../features/lab/SwarmLab';
import { EventStream } from '../features/replay/EventStream';
import { Transport } from '../features/replay/Transport';
import { TopologyLegend, TopologyMap } from '../features/topology/TopologyMap';
import { PRODUCT_NAME, PRODUCT_TAGLINE } from '../shared/lib/brand';
import { useConsole } from '../shared/state/store';
import { Panel, Pill, Problem } from '../shared/ui/primitives';

function SourceBadge() {
  const source = useConsole((s) => s.source);
  if (!source) return null;
  return (
    <Pill tone={source === 'live' ? 'mint' : 'neutral'}>
      {source === 'live' ? 'live engine' : 'recorded session'}
    </Pill>
  );
}

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

export function App() {
  const ready = useConsole((s) => s.ready);
  const problem = useConsole((s) => s.problem);
  const source = useConsole((s) => s.source);
  const scenario = useConsole((s) => s.scenarios.find((s2) => s2.id === s.scenarioId));
  const state = useConsole((s) => s.state);
  const dismiss = useConsole((s) => s.dismissProblem);

  useEffect(() => {
    void useConsole.getState().boot();
  }, []);

  return (
    <div className="min-h-screen bg-ground">
      <a
        href="#estate"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-[2px] focus:bg-mint focus:px-3 focus:py-2 focus:font-mono focus:text-[11px] focus:text-ground"
      >
        Skip to the interaction map
      </a>

      {/* Standing safety statement. It is a fact about the system, so it is a
          permanent part of the chrome rather than a dismissible notice. */}
      <div className="border-b border-amber/25 bg-amber/[0.06]">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-3 gap-y-1 px-6 py-2">
          <span aria-hidden className="size-1.5 bg-amber" />
          <p className="m-0 font-mono text-[10.5px] tracking-[0.1em] text-amber">
            Simulated environment. Fictional data. No system is contacted and every control is
            simulated.
          </p>
        </div>
      </div>

      <header className="sticky top-0 z-40 border-b border-rule bg-ground/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3">
          {/* The wordmark returns to the overview, which is the page above this one. */}
          <a
            href="../"
            className="font-display text-[15px] font-semibold tracking-[0.24em] text-ink-bright transition-colors hover:text-mint"
          >
            {PRODUCT_NAME}
          </a>
          <span className="hidden max-w-[16rem] font-mono text-[10.5px] leading-tight text-muted-deep sm:block">
            {PRODUCT_TAGLINE}
          </span>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            {state && (
              <span className="tabular hidden text-[10.5px] text-muted-deep md:inline">
                {state.manifest_version}
              </span>
            )}
            <SourceBadge />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1680px] px-6 py-8">
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
                Every action below is one its actor is permitted to take. Composed, they form a
                route from restricted customer data to a destination outside the estate that nobody
                designed and no single-agent policy can see. Step through it and watch the moment it
                closes.
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
        )}
      </main>

      <footer className="mt-4 border-t border-rule">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-3 px-6 py-5">
          <p className="m-0 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-deep">
            HIVE reports risky system states and deviations from a declared architecture. It does
            not determine intent, and it never concludes that an agent is malicious.
            {source === 'recorded' &&
              ' This page is replaying output recorded from the analysis engine; run the core service locally to drive it live.'}
          </p>
          <span className="label">TLN Cybersecurity Challenge 2026</span>
        </div>
      </footer>
    </div>
  );
}
