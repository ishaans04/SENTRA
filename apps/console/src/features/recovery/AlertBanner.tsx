/**
 * One alert per finding (PRD §13.7), in the template's exact words. The
 * service writes the sentence; the console only shows it.
 */

import { useAegis } from '../../shared/state/aegisSlice';

export function AlertBanner() {
  const alerts = useAegis((s) => s.snapshot?.alerts ?? []);
  if (alerts.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      {alerts.map((alert) => (
        <div
          key={alert.event_id}
          role="alert"
          className="rule-box flex items-start gap-3 border-l-2 border-l-red bg-red/[0.06] px-4 py-3"
        >
          <span className="label !text-red">Alert</span>
          <p className="m-0 text-[13px] leading-relaxed text-ink">{alert.text}</p>
        </div>
      ))}
    </div>
  );
}
