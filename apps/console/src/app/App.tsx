/**
 * The console shell.
 *
 * Two views under one header. The live sandbox is the judge path: approvals,
 * the gateway, HIVE's finding and dictated recovery on one visitor's own world.
 * The HIVE engine view is the original replay console, kept one click away and
 * off the judge path. The view lives in the URL hash so either can be linked.
 */

import { useEffect, useState } from 'react';

import { HiveEngineView } from '../features/engine/HiveEngineView';
import { HaegisView } from '../features/sandbox/HaegisView';
import { PRODUCT_NAME, PRODUCT_TAGLINE } from '../shared/lib/brand';
import { useAegis } from '../shared/state/aegisSlice';
import { useConsole } from '../shared/state/store';
import { Pill } from '../shared/ui/primitives';

type View = 'sandbox' | 'engine';

function viewFromHash(): View {
  return window.location.hash === '#engine' ? 'engine' : 'sandbox';
}

function Badges({ view }: { view: View }) {
  const mode = useAegis((s) => s.mode);
  const source = useConsole((s) => s.source);
  if (view === 'engine') {
    if (!source) return null;
    return (
      <Pill tone={source === 'live' ? 'mint' : 'neutral'}>
        {source === 'live' ? 'live engine' : 'recorded session'}
      </Pill>
    );
  }
  return (
    <>
      <Pill tone="amber">Fictional data</Pill>
      {mode === 'live' && <Pill tone="mint">Live sandbox</Pill>}
      {mode === 'recorded' && <Pill tone="neutral">Recorded replay</Pill>}
    </>
  );
}

export function App() {
  const [view, setView] = useState<View>(viewFromHash);

  useEffect(() => {
    const onHash = () => setView(viewFromHash());
    window.addEventListener('hashchange', onHash);
    return () => window.removeEventListener('hashchange', onHash);
  }, []);

  return (
    <div className="min-h-screen bg-ground">
      <a
        href="#estate"
        className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-[2px] focus:bg-mint focus:px-3 focus:py-2 focus:font-mono focus:text-[11px] focus:text-ground"
      >
        Skip to the interaction map
      </a>

      {/* Standing safety statement. It is a fact about the system, so it is a
          permanent part of the chrome rather than a dismissible notice. */}
      <div className="border-b border-amber/25 bg-amber/[0.06]">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-3 gap-y-1 px-6 py-2">
          <span aria-hidden className="size-1.5 bg-amber" />
          <p className="m-0 font-mono text-[10.5px] tracking-[0.1em] text-amber">
            {view === 'engine'
              ? 'Simulated environment. Fictional data. No system is contacted and every control is simulated.'
              : 'Fictional data. Every control is enforced at the gateway in front of fictional tool servers. Nothing outside this sandbox is contacted.'}
          </p>
        </div>
      </div>

      <header className="sticky top-0 z-40 border-b border-rule bg-ground/95 backdrop-blur">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center gap-x-5 gap-y-2 px-6 py-3">
          <a
            href="#"
            className="font-display text-[15px] font-semibold tracking-[0.24em] text-ink-bright transition-colors hover:text-mint"
          >
            {PRODUCT_NAME}
          </a>
          <span className="hidden max-w-[16rem] font-mono text-[10.5px] leading-tight text-muted-deep sm:block">
            {PRODUCT_TAGLINE}
          </span>
          <nav aria-label="View" className="flex gap-1.5">
            <a
              href="#"
              aria-current={view === 'sandbox' ? 'page' : undefined}
              className={`label rounded-[2px] border px-2.5 py-1 ${view === 'sandbox' ? 'border-mint/60 !text-mint' : 'border-rule'}`}
            >
              Live sandbox
            </a>
            <a
              href="#engine"
              aria-current={view === 'engine' ? 'page' : undefined}
              className={`label rounded-[2px] border px-2.5 py-1 ${view === 'engine' ? 'border-mint/60 !text-mint' : 'border-rule'}`}
            >
              HIVE engine
            </a>
          </nav>
          <div className="ml-auto flex flex-wrap items-center gap-3">
            <Badges view={view} />
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1680px] px-6 py-8">
        {view === 'engine' ? <HiveEngineView /> : <HaegisView />}
      </main>

      <footer className="mt-4 border-t border-rule">
        <div className="mx-auto flex max-w-[1680px] flex-wrap items-center justify-between gap-3 px-6 py-5">
          <p className="m-0 max-w-[76ch] text-[11.5px] leading-relaxed text-muted-deep">
            A route is a risk finding, not proof of a leak. Only calls through the gateway are
            controlled. Recovery uses registered inverses only, and a person's later edit is never
            overwritten.
          </p>
          <span className="label">WeMakeDevs × Wispr Flow · No Hands Challenge 2026</span>
        </div>
      </footer>
    </div>
  );
}
