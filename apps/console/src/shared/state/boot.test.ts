import { afterEach, describe, expect, it, vi } from 'vitest';

import { useAegis } from './aegisSlice';

const existing = { session_id: 's-1', beat: 8, plans: [] };

function reply(body: unknown, status = 200): Promise<Response> {
  return Promise.resolve(new Response(JSON.stringify(body), { status }));
}

describe('boot and confirm', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reuses the sandbox it already has instead of resetting it', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) => {
      if (url.endsWith('/healthz')) return reply({ status: 'ok' });
      if (url.endsWith('/api/state')) return reply(existing);
      return reply({ error: 'unexpected', message: `${init?.method} ${url}` }, 500);
    });
    vi.stubGlobal('fetch', fetchMock);
    useAegis.setState({ mode: 'connecting', snapshot: null });
    await useAegis.getState().boot();
    expect(useAegis.getState().snapshot?.beat).toBe(8);
    expect(fetchMock.mock.calls.some(([url]) => String(url).endsWith('/api/session'))).toBe(false);
  });

  it('starts a sandbox only when there is none', async () => {
    const fetchMock = vi.fn((url: string) => {
      if (url.endsWith('/healthz')) return reply({ status: 'ok' });
      if (url.endsWith('/api/state')) return reply({ error: 'no_session', message: 'x' }, 404);
      return reply({ ...existing, beat: -1 });
    });
    vi.stubGlobal('fetch', fetchMock);
    useAegis.setState({ mode: 'connecting', snapshot: null });
    await useAegis.getState().boot();
    expect(useAegis.getState().snapshot?.beat).toBe(-1);
  });

  it('confirms the revision that was read back', async () => {
    const fetchMock = vi.fn((url: string, init?: RequestInit) =>
      url.endsWith('/api/state') ? reply(existing) : reply({ id: 'P-1', body: init?.body }),
    );
    vi.stubGlobal('fetch', fetchMock);
    useAegis.setState({
      mode: 'live',
      snapshot: {
        ...existing,
        plans: [{ id: 'P-1', status: 'read_back', revision: 'abc123' }],
      } as never,
    });
    await useAegis.getState().confirmRecovery();
    const confirm = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/confirm'));
    expect(JSON.parse(String(confirm?.[1]?.body))).toEqual({ revision: 'abc123' });
  });
});
