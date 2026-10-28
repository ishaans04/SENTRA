import { afterEach, describe, expect, it, vi } from 'vitest';

import { useAegis } from './aegisSlice';

const frames = [
  { n: 0, title: 'Seed', file: 'beat-00.json' },
  { n: 1, title: 'Approve', file: 'beat-01.json' },
];

function frame(beat: number, seq: number) {
  return {
    snapshot: {
      session_id: 's-recorded',
      beat,
      labels: { data: 'Fictional data', mode: 'Recorded replay' },
    },
    ledger: [{ seq, kind: 'session.seeded' }],
  };
}

function fakeFetch(url: string): Promise<Response> {
  if (url.endsWith('/healthz')) return Promise.reject(new Error('offline'));
  const body = url.endsWith('index.json')
    ? { frames }
    : url.endsWith('beat-00.json')
      ? frame(0, 3)
      : frame(1, 7);
  return Promise.resolve(new Response(JSON.stringify(body), { status: 200 }));
}

describe('recorded replay', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('plays the recording when the sandbox is unreachable, with commands disabled', async () => {
    vi.stubGlobal('fetch', vi.fn(fakeFetch));
    useAegis.setState({ mode: 'connecting', snapshot: null, frames: [], frame: 0 });
    await useAegis.getState().boot();
    expect(useAegis.getState().mode).toBe('recorded');
    expect(useAegis.getState().snapshot?.labels.mode).toBe('Recorded replay');

    await useAegis.getState().step();
    expect(useAegis.getState().snapshot?.beat).toBe(1);
    expect(useAegis.getState().lastSeq).toBe(7);

    await useAegis.getState().interpretApproval('Approve reporting');
    expect(useAegis.getState().proposal).toBeNull();

    await useAegis.getState().reset();
    expect(useAegis.getState().snapshot?.beat).toBe(0);
  });
});
