/**
 * Last-resort boundary. If rendering breaks, say so plainly rather than show
 * a blank page that reads as "nothing is wrong".
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
    console.error('HAEGIS failed to render.', error, info.componentStack);
  }

  render(): ReactNode {
    const { error } = this.state;
    if (!error) return this.props.children;

    return (
      <div style={{ minHeight: '100vh', padding: 24 }}>
        <div
          role="alert"
          style={{
            maxWidth: '70ch',
            margin: '10vh auto 0',
            padding: 24,
            borderRadius: 14,
            border: '1px solid var(--red)',
            background: 'var(--red-bg)',
          }}
        >
          <h1 style={{ margin: 0, font: '600 18px var(--font-sans)' }}>The page stopped.</h1>
          <p
            style={{
              margin: '12px 0 0',
              font: '400 14px/1.5 var(--font-sans)',
              color: 'var(--ink-2)',
            }}
          >
            Something failed while drawing this screen, so what you see here can’t be trusted.
          </p>
          <p
            className="mono"
            style={{
              margin: '12px 0 0',
              fontSize: 12,
              color: 'var(--mute)',
              overflowWrap: 'anywhere',
            }}
          >
            {error.message}
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            style={{
              marginTop: 18,
              height: 36,
              padding: '0 14px',
              border: 0,
              borderRadius: 8,
              background: 'var(--ink)',
              color: 'var(--paper)',
              cursor: 'pointer',
              font: '500 13px var(--font-sans)',
            }}
          >
            Reload
          </button>
        </div>
      </div>
    );
  }
}
