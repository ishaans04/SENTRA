/**
 * The finding inspector.
 *
 * Reading order is deliberate, and it is the order a reviewer needs rather than
 * the order the data arrives in:
 *
 *   1. what was composed, hop by hop, with each hop marked declared or not
 *   2. which signals fired, with the weight each contributed
 *   3. what the engine will not claim
 *   4. which pre-authorised actions were evaluated, and why each was kept or
 *      rejected
 *   5. what applying the recommendation actually verified
 *
 * The candidate table is the argument that HIVE reasons rather than reacts: the
 * two rejected controls both remove the path, and are rejected anyway because
 * they sever work the architecture declares.
 */

import type {
  ContainmentPlan,
  Finding,
  PathStep,
  RiskFactor,
  Verification,
} from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';
import { Button, Contribution, Empty, Panel, Pill, SeverityPill } from '../../shared/ui/primitives';

// ---------------------------------------------------------------------------

function PathTrace({ path }: { path: PathStep[] }) {
  return (
    <ol className="m-0 list-none p-0">
      {path.map((step, index) => {
        const declared = step.expected_status === 'expected';
        return (
          <li key={`${step.source}-${step.action}-${step.target}`} className="relative pl-6">
            {index < path.length - 1 && (
              <span
                aria-hidden
                className="absolute top-[18px] bottom-0 left-[5px] w-px bg-gradient-to-b from-red/60 to-red/20"
              />
            )}
            <span
              aria-hidden
              className={`absolute top-[11px] left-0 size-[11px] rounded-full border-2 ${
                declared ? 'border-muted-deep bg-surface' : 'border-amber bg-surface'
              }`}
            />
            <div className="border-b border-rule-soft py-2.5 last:border-0">
              <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1 font-mono text-[11.5px]">
                <span className="text-ink">{step.source}</span>
                <span className="text-red">{step.action}</span>
                <span className="text-ink">{step.target}</span>
                <span
                  className={`ml-auto shrink-0 text-[9.5px] tracking-[0.12em] uppercase ${
                    declared ? 'text-muted-deep' : 'text-amber'
                  }`}
                >
                  {declared ? 'declared' : 'not declared'}
                </span>
              </div>
              <p className="m-0 mt-1 text-[12px] leading-snug text-muted">{step.role}</p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

// ---------------------------------------------------------------------------

function RiskFactors({ factors, score }: { factors: RiskFactor[]; score: number }) {
  return (
    <div>
      <ul className="m-0 list-none p-0">
        {factors.map((factor) => (
          <li
            key={factor.id}
            className="flex items-start gap-3 border-b border-rule-soft py-2.5 last:border-0"
          >
            <Contribution weight={factor.weight} present={factor.present} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-3">
                <span
                  className={`text-[12.5px] ${factor.present ? 'text-ink' : 'text-muted-deep'}`}
                >
                  {factor.label}
                </span>
                <span
                  className={`tabular shrink-0 text-[10.5px] ${
                    factor.present ? 'text-red' : 'text-muted-deep/60'
                  }`}
                >
                  {factor.present ? `+${factor.weight.toFixed(2)}` : '0.00'}
                </span>
              </div>
              <p className="m-0 mt-0.5 text-[11.5px] leading-snug text-muted-deep">
                {factor.detail}
              </p>
            </div>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex items-baseline justify-between border-t border-rule pt-3">
        <span className="label">Emergence score</span>
        <span className="tabular text-[13px] text-red">{score.toFixed(2)} / 1.00</span>
      </div>
      <p className="m-0 mt-2 text-[11.5px] leading-relaxed text-muted-deep">
        Weights are fixed and sum to one, so the total is reconstructible by hand. The score ranks
        findings; the factors above are what explain them.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------

function Candidates({ plan }: { plan: ContainmentPlan }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <caption className="sr-only">
          Every pre-authorised control, evaluated against the current graph
        </caption>
        <thead>
          <tr className="border-b border-rule">
            {['Control', 'Cost', 'Removes path', 'Preserves work', ''].map((heading, index) => (
              <th
                key={heading || index}
                scope="col"
                className={`label pb-2 font-normal ${index > 0 ? 'text-center' : ''}`}
              >
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {plan.candidates.map((candidate) => {
            const recommended = candidate.capability_id === plan.recommended_capability_id;
            return (
              <tr
                key={candidate.capability_id}
                className={`border-b border-rule-soft align-top last:border-0 ${
                  recommended ? 'bg-mint/[0.05]' : ''
                }`}
              >
                <th scope="row" className="py-2.5 pr-3 font-normal">
                  <span
                    className={`block text-[12.5px] leading-snug ${
                      candidate.viable ? 'text-ink' : 'text-muted'
                    }`}
                  >
                    {candidate.label}
                  </span>
                  {!candidate.viable && candidate.rejection_reason && (
                    <span className="mt-1 block text-[11.5px] leading-snug text-amber/80">
                      {candidate.rejection_reason}
                    </span>
                  )}
                </th>
                <td className="tabular px-2 py-2.5 text-center text-[11.5px] text-muted">
                  {candidate.cost}
                </td>
                <td className="px-2 py-2.5 text-center">
                  <Mark ok={candidate.removes_unsafe_path} />
                </td>
                <td className="px-2 py-2.5 text-center">
                  <Mark ok={candidate.preserves_workflow} />
                </td>
                <td className="py-2.5 pl-2 text-right">
                  {recommended && <Pill tone="mint">recommended</Pill>}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Mark({ ok }: { ok: boolean }) {
  return (
    <span className={`font-mono text-[12px] ${ok ? 'text-mint' : 'text-muted-deep'}`}>
      <span className="sr-only">{ok ? 'yes' : 'no'}</span>
      <span aria-hidden>{ok ? '●' : '○'}</span>
    </span>
  );
}

// ---------------------------------------------------------------------------

function VerificationReport({ verification }: { verification: Verification }) {
  if (!verification.attempted) {
    return <p className="m-0 text-[12.5px] leading-relaxed text-amber">{verification.reason}</p>;
  }
  const rows: [string, boolean][] = [
    ['Composed path removed', verification.unsafe_path_removed ?? false],
    ['Declared work preserved', verification.workflow_preserved ?? false],
    ['Action is reversible', verification.reversible ?? false],
  ];
  return (
    <div>
      <ul className="m-0 list-none p-0">
        {rows.map(([label, ok]) => (
          <li
            key={label}
            className="flex items-center justify-between border-b border-rule-soft py-2 last:border-0"
          >
            <span className="text-[12.5px] text-ink-soft">{label}</span>
            <span className={`font-mono text-[11px] ${ok ? 'text-mint' : 'text-red'}`}>
              {ok ? 'verified' : 'failed'}
            </span>
          </li>
        ))}
      </ul>
      <p className="m-0 mt-3 text-[11.5px] leading-relaxed text-muted-deep">
        Measured after the control was issued, by re-running the rules over the contained graph —
        not by trusting what the planner predicted.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------

export function ContainmentPanel() {
  const findings = useConsole((s) => s.findings);
  const plans = useConsole((s) => s.plans);
  const selectedId = useConsole((s) => s.selectedFindingId);
  const busy = useConsole((s) => s.busy);
  const applyPlan = useConsole((s) => s.applyPlan);

  const finding = findings.find((f) => f.id === selectedId) ?? findings[0];
  const plan =
    plans.find((entry) => entry.finding_id === finding?.id) ??
    plans.find((entry) => entry.state === 'verified');

  if (!plan) return null;
  const applied = plan.state === 'verified' || plan.state === 'applied';

  return (
    <Panel
      title="Containment"
      tone={applied ? 'resolved' : 'neutral'}
      aside={<Pill tone={applied ? 'mint' : 'neutral'}>{plan.state}</Pill>}
    >
      <p className="m-0 mb-4 max-w-[86ch] text-[13px] leading-relaxed text-ink-soft">
        {plan.impact}
      </p>

      <Candidates plan={plan} />

      {plan.verification.attempted ? (
        <div className="mt-5 grid gap-5 border-t border-rule pt-4 md:grid-cols-2">
          <VerificationReport verification={plan.verification} />
          <div>
            <span className="label">Declared relationships after containment</span>
            <ul className="m-0 mt-2 list-none p-0">
              {(plan.verification.declared_relationships_after ?? []).map((relationship) => (
                <li key={relationship} className="py-[2px] font-mono text-[11px] text-mint">
                  {relationship}
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : (
        <div className="mt-5 flex flex-wrap items-center gap-3 border-t border-rule pt-4">
          <Button
            variant="danger"
            disabled={busy || !plan.recommended_capability_id}
            onClick={() => void applyPlan(plan.id)}
          >
            {plan.recommended_capability_id
              ? 'Apply recommended control'
              : 'No safe control available'}
          </Button>
          <span className="text-[11.5px] leading-snug text-muted-deep">
            Simulated. Nothing outside this process is contacted.
          </span>
        </div>
      )}
    </Panel>
  );
}

export function FindingPanel() {
  const findings = useConsole((s) => s.findings);
  const plans = useConsole((s) => s.plans);
  const selectedId = useConsole((s) => s.selectedFindingId);
  const state = useConsole((s) => s.state);

  const finding: Finding | undefined = findings.find((f) => f.id === selectedId) ?? findings[0];

  // A plan whose finding has gone is the record of a containment that worked.
  const resolved = plans.find(
    (plan) => plan.state === 'verified' && !findings.some((f) => f.id === plan.finding_id),
  );

  if (!finding) {
    if (resolved) {
      return (
        <Panel title="Containment verified" tone="resolved">
          <p className="m-0 text-[13px] leading-relaxed text-ink-soft">{resolved.impact}</p>
          <div className="mt-4">
            <VerificationReport verification={resolved.verification} />
          </div>
          <div className="mt-4 border-t border-rule pt-3">
            <span className="label">Severed</span>
            <ul className="m-0 mt-2 list-none p-0">
              {(state?.applied_controls ?? []).map((control) => (
                <li key={control} className="tabular text-[11px] text-mint">
                  {control}
                </li>
              ))}
            </ul>
          </div>
        </Panel>
      );
    }
    return (
      <Panel title="Detection">
        <Empty
          title="Nothing composed yet."
          body="The rules are running against every event as it arrives. Advance the replay to watch the estate change, and to see whether a path forms that the architecture forbids."
        />
      </Panel>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <Panel
        title={`${finding.rule_id} · finding`}
        tone="alert"
        aside={<SeverityPill severity={finding.severity} />}
      >
        <h3 className="mb-3 font-display text-[19px] leading-tight text-ink-bright">
          {finding.title}
        </h3>
        <p className="m-0 text-[13px] leading-relaxed text-ink-soft">{finding.explanation}</p>

        <div className="mt-4 border-t border-rule pt-3">
          <span className="label">Policy basis</span>
          <p className="m-0 mt-1.5 font-mono text-[11.5px] leading-relaxed text-mint">
            {finding.policy_basis}
          </p>
        </div>

        <div className="mt-4 border-t border-rule pt-3">
          <span className="label">What this does not establish</span>
          <p className="m-0 mt-1.5 text-[12px] leading-relaxed text-muted">{finding.uncertainty}</p>
        </div>
      </Panel>

      <Panel
        title="Composed path"
        aside={<span className="label">{finding.incident_path.length} hops</span>}
      >
        <PathTrace path={finding.incident_path} />
      </Panel>

      <Panel title="Signals" aside={<span className="label">{finding.manifest_version}</span>}>
        <RiskFactors factors={finding.risk_factors} score={finding.emergence_score} />
      </Panel>
    </div>
  );
}
