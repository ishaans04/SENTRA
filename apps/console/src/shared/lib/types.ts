/**
 * The transport contract, mirrored from the core service.
 *
 * These shapes are the same ones `contracts/openapi/hive-core-v1.json`
 * describes, and that document is generated from the running service rather
 * than maintained by hand. If a field here drifts, the contract test in the
 * core fails first.
 */

export type Action =
  'read' | 'write' | 'call' | 'message' | 'delegate' | 'discover' | 'send' | 'execute' | 'block';

export type ExpectedStatus = 'expected' | 'unexpected';
export type Registration = 'expected' | 'unregistered' | 'unknown';
export type Trust = 'internal' | 'untrusted' | 'external';
export type Severity = 'low' | 'medium' | 'high' | 'critical';
export type DataClassification = 'public' | 'internal' | 'restricted';

export interface GraphNode {
  id: string;
  kind: 'agent' | 'store' | 'datasource' | 'tool' | 'api' | 'destination' | 'control_point';
  label: string;
  zone: string;
  data_classification: DataClassification;
  registration: Registration;
  trust: Trust;
  declared: boolean;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  action: Action;
  first_seen: string;
  last_seen: string;
  expected_status: ExpectedStatus;
  observation_count: number;
  evidence_event_ids: string[];
}

export interface GraphSnapshot {
  nodes: GraphNode[];
  edges: GraphEdge[];
  applied_controls: string[];
}

export interface ObservationEvent {
  event_id: string;
  sequence: number;
  occurred_at: string;
  actor: string;
  action: Action;
  target: string;
  context: Record<string, unknown>;
  provenance: Record<string, unknown>;
  result: string;
}

export interface Invariant {
  id: string;
  description: string;
  source_data_class: DataClassification;
  sink_zone: string;
  required_bridge_registration: Registration;
  status: 'prohibited' | 'advisory';
}

export interface InvariantResult {
  invariant: Invariant;
  violated: boolean;
  witness_path: string[];
}

export interface ReplayState {
  scenario_id: string;
  manifest_version: string;
  cursor: number;
  last_sequence: number;
  replayed_events: number;
  total_events: number;
  at_end: boolean;
  graph: GraphSnapshot;
  timeline: ObservationEvent[];
  invariants: InvariantResult[];
  applied_controls: string[];
}

export interface PathStep {
  source: string;
  action: Action;
  target: string;
  role: string;
  expected_status: ExpectedStatus;
  evidence_event_ids: string[];
}

export interface RiskFactor {
  id: string;
  label: string;
  present: boolean;
  weight: number;
  detail: string;
}

export interface Finding {
  id: string;
  rule_id: 'PS-001' | 'PS-002';
  title: string;
  status: 'open' | 'contained';
  severity: Severity;
  manifest_version: string;
  detected_at_sequence: number;
  risk_factors: RiskFactor[];
  emergence_score: number;
  policy_basis: string;
  incident_node_ids: string[];
  incident_edge_ids: string[];
  incident_path: PathStep[];
  evidence_event_ids: string[];
  explanation: string;
  uncertainty: string;
}

export interface ContainmentCandidate {
  capability_id: string;
  label: string;
  cost: number;
  removes_unsafe_path: boolean;
  preserves_workflow: boolean;
  broken_expected_relationships: string[];
  viable: boolean;
  rejection_reason: string;
}

export interface Verification {
  attempted: boolean;
  reason?: string;
  capability_id?: string;
  control_event_ids?: string[];
  unsafe_path_removed?: boolean;
  declared_relationships_before?: string[];
  declared_relationships_after?: string[];
  broken_declared_relationships?: string[];
  workflow_preserved?: boolean;
  reversible?: boolean;
}

export interface ContainmentPlan {
  id: string;
  finding_id: string;
  manifest_version: string;
  candidates: ContainmentCandidate[];
  recommended_capability_id: string | null;
  cost_breakdown: Record<string, number | null>;
  impact: string;
  state: 'proposed' | 'applied' | 'verified' | 'failed';
  verification: Verification;
}

export interface FindingsEnvelope {
  findings: Finding[];
  plans: ContainmentPlan[];
}

export interface Relationship {
  source: string;
  action: Action;
  target: string;
}

export interface ControlCapability {
  id: string;
  type: 'block_edge' | 'quarantine_node';
  label: string;
  source: string | null;
  action: Action | null;
  target: string;
  reversible: boolean;
  cost: number;
  rationale: string;
}

export interface ZoneSpec {
  order?: number;
  label?: string;
  trust?: Trust;
  description?: string;
}

export interface Architecture {
  version: string;
  zones: Record<string, ZoneSpec>;
  nodes: GraphNode[];
  allowed_relationships: Relationship[];
  invariants: Invariant[];
  control_capabilities: ControlCapability[];
}

export interface ImmunityPattern {
  id: string;
  rule_id: 'PS-001' | 'PS-002';
  lifecycle: 'draft' | 'shadow' | 'active';
  title: string;
  abstract_preconditions: string[];
  evidence_basis: string[];
  recommended_control_class: string;
  created_at: string;
  promoted_at: string | null;
}

export interface ScenarioDescriptor {
  id: string;
  name: string;
  manifest_id: string;
  rule_id: 'PS-001' | 'PS-002';
  summary: string;
  event_count: number;
}

export interface SwarmConfig {
  population: number;
  connectivity: 'restricted' | 'normal' | 'open';
  shared_memory: 'off' | 'limited' | 'enabled';
  delegation: 'restricted' | 'normal' | 'recursive';
  external_access: 'none' | 'limited' | 'broad';
  perturbation:
    | 'none'
    | 'unregistered_shared_resource'
    | 'cross_agent_execution'
    | 'delegation_cascade'
    | 'new_external_endpoint';
}

export interface SwarmResult {
  config: SwarmConfig;
  outcome: 'risk_detected' | 'no_composition_found';
  population: {
    agents: number;
    resources: number;
    observations: number;
    relationships: number;
    undeclared_relationships: number;
  };
  findings: Finding[];
  plans: ContainmentPlan[];
  interpretation: string;
  determinism: { seed: number; note: string };
}

export interface Health {
  status: string;
  version: string;
  mode: string;
  safety: {
    network_egress: boolean;
    real_data: boolean;
    enforcement: string;
  };
}
