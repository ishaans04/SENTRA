import '@testing-library/jest-dom/vitest';

import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';

// Vitest is not running with globals, so Testing Library's own afterEach hook
// is never registered. Without this the DOM accumulates across tests and
// queries start matching leftovers from an earlier render.
afterEach(cleanup);
