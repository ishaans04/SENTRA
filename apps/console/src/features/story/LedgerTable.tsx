/**
 * The session ledger, newest first: every gateway call, finding, decision
 * change and recovery step, rejected calls included (INV-4).
 */

import { useAegis } from '../../shared/state/aegisSlice';

function describe(kind: string, payload: Record<string, unknown>): string {
  if (kind === 'gateway.call') {
    const outcome = String(payload.outcome);
    const reason = payload.reason ? ` (${String(payload.reason)})` : '';
    return `${String(payload.tool)} · ${outcome}${reason}`;
  }
  if (kind === 'finding.raised') return `${String(payload.rule_id)} possible route`;
  if (kind.startsWith('action.')) return `${kind.slice(7)} ${String(payload.action_id)}`;
  return kind;
}

export function LedgerTable() {
  const ledger = useAegis((s) => s.ledger);
  const rows = ledger.slice(-80).reverse();
  if (rows.length === 0) {
    return <p className="m-0 p-4 text-[12px] text-muted-deep">No events yet. Press Step.</p>;
  }
  return (
    <div className="max-h-[360px] overflow-auto">
      <table className="w-full border-collapse text-left text-[11.5px]">
        <thead className="sticky top-0 bg-surface">
          <tr className="text-muted-deep">
            <th className="px-3 py-2 font-normal">seq</th>
            <th className="px-3 py-2 font-normal">actor</th>
            <th className="px-3 py-2 font-normal">event</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((event) => {
            const rejected = event.kind === 'gateway.call' && event.payload.outcome === 'rejected';
            return (
              <tr key={event.seq} className="border-t border-rule-soft">
                <td className="tabular px-3 py-1.5 font-mono text-muted-deep">{event.seq}</td>
                <td className="px-3 py-1.5 font-mono text-muted">
                  {event.actor ?? event.producer}
                </td>
                <td className={`px-3 py-1.5 font-mono ${rejected ? 'text-red' : 'text-ink'}`}>
                  {describe(event.kind, event.payload)}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
