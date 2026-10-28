/**
 * Swarm Lab.
 *
 * The replay answers "what happened?" for one recorded estate. The lab answers
 * a design question instead: given a population of this size, with these
 * permissions and this much shared state, can a dangerous composition form at
 * all?
 *
 * The answer is worth something because the lab is not scoring topologies with
 * a formula. It synthesises a real manifest, generates a real observation
 * stream, and runs the same rules and the same planner this console uses. The
 * most useful result is usually the negative one, so the panel leads with the
 * interpretation rather than with a number.
 */

import type { SwarmConfig } from '../../shared/lib/types';
import { DEFAULT_LAB, labConstraints, useConsole } from '../../shared/state/store';
import { Button, Choice, Field, Panel, Pill, Problem } from '../../shared/ui/primitives';

const AXES = [
  { key: 'connectivity', label: 'Connectivity', options: ['restricted', 'normal', 'open'] },
  { key: 'shared_memory', label: 'Shared memory', options: ['off', 'limited', 'enabled'] },
  { key: 'delegation', label: 'Delegation', options: ['restricted', 'normal', 'recursive'] },
  { key: 'external_access', label: 'External access', options: ['none', 'limited', 'broad'] },
] as const;

const PERTURBATIONS = [
  'none',
  'unregistered_shared_resource',
  'cross_agent_execution',
  'delegation_cascade',
  'new_external_endpoint',
] as const;

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <div className="label">{label}</div>
      <div className="tabular mt-1 text-[16px] text-ink">{value}</div>
    </div>
  );
}

export function SwarmLab() {
  const config = useConsole((s) => s.labConfig);
  const result = useConsole((s) => s.labResult);
  const running = useConsole((s) => s.labRunning);
  const problem = useConsole((s) => s.labProblem);
  const update = useConsole((s) => s.updateLab);
  const run = useConsole((s) => s.runLab);

  const { held, populations } = labConstraints();
  const isHeld = (key: keyof SwarmConfig) => held.includes(key);

  return (
    <Panel
      title="Swarm Lab"
      aside={
        result ? (
          <span className="tabular text-[10px] text-muted-deep">
            seed {result.determinism.seed.toString(16).slice(0, 10)}
          </span>
        ) : undefined
      }
    >
      <p className="m-0 mb-5 max-w-[68ch] text-[13px] leading-relaxed text-muted">
        Describe a population you are thinking of deploying. The lab builds it, observes it, and
        runs the same detection and containment code as the replay above — so a result here is
        produced by the engine, not estimated about it.
      </p>

      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
        <Field label="Population">
          <Choice
            name="Population"
            options={populations}
            value={config.population}
            onChange={(population) => update({ population })}
          />
        </Field>

        {AXES.map((axis) => (
          <Field key={axis.key} label={isHeld(axis.key) ? `${axis.label} — held` : axis.label}>
            <Choice
              name={axis.label}
              options={axis.options}
              value={config[axis.key] as string}
              disabled={isHeld(axis.key)}
              onChange={(next) => update({ [axis.key]: next } as Partial<SwarmConfig>)}
            />
          </Field>
        ))}

        <Field label="Perturbation">
          <Choice
            name="Perturbation"
            options={PERTURBATIONS}
            value={config.perturbation}
            onChange={(perturbation) => update({ perturbation })}
          />
        </Field>
      </div>

      {held.length > 0 && (
        <p className="m-0 mt-4 text-[11.5px] leading-relaxed text-muted-deep">
          {held.join(' and ')} are held at their defaults in the recorded session — they change the
          texture of a population without changing whether a composition forms. Run the core service
          locally to vary them.
        </p>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-rule pt-4">
        <Button variant="primary" onClick={() => void run()} disabled={running}>
          {running ? 'Running' : 'Run experiment'}
        </Button>
        <Button onClick={() => update(DEFAULT_LAB)} disabled={running}>
          Reset
        </Button>
        <span className="text-[11.5px] text-muted-deep">
          The same settings always produce the same population and the same conclusion.
        </span>
      </div>

      {problem && (
        <div className="mt-4">
          <Problem message={problem.message} hint={problem.hint} />
        </div>
      )}

      {result && (
        <div className="mt-5 border-t border-rule pt-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <h3 className="font-display text-[15px] text-ink-bright">
              {result.outcome === 'risk_detected'
                ? 'A composition formed.'
                : 'No composition formed.'}
            </h3>
            <Pill tone={result.outcome === 'risk_detected' ? 'red' : 'mint'}>
              {result.outcome === 'risk_detected'
                ? `${result.findings.map((f) => f.rule_id).join(', ')}`
                : 'nothing to contain'}
            </Pill>
          </div>

          <p className="m-0 mt-2 max-w-[72ch] text-[13px] leading-relaxed text-ink-soft">
            {result.interpretation}
          </p>

          <div className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-5">
            <Stat label="Agents" value={result.population.agents} />
            <Stat label="Resources" value={result.population.resources} />
            <Stat label="Observations" value={result.population.observations} />
            <Stat label="Relationships" value={result.population.relationships} />
            <Stat label="Undeclared" value={result.population.undeclared_relationships} />
          </div>

          {result.findings.map((finding) => {
            const plan = result.plans.find((entry) => entry.finding_id === finding.id);
            return (
              <div key={finding.id} className="mt-5 rule-box border-red/30 bg-red/[0.04] p-4">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <span className="font-mono text-[11px] text-red">{finding.rule_id}</span>
                  <span className="tabular text-[11px] text-muted">
                    emergence {finding.emergence_score.toFixed(2)}
                  </span>
                </div>
                <p className="m-0 mt-2 text-[12.5px] leading-relaxed text-ink-soft">
                  {finding.explanation}
                </p>
                {plan?.recommended_capability_id && (
                  <p className="m-0 mt-3 border-t border-rule pt-3 font-mono text-[11px] text-mint">
                    recommends {plan.recommended_capability_id}
                    <span className="text-muted-deep">
                      {' '}
                      — {plan.candidates.filter((c) => c.viable).length} of {plan.candidates.length}{' '}
                      controls viable
                    </span>
                  </p>
                )}
              </div>
            );
          })}
        </div>
      )}
    </Panel>
  );
}
