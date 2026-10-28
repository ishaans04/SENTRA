/**
 * The console must report what the engine said, and nothing else.
 *
 * These tests exist mainly to pin the honesty rules: a rejected control stays
 * visible with its reason, a failed verification is not dressed up as success,
 * and the apply button is unavailable when no safe control exists.
 */

import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import type { ContainmentPlan, Finding } from '../../shared/lib/types';
import { useConsole } from '../../shared/state/store';
import { ContainmentPanel, FindingPanel } from './FindingPanel';

const finding: Finding = {
  id: 'finding-ps001',
  rule_id: 'PS-001',
  title: 'Restricted data can reach external egress via unregistered shared state',
  status: 'open',
  severity: 'critical',
  manifest_version: 'support-estate/v1',
  detected_at_sequence: 12,
  emergence_score: 1,
  risk_factors: [
    {
      id: 'unregistered_bridge',
      label: 'Unregistered shared state on the path',
      present: true,
      weight: 0.25,
      detail: 'Scratchpad is not declared.',
    },
    {
      id: 'cross_agent_composition',
      label: 'Capability is composed across two different actors',
      present: false,
      weight: 0.15,
      detail: 'Same actor on both sides.',
    },
  ],
  policy_basis: 'No path may connect restricted data to an external destination.',
  incident_node_ids: [],
  incident_edge_ids: [],
  incident_path: [
    {
      source: 'Support Agent',
      action: 'read',
      target: 'Fictional CRM',
      role: 'ingest: restricted data enters the population',
      expected_status: 'expected',
      evidence_event_ids: ['p0-ev-01'],
    },
    {
      source: 'Support Agent',
      action: 'write',
      target: 'Unregistered Shared Scratchpad',
      role: 'bridge write',
      expected_status: 'unexpected',
      evidence_event_ids: ['p0-ev-10'],
    },
  ],
  evidence_event_ids: ['p0-ev-01', 'p0-ev-10'],
  explanation: 'Each action is individually permitted.',
  uncertainty: 'HIVE observes reported interactions, not payloads.',
};

const plan: ContainmentPlan = {
  id: 'plan-finding-ps001',
  finding_id: 'finding-ps001',
  manifest_version: 'support-estate/v1',
  recommended_capability_id: 'block-support-scratchpad-write',
  cost_breakdown: {},
  impact: 'Removes every path at a disruption cost of 1.',
  state: 'proposed',
  verification: { attempted: false },
  candidates: [
    {
      capability_id: 'block-support-scratchpad-write',
      label: 'Block Support Agent writes to the unregistered scratchpad',
      cost: 1,
      removes_unsafe_path: true,
      preserves_workflow: true,
      broken_expected_relationships: [],
      viable: true,
      rejection_reason: '',
    },
    {
      capability_id: 'block-support-crm-read',
      label: 'Block Support Agent reads from the CRM',
      cost: 9,
      removes_unsafe_path: true,
      preserves_workflow: false,
      broken_expected_relationships: ['Support Agent--read-->Fictional CRM'],
      viable: false,
      rejection_reason: 'Breaks declared relationships that are currently in use.',
    },
  ],
};

function seed(patch: Partial<ReturnType<typeof useConsole.getState>>) {
  useConsole.setState({
    findings: [finding],
    plans: [plan],
    selectedFindingId: finding.id,
    ...patch,
  });
}

beforeEach(() => {
  useConsole.setState({
    findings: [],
    plans: [],
    selectedFindingId: null,
    busy: false,
    state: null,
  });
});

describe('FindingPanel', () => {
  it('states what the finding does not establish', () => {
    seed({});
    render(<FindingPanel />);
    expect(screen.getByText(/does not establish/i)).toBeDefined();
    expect(screen.getByText(/not payloads/i)).toBeDefined();
  });

  it('marks each hop as declared or not, so the composition is the point', () => {
    seed({});
    render(<FindingPanel />);
    expect(screen.getAllByText('declared').length).toBeGreaterThan(0);
    expect(screen.getAllByText('not declared').length).toBeGreaterThan(0);
  });

  it('shows a signal that did not fire rather than hiding it', () => {
    seed({});
    render(<FindingPanel />);
    expect(screen.getByText(/composed across two different actors/i)).toBeDefined();
    expect(screen.getByText('0.00')).toBeDefined();
  });

  it('invites action instead of reporting an error when nothing is wrong', () => {
    render(<FindingPanel />);
    expect(screen.getByText(/Nothing composed yet/i)).toBeDefined();
  });
});

describe('ContainmentPanel', () => {
  it('keeps a rejected control visible with the reason it was rejected', () => {
    seed({});
    render(<ContainmentPanel />);
    expect(screen.getByText(/Block Support Agent reads from the CRM/)).toBeDefined();
    expect(screen.getByText(/Breaks declared relationships/)).toBeDefined();
  });

  it('marks exactly one candidate as recommended', () => {
    seed({});
    render(<ContainmentPanel />);
    expect(screen.getAllByText('recommended')).toHaveLength(1);
  });

  it('offers the control when one is safe', () => {
    seed({});
    render(<ContainmentPanel />);
    expect(screen.getByRole('button', { name: /Apply recommended control/i })).toBeDefined();
  });

  it('refuses to offer an action when no control is safe', () => {
    seed({ plans: [{ ...plan, recommended_capability_id: null }] });
    render(<ContainmentPanel />);
    const button = screen.getByRole('button', { name: /No safe control available/i });
    expect(button.hasAttribute('disabled')).toBe(true);
  });

  it('reports a failed verification as failed', () => {
    seed({
      plans: [
        {
          ...plan,
          state: 'failed',
          verification: {
            attempted: true,
            unsafe_path_removed: false,
            workflow_preserved: true,
            reversible: true,
          },
        },
      ],
    });
    render(<ContainmentPanel />);
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0);
  });
});
