/**
 * The HAEGIS session snapshot, as `GET /api/state` returns it.
 *
 * These mirror the service's JSON exactly. The console renders them and never
 * derives a decision status, an epoch or a check result of its own.
 */

import type { Architecture, ContainmentPlan, Finding, GraphSnapshot } from './types';

export type DecisionStatus =
  'proposed' | 'active' | 'needs_review' | 'suspended' | 'withdrawn' | 'discarded';
export type RunStatus = 'running' | 'stale' | 'completed' | 'cancelled';
export type ActionStatus = 'queued' | 'held' | 'released' | 'delivered' | 'cancelled';
export type PlanStatus =
  | 'drafted'
  | 'invalid'
  | 'read_back'
  | 'confirmed'
  | 'executing'
  | 'verified'
  | 'verified_with_conflicts'
  | 'failed'
  | 'escalated'
  | 'abandoned';

export interface ConditionView {
  id: string;
  plain: string;
  words: string;
  typed: string;
  last_result: 'HOLDS' | 'FAILS' | 'UNKNOWN' | null;
  witnesses: string[];
}

export interface DecisionView {
  id: string;
  statement: string;
  subject: string;
  actor: string;
  dictated_text: string;
  status: DecisionStatus;
  epoch: number;
  hold_rule: boolean;
  bases: { id: string; conditions: string[]; accepted: boolean }[];
  conditions: ConditionView[];
}

export interface RunView {
  id: string;
  actor: string;
  decision_id: string;
  epoch: number;
  status: RunStatus;
  fresh_context: boolean;
}

export interface ActionView {
  id: string;
  run_id: string;
  decision_id: string;
  tool: string;
  args: Record<string, unknown>;
  status: ActionStatus;
}

export interface RejectedCall {
  event_id: string;
  run_id: string | null;
  tool: string;
  reason: string | null;
}

export interface ItemView {
  id: string;
  resource: string;
  version: number;
  writer: string | null;
  content: string | null;
}

export interface PlanStep {
  kind: string;
  [key: string]: unknown;
}

export interface RecoveryPlanView {
  id: string;
  finding_id: string | null;
  dictated_text: string;
  steps: PlanStep[];
  read_back: string;
  status: PlanStatus;
  interpreted_by: 'gemini' | 'groq' | 'grammar' | 'recorded';
  errors: string[];
  revision: string;
}

export interface StepResultView {
  event_id: string;
  plan_id: string;
  index: number;
  kind: 'succeeded' | 'conflict' | 'failed' | 'escalated';
  step: PlanStep;
  detail?: string;
  evidence?: Record<string, unknown>;
}

export interface ConflictView {
  id: string;
  plan_id: string;
  item: string;
  detail: string;
  status: 'open' | 'keep_human' | 'leave_for_review';
}

export interface CheckView {
  event_id: string;
  plan_id: string;
  name: string;
  passed: boolean;
  detail: string;
}

export interface AlertView {
  event_id: string;
  decision_id: string | null;
  finding_id: string;
  text: string;
  held_actions: string[];
}

export interface FinalRecord {
  plan_id: string;
  status: PlanStatus;
  approval: {
    id: string;
    statement: string;
    dictated_text: string;
    conditions: { id: string; plain: string }[];
  } | null;
  finding: { id: string; rule_id: string; title: string; cited_events: string[] } | null;
  plan: { dictated_text: string; read_back: string; interpreted_by: string; controls: string[] };
  summary: string[];
  conflicts: string[];
  checks: { name: string; passed: boolean; detail: string }[];
}

export interface Snapshot {
  session_id: string;
  labels: { data: string; mode: string };
  manifest_version: string;
  beat: number;
  at_end: boolean;
  storyline: { n: number; title: string; done: boolean }[];
  architecture: Architecture;
  graph: GraphSnapshot;
  applied_controls: string[];
  findings: (Finding & { plan: ContainmentPlan })[];
  alerts: AlertView[];
  decisions: DecisionView[];
  runs: RunView[];
  actions: ActionView[];
  rejected_calls: RejectedCall[];
  items: ItemView[];
  plans: RecoveryPlanView[];
  steps: StepResultView[];
  conflicts: ConflictView[];
  checks: CheckView[];
  record: FinalRecord | null;
  deliveries: Record<string, unknown>[];
  last_seq: number;
}

export interface LedgerEvent {
  seq: number;
  event_id: string;
  session_id: string;
  at: string;
  kind: string;
  producer: string;
  actor: string | null;
  run_id: string | null;
  decision_id: string | null;
  epoch: number | null;
  cites: string[];
  payload: Record<string, unknown>;
}

export interface ProposedDecision {
  decision: { id: string; statement: string };
  read_back: string;
  interpreted_by: string;
}
