import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import type { Snapshot } from '../../shared/lib/aegisTypes';
import { useAegis } from '../../shared/state/aegisSlice';
import { RecoveryPanel } from './RecoveryPanel';

const afterRecovery = {
  session_id: 's',
  items: [
    {
      id: 'draft-1',
      resource: 'report_store/drafts',
      version: 2,
      writer: 'teammate',
      content: 'Edited by hand.',
    },
  ],
  plans: [
    {
      id: 'P-1',
      finding_id: 'F',
      dictated_text: 'Stop this reporting run...',
      steps: [],
      read_back: 'I will:\n 1. Cancel reporting run R-1.',
      status: 'verified_with_conflicts',
      interpreted_by: 'grammar',
      errors: [],
    },
  ],
  steps: [
    {
      event_id: 'ev-30',
      plan_id: 'P-1',
      index: 0,
      kind: 'succeeded',
      step: { kind: 'CANCEL_RUN' },
      detail: 'R-1 cancelled.',
    },
    {
      event_id: 'ev-31',
      plan_id: 'P-1',
      index: 3,
      kind: 'conflict',
      step: { kind: 'COMPENSATE' },
      detail: 'draft-1 was changed by teammate.',
    },
  ],
  conflicts: [
    {
      id: 'K-1',
      plan_id: 'P-1',
      item: 'draft-1',
      detail: 'draft-1 was changed by teammate after the agent wrote it.',
      status: 'open',
    },
  ],
  checks: [
    { event_id: 'ev-40', plan_id: 'P-1', name: 'route_closed', passed: true, detail: 'No route.' },
  ],
  record: {
    plan_id: 'P-1',
    status: 'verified_with_conflicts',
    approval: { id: 'D-1', statement: 'Reporting may proceed', dictated_text: '', conditions: [] },
    finding: { id: 'F', rule_id: 'PS-001', title: 't', cited_events: ['ev-1'] },
    plan: {
      dictated_text: '',
      read_back: '',
      interpreted_by: 'grammar',
      controls: ['deny-reporting-scratchpad-read'],
    },
    summary: ['Affected send cancelled.', 'Support work preserved.'],
    conflicts: [
      'draft-1: a person edited it after the agent wrote it. The human version was kept for review.',
    ],
    checks: [],
  },
} as unknown as Snapshot;

describe('RecoveryPanel', () => {
  beforeEach(() => {
    useAegis.setState({ snapshot: afterRecovery, mode: 'live', busy: false });
  });

  it('Ctrl+K focuses Tell AEGIS', () => {
    render(<RecoveryPanel />);
    fireEvent.keyDown(document, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('textbox', { name: 'Tell AEGIS' })).toHaveFocus();
  });

  it('conflict card has no overwrite button', () => {
    render(<RecoveryPanel />);
    const card = screen.getByRole('article', { name: 'Conflict on draft-1' });
    expect(card).toHaveTextContent('Edited by hand.');
    expect(screen.getByRole('button', { name: 'Keep the human version' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Leave for review' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /overwrite/i })).not.toBeInTheDocument();
  });

  it('final record lists the conflict', () => {
    render(<RecoveryPanel />);
    const record = screen.getByRole('region', { name: 'Final record' });
    expect(record).toHaveTextContent('Support work preserved.');
    expect(record).toHaveTextContent('The human version was kept for review.');
  });

  it('shows the honest message for a plan that cannot run', () => {
    useAegis.setState({
      snapshot: {
        ...afterRecovery,
        plans: [
          {
            ...afterRecovery.plans[0],
            status: 'invalid',
            read_back: '',
            errors: ['There is no run R-9.'],
          },
        ],
        steps: [],
        conflicts: [],
        checks: [],
        record: null,
      },
    });
    render(<RecoveryPanel />);
    expect(screen.getByRole('alert')).toHaveTextContent(
      "I can't establish a safe automatic recovery",
    );
    expect(screen.getByRole('alert')).toHaveTextContent('There is no run R-9.');
  });
});
