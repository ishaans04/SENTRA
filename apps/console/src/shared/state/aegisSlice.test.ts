import { beforeEach, describe, expect, it } from 'vitest';

import type { LedgerEvent, Snapshot } from '../lib/aegisTypes';
import { currentPlan, useAegis } from './aegisSlice';

function event(seq: number, kind: string, extra: Partial<LedgerEvent> = {}): LedgerEvent {
  return {
    seq,
    event_id: `ev-${seq}`,
    session_id: 's',
    at: '2026-10-28T10:00:00Z',
    kind,
    producer: 'aegis',
    actor: null,
    run_id: null,
    decision_id: null,
    epoch: null,
    cites: [],
    payload: {},
    ...extra,
  };
}

const snapshot = {
  session_id: 's',
  decisions: [{ id: 'D-1', status: 'active', epoch: 1 }],
  plans: [],
} as unknown as Snapshot;

describe('aegis store', () => {
  beforeEach(() => {
    useAegis.setState({ snapshot, ledger: [], lastSeq: 0, mode: 'live' });
  });

  it('applies decision.suspended', () => {
    useAegis
      .getState()
      .applyEvent(
        event(4, 'decision.suspended', { decision_id: 'D-1', payload: { new_epoch: 2 } }),
      );
    const d1 = useAegis.getState().snapshot?.decisions[0];
    expect(d1?.status).toBe('suspended');
    expect(d1?.epoch).toBe(2);
  });

  it('ignores a duplicate event id', () => {
    const store = useAegis.getState();
    expect(store.applyEvent(event(1, 'session.seeded'))).toBe(true);
    expect(store.applyEvent(event(2, 'gateway.call'))).toBe(true);
    expect(useAegis.getState().applyEvent(event(2, 'gateway.call'))).toBe(false);
    expect(useAegis.getState().applyEvent(event(1, 'session.seeded'))).toBe(false);
    expect(useAegis.getState().ledger.map((e) => e.seq)).toEqual([1, 2]);
  });

  it('picks the newest plan that was not abandoned', () => {
    const plans = [
      { id: 'P-1', status: 'abandoned' },
      { id: 'P-2', status: 'read_back' },
    ];
    expect(currentPlan({ ...snapshot, plans } as unknown as Snapshot)?.id).toBe('P-2');
    expect(currentPlan(null)).toBeNull();
  });
});
