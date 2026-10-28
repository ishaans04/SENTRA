/**
 * The console's shared vocabulary of surfaces, labels and states.
 *
 * Keeping these in one place is what stops a security interface from drifting
 * into four slightly different ways of saying the same thing — which matters
 * more here than usual, because an operator reads severity and state under
 * time pressure.
 */

import type { ReactNode } from 'react';

export function Panel({
  title,
  aside,
  children,
  flush = false,
  tone = 'neutral',
}: {
  title: string;
  aside?: ReactNode;
  children: ReactNode;
  flush?: boolean;
  tone?: 'neutral' | 'alert' | 'resolved';
}) {
  const edge =
    tone === 'alert'
      ? 'border-l-[#f4543c]'
      : tone === 'resolved'
        ? 'border-l-[#7ff0c0]'
        : 'border-l-rule';
  return (
    <section data-panel={title} className={`rule-box border-l-2 bg-surface ${edge}`}>
      <header className="flex items-center justify-between gap-4 border-b border-rule-soft px-4 py-3">
        <h2 className="label !text-muted">{title}</h2>
        {aside}
      </header>
      <div className={flush ? '' : 'p-4'}>{children}</div>
    </section>
  );
}

export function Pill({
  children,
  tone = 'neutral',
}: {
  children: ReactNode;
  tone?: 'neutral' | 'mint' | 'amber' | 'red' | 'violet';
}) {
  const tones = {
    neutral: 'border-rule text-muted',
    mint: 'border-mint/40 text-mint',
    amber: 'border-amber/40 text-amber',
    red: 'border-red/50 text-red',
    violet: 'border-violet/40 text-violet',
  } as const;
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-[2px] border px-2 py-[3px] font-mono text-[10px] tracking-[0.14em] uppercase ${tones[tone]}`}
    >
      {children}
    </span>
  );
}

const SEVERITY_TONE = {
  low: 'neutral',
  medium: 'amber',
  high: 'red',
  critical: 'red',
} as const;

export function SeverityPill({ severity }: { severity: keyof typeof SEVERITY_TONE }) {
  return <Pill tone={SEVERITY_TONE[severity]}>{severity} severity</Pill>;
}

/**
 * A weighted contribution bar.
 *
 * The width is the factor's weight, so a reader can see the scale add to one
 * and reconstruct the total by eye. A factor that did not fire keeps its slot
 * and goes dark rather than disappearing, because which signals were absent is
 * as informative as which were present.
 */
export function Contribution({
  weight,
  present,
  max = 0.35,
}: {
  weight: number;
  present: boolean;
  max?: number;
}) {
  return (
    <span
      className="relative block h-[3px] w-14 shrink-0 bg-rule-soft"
      role="presentation"
      title={`weight ${weight.toFixed(2)}`}
    >
      <span
        className={`absolute inset-y-0 left-0 ${present ? 'bg-red' : 'bg-rule'}`}
        style={{ width: `${Math.min(100, (weight / max) * 100)}%` }}
      />
    </span>
  );
}

export function Empty({ title, body }: { title: string; body: string }) {
  return (
    <div className="px-1 py-6">
      <p className="m-0 font-display text-[15px] text-ink-soft">{title}</p>
      <p className="m-0 mt-1.5 max-w-[46ch] text-[13px] leading-relaxed text-muted">{body}</p>
    </div>
  );
}

export function Problem({
  message,
  hint,
  onDismiss,
}: {
  message: string;
  hint?: string;
  onDismiss?: () => void;
}) {
  return (
    <div role="alert" className="rule-box border-red/50 bg-red/5 p-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="m-0 text-[13px] text-ink">{message}</p>
          {hint && (
            <p className="m-0 mt-2 font-mono text-[11px] leading-relaxed text-muted">{hint}</p>
          )}
        </div>
        {onDismiss && (
          <button
            type="button"
            onClick={onDismiss}
            className="label shrink-0 hover:text-ink"
            aria-label="Dismiss"
          >
            close
          </button>
        )}
      </div>
    </div>
  );
}

export function Button({
  children,
  onClick,
  variant = 'quiet',
  disabled,
  title,
  pressed,
}: {
  children: ReactNode;
  onClick?: () => void;
  variant?: 'quiet' | 'primary' | 'danger';
  disabled?: boolean;
  title?: string;
  pressed?: boolean;
}) {
  const variants = {
    quiet: 'border-rule text-muted hover:border-ink/30 hover:text-ink disabled:hover:border-rule',
    primary: 'border-mint/60 bg-mint/10 text-mint hover:bg-mint/20',
    danger: 'border-red/60 bg-red/10 text-red hover:bg-red/20',
  } as const;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-pressed={pressed}
      className={`rounded-[2px] border px-3 py-[7px] font-mono text-[10px] tracking-[0.14em] uppercase transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${variants[variant]}`}
    >
      {children}
    </button>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="label mb-2">{label}</div>
      {children}
    </div>
  );
}

export function Choice<T extends string | number>({
  options,
  value,
  onChange,
  disabled,
  name,
}: {
  options: readonly T[];
  value: T;
  onChange: (next: T) => void;
  disabled?: boolean;
  name: string;
}) {
  return (
    <div className="flex flex-wrap gap-1.5" role="radiogroup" aria-label={name}>
      {options.map((option) => {
        const active = option === value;
        return (
          <button
            key={String(option)}
            type="button"
            role="radio"
            aria-checked={active}
            disabled={disabled}
            onClick={() => onChange(option)}
            className={`rounded-[2px] border px-2.5 py-1 font-mono text-[10.5px] tracking-[0.06em] transition-colors disabled:cursor-not-allowed disabled:opacity-35 ${
              active
                ? 'border-mint/60 bg-mint/10 text-mint'
                : 'border-rule text-muted hover:border-ink/25 hover:text-ink'
            }`}
          >
            {String(option).replace(/_/g, ' ')}
          </button>
        );
      })}
    </div>
  );
}
