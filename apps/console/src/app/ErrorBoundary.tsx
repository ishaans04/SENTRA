/**
 * Last-resort boundary.
 *
 * A security console that fails silently is worse than one that fails loudly:
 * a blank panel reads as "nothing is wrong". If rendering breaks, say so
 * plainly and say what state the analysis is actually in.
 */

import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    console.error('The console failed to render.', error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div className="min-h-screen bg-ground p-6">
        <div
          role="alert"
          className="mx-auto max-w-[70ch] rounded-[2px] border border-red/50 bg-red/5 p-6"
        >
          <h1 className="font-display text-[18px] text-ink-bright">The console stopped.</h1>
          <p className="mt-3 text-[13px] leading-relaxed text-ink-soft">
            Rendering failed, so nothing on this page can be trusted to reflect the current state of
            the estate. No analysis result is implied by this screen.
          </p>
          <p className="mt-3 font-mono text-[11.5px] leading-relaxed break-words text-muted">
            {error.message}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="mt-5 rounded-[2px] border border-mint/60 bg-mint/10 px-3 py-2 font-mono text-[10px] tracking-[0.14em] text-mint uppercase"
          >
            Reload the console
          </button>
        </div>
      </div>
    );
  }
}
