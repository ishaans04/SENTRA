/**
 * The declared architecture.
 *
 * This panel exists to make one thing unmistakable: HIVE is measuring observed
 * behaviour against something a person wrote down, not against a statistical
 * notion of normal. Everything here came from the manifest. If a relationship
 * is missing from this list, that is a decision someone made, and it is the
 * reason a deviation means anything at all.
 */

import { useState } from 'react';

import type { InvariantResult } from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';
import { Panel, Pill } from '../../shared/ui/primitives';

type Tab = 'relationships' | 'invariants' | 'controls';

const TABS: { id: Tab; label: string }[] = [
  { id: 'relationships', label: 'Permitted' },
  { id: 'invariants', label: 'Invariants' },
  { id: 'controls', label: 'Controls' },
];

function Invariants({ results }: { results: InvariantResult[] }) {
  if (!results.length) {
    return <p className="m-0 text-[12.5px] text-muted">This manifest declares no invariants.</p>;
  }
  return (
    <ul className="m-0 list-none p-0">
      {results.map(({ invariant, violated, witness_path }) => (
        <li key={invariant.id} className="border-b border-rule-soft py-3 last:border-0">
          <div className="flex items-start justify-between gap-3">
            <span className="font-mono text-[11.5px] text-ink">{invariant.id}</span>
            <Pill tone={violated ? 'red' : 'mint'}>{violated ? 'violated' : 'holding'}</Pill>
          </div>
          <p className="m-0 mt-1.5 text-[12px] leading-relaxed text-muted">
            {invariant.description}
          </p>
          {violated && witness_path.length > 0 && (
            <div className="mt-2 rule-box border-red/30 bg-red/5 p-2">
              <span className="label !text-red">Witness</span>
              <p className="m-0 mt-1 font-mono text-[11px] leading-relaxed break-words text-ink-soft">
                {witness_path.join('  →  ')}
              </p>
            </div>
          )}
        </li>
      ))}
    </ul>
  );
}

export function ArchitecturePanel() {
  const architecture = useConsole((s) => s.architecture);
  const state = useConsole((s) => s.state);
  const [tab, setTab] = useState<Tab>('relationships');

  if (!architecture) return null;

  const observed = new Set((state?.graph.edges ?? []).map((edge) => edge.id));

  return (
    <Panel
      title="Declared architecture"
      aside={<span className="label">{architecture.version}</span>}
      flush
    >
      <div className="flex gap-1 border-b border-rule-soft px-4 pt-3" role="tablist">
        {TABS.map((entry) => (
          <button
            key={entry.id}
            type="button"
            role="tab"
            aria-selected={tab === entry.id}
            onClick={() => setTab(entry.id)}
            className={`-mb-px border-b px-2.5 pb-2 font-mono text-[10px] tracking-[0.16em] uppercase transition-colors ${
              tab === entry.id
                ? 'border-mint text-mint'
                : 'border-transparent text-muted-deep hover:text-muted'
            }`}
          >
            {entry.label}
          </button>
        ))}
      </div>

      <div className="max-h-[300px] overflow-y-auto p-4">
        {tab === 'relationships' && (
          <ul className="m-0 list-none p-0">
            {architecture.allowed_relationships.map((relationship) => {
              const key = `${relationship.source}--${relationship.action}-->${relationship.target}`;
              const live = observed.has(key);
              return (
                <li
                  key={key}
                  className="flex items-baseline gap-2 border-b border-rule-soft py-2 font-mono text-[11px] last:border-0"
                >
                  <span
                    aria-hidden
                    className={`size-1.5 shrink-0 rounded-full ${live ? 'bg-mint' : 'bg-rule'}`}
                  />
                  <span className={live ? 'text-ink' : 'text-muted-deep'}>
                    {relationship.source}
                  </span>
                  <span className="text-muted-deep">{relationship.action}</span>
                  <span className={live ? 'text-ink' : 'text-muted-deep'}>
                    {relationship.target}
                  </span>
                  <span className="label ml-auto shrink-0 !tracking-[0.1em]">
                    {live ? 'in use' : 'idle'}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        {tab === 'invariants' && <Invariants results={state?.invariants ?? []} />}

        {tab === 'controls' && (
          <ul className="m-0 list-none p-0">
            {architecture.control_capabilities.map((capability) => (
              <li key={capability.id} className="border-b border-rule-soft py-3 last:border-0">
                <div className="flex items-start justify-between gap-3">
                  <span className="text-[12.5px] leading-snug text-ink">{capability.label}</span>
                  <span className="tabular shrink-0 text-[11px] text-muted">
                    cost {capability.cost}
                  </span>
                </div>
                <p className="m-0 mt-1 text-[11.5px] leading-relaxed text-muted-deep">
                  {capability.rationale}
                </p>
              </li>
            ))}
            <li className="pt-3">
              <p className="m-0 text-[11.5px] leading-relaxed text-muted-deep">
                HIVE may propose only what appears here. It cannot invent an action, and it has no
                general kill switch.
              </p>
            </li>
          </ul>
        )}
      </div>
    </Panel>
  );
}
