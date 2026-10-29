import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Vitest is not running with globals, so Testing Library's own afterEach hook
// is never registered. Without this the DOM accumulates across tests and
// queries start matching leftovers from an earlier render.
afterEach(cleanup);

// jsdom has neither observer; the views only need them to exist.
class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() {
    return [];
  }
}
globalThis.IntersectionObserver ??= NoopObserver as unknown as typeof IntersectionObserver;
globalThis.ResizeObserver ??= NoopObserver as unknown as typeof ResizeObserver;

// jsdom does not scroll; the case file only asks to.
Element.prototype.scrollTo ??= () => {};

// jsdom has no canvas; the hero skips drawing when there is no context.
HTMLCanvasElement.prototype.getContext = (() =>
  null) as typeof HTMLCanvasElement.prototype.getContext;
