import { render, screen, within } from '@testing-library/react';
import { beforeEach, describe, expect, it } from 'vitest';

import type { Snapshot } from '../../shared/lib/aegisTypes';
import { useAegis } from '../../shared/state/aegisSlice';
import { ApprovalsPanel } from './ApprovalsPanel';

const suspended = {
  session_id: 's',
  decisions: [
    {
      id: 'D-1',
      statement: 'Reporting may proceed',
      subject: 'Reporting',
      actor: 'reporting-agent',
      dictated_text: 'Approve reporting...',
      status: 'suspended',
      epoch: 2,
      hold_rule: true,
      bases: [{ id: 'B-2', conditions: ['C-1'], accepted: false }],
      conditions: [
        {
          id: 'C-1',
          plain: 'this agent receives only sanitized summaries',
          words: 'Reporting Agent only reads from Approved summaries',
          typed: 'ReadsOnlyFrom(reporting-agent, [report_store/approved_summaries])',
          last_result: 'FAILS',
          witnesses: ['ev-000017'],
        },
      ],
    },
  ],
  runs: [
    {
      id: 'R-1',
      actor: 'reporting-agent',
      decision_id: 'D-1',
      epoch: 1,
      status: 'stale',
      fresh_context: false,
    },
  ],
  actions: [
    {
      id: 'A-1',
      run_id: 'R-1',
      decision_id: 'D-1',
      tool: 'webhook.send_report',
      args: { item: 'draft-1' },
      status: 'held',
    },
  ],
  rejected_calls: [
    { event_id: 'ev-000021', run_id: 'R-1', tool: 'webhook.send_report', reason: 'stale_epoch' },
  ],
  alerts: [
    {
      event_id: 'ev-000020',
      decision_id: 'D-1',
      finding_id: 'F',
      held_actions: ['A-1'],
      text: 'Reporting was approved on the condition that this agent receives only sanitized summaries.',
    },
  ],
  plans: [],
} as unknown as Snapshot;

describe('ApprovalsPanel', () => {
  beforeEach(() => {
    useAegis.setState({ snapshot: suspended, proposal: null, mode: 'live', busy: false });
  });

  it('shows Suspended at epoch 2', () => {
    render(<ApprovalsPanel />);
    const card = screen.getByRole('article', { name: 'Approval D-1' });
    expect(within(card).getByText('suspended')).toBeInTheDocument();
    expect(within(card).getByText('epoch 2')).toBeInTheDocument();
    expect(within(card).getByText('held')).toBeInTheDocument();
    expect(within(card).getByText('stale_epoch')).toBeInTheDocument();
    expect(within(card).getByText(/ReadsOnlyFrom\(reporting-agent/)).toBeInTheDocument();
    expect(within(card).getByText(/approved on the condition/)).toBeInTheDocument();
  });

  it('confirm disabled until read-back shown', () => {
    const { rerender } = render(<ApprovalsPanel />);
    expect(screen.queryByRole('button', { name: 'Confirm' })).not.toBeInTheDocument();
    useAegis.setState({
      proposal: {
        decision: { id: 'D-2', statement: 'Reporting may proceed' },
        read_back: 'I will record this approval: Reporting may proceed.',
        interpreted_by: 'grammar',
      },
    });
    rerender(<ApprovalsPanel />);
    expect(screen.getByLabelText('Approval read-back')).toHaveTextContent(
      'I will record this approval',
    );
    expect(screen.getByRole('button', { name: 'Confirm' })).toBeEnabled();
  });

  it('is read-only in a recorded replay', () => {
    useAegis.setState({ mode: 'recorded' });
    render(<ApprovalsPanel />);
    expect(screen.getByRole('textbox', { name: 'Approval' })).toBeDisabled();
  });
});
