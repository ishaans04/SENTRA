/**
 * The HAEGIS API client (PRD §12.2).
 *
 * The built console is served by the same process as the API, so the default
 * base is the page's own origin. In development, `VITE_HAEGIS_API_BASE` points
 * at the local service. The session lives in an HTTP-only cookie.
 */

import type { ProposedDecision, RecoveryPlanView, Snapshot } from '../lib/aegisTypes';

export const HAEGIS_BASE = (import.meta.env.VITE_HAEGIS_API_BASE ?? '').replace(/\/$/, '');

export class AegisError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function call<T>(method: 'GET' | 'POST', path: string, body?: unknown): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${HAEGIS_BASE}${path}`, {
      method,
      credentials: 'include',
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new AegisError('The sandbox is not reachable right now.', 'offline', 0);
  }
  if (!response.ok) {
    let code = 'error';
    let message = `The service answered ${response.status}.`;
    try {
      const envelope = (await response.json()) as { error?: string; message?: string };
      code = envelope.error ?? code;
      message = envelope.message ?? message;
    } catch {
      // Not JSON: keep the plain status message.
    }
    throw new AegisError(message, code, response.status);
  }
  return (await response.json()) as T;
}

export async function isLive(timeoutMs = 2500): Promise<boolean> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(`${HAEGIS_BASE}/healthz`, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  createSession: () => call<Snapshot>('POST', '/api/session'),
  state: () => call<Snapshot>('GET', '/api/state'),
  step: () => call<Snapshot>('POST', '/api/story/step'),
  play: () => call<Snapshot>('POST', '/api/story/play'),
  reset: () => call<Snapshot>('POST', '/api/story/reset'),
  interpretDecision: (text: string) =>
    call<ProposedDecision>('POST', '/api/decisions/interpret', { text }),
  decision: (id: string, verb: 'confirm' | 'reject' | 'renew' | 'withdraw') =>
    call<Snapshot>('POST', `/api/decisions/${encodeURIComponent(id)}/${verb}`),
  interpretRecovery: (text: string) =>
    call<RecoveryPlanView>('POST', '/api/recovery/interpret', { text }),
  correctRecovery: (id: string, text: string) =>
    call<RecoveryPlanView>('POST', `/api/recovery/${encodeURIComponent(id)}/correct`, { text }),
  recovery: (id: string, verb: 'confirm' | 'abandon') =>
    call<RecoveryPlanView>('POST', `/api/recovery/${encodeURIComponent(id)}/${verb}`),
  humanEdit: (item: string, content: string) =>
    call<Snapshot>('POST', `/api/items/${encodeURIComponent(item)}/human-edit`, { content }),
  resolveConflict: (id: string, choice: 'keep_human' | 'leave_for_review') =>
    call<Snapshot>('POST', `/api/conflicts/${encodeURIComponent(id)}/resolve`, { choice }),
};

export const EVENTS_URL = `${HAEGIS_BASE}/api/events`;
