/**
 * The live event stream (PRD §12.3).
 *
 * Every ledger event arrives once, on its console channel. The browser's
 * EventSource resends `Last-Event-ID` when it reconnects, and the store drops
 * any sequence number it has already applied. After a burst of events the
 * snapshot is refreshed once, so the red path, the Suspended card and the held
 * send appear together.
 */

import { useEffect } from 'react';

import type { LedgerEvent } from '../lib/aegisTypes';
import { useAegis } from '../state/aegisSlice';
import { EVENTS_URL } from './aegis';

const CHANNELS = [
  'ledger',
  'graph',
  'finding',
  'decision',
  'action',
  'alert',
  'recovery',
  'verification',
  'record',
] as const;

export function useEventStream(sessionId: string | null): void {
  useEffect(() => {
    if (!sessionId || typeof EventSource === 'undefined') return;
    const source = new EventSource(EVENTS_URL, { withCredentials: true });
    let timer: ReturnType<typeof setTimeout> | null = null;

    const onEvent = (raw: MessageEvent<string>) => {
      const event = JSON.parse(raw.data) as LedgerEvent;
      if (!useAegis.getState().applyEvent(event)) return;
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => void useAegis.getState().refresh(), 60);
    };

    for (const channel of CHANNELS) source.addEventListener(channel, onEvent);
    return () => {
      if (timer) clearTimeout(timer);
      source.close();
    };
  }, [sessionId]);
}
