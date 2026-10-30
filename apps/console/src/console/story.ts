/**
 * The recorded session the console replays: 28 events over a fictional
 * support/reporting estate, grouped into nine chapters. Everything here is
 * pure data or a pure function of the current beat, so the view can be
 * rebuilt from the beat alone and the same beat always looks the same.
 *
 * Beat b shows events 1..(7 + b). Beat 0 is the approved baseline (events
 * 1–7), beat 8 waits for the operator, and beat 16 is the verified record.
 * Beat 17 waits for the operator again, to keep a standing order, and beats
 * 19–21 are the week after, when that order refuses the scratchpad read.
 */

import { C } from '../shared/theme';

export const LAST_BEAT = 21;
export const OPERATOR_BEAT = 8;
/** The outcome record of the recovery. */
export const VERIFIED_BEAT = 16;
/** The operator keeps what the incident taught as a standing order. */
export const REMEMBER_BEAT = 17;
/** From the route chapter on, the case file lives in the glass panel. */
export const CASE_FILE_BEAT = 3;
export const ROUTE_BEAT = 5;
export const WITHDRAWN_BEAT = 6;
export const RECOVER_BEAT = 10;

export const DICTATION =
  'Stop this reporting run, remove its scratchpad access, and rebuild the report from approved summaries. Keep the support work.';

export const REMEMBER_DICTATION =
  'From now on, an agent that can send outside never reads from a store nobody declared.';

export type Lane = 'decision' | 'gateway' | 'agent';
export type Tone = 'ok' | 'ink' | 'amber' | 'red' | 'blue' | 'green';

export interface StoryEvent {
  lane: Lane;
  actor: string;
  verb: string;
  target: string;
  note: string;
  tone: Tone;
}

const ev = (
  lane: Lane,
  actor: string,
  verb: string,
  target: string,
  note: string,
  tone: Tone,
): StoryEvent => ({ lane, actor, verb, target, note, tone });

export const EVENTS: StoryEvent[] = [
  ev(
    'decision',
    'Operator',
    'approve',
    'D-07 · epoch 3',
    'Reporting may proceed on sanitized summaries only',
    'blue',
  ),
  ev('agent', 'Support Agent', 'read', 'Fictional CRM', 'declared', 'ok'),
  ev('agent', 'Support Agent', 'write', 'Approved Ticket Store', 'declared', 'ok'),
  ev('agent', 'Analytics Agent', 'read', 'Approved Ticket Store', 'declared', 'ok'),
  ev('agent', 'Analytics Agent', 'write', 'Internal Report Store', 'declared', 'ok'),
  ev('agent', 'Reporting Agent', 'read', 'Internal Report Store', 'declared · run r-0411', 'ok'),
  ev('agent', 'Reporting Agent', 'send', 'External Webhook', 'declared · r-0411 delivered', 'ok'),
  ev('agent', 'Support Agent', 'discover', 'Unregistered Scratchpad', 'not in manifest', 'amber'),
  ev('agent', 'Support Agent', 'write', 'Unregistered Scratchpad', 'undeclared write', 'amber'),
  ev('agent', 'Reporting Agent', 'discover', 'Unregistered Scratchpad', 'not in manifest', 'amber'),
  ev(
    'gateway',
    'Reporting Agent',
    'queue',
    'Outbox → External Webhook',
    'r-0412 queued under D-07 · e3',
    'ok',
  ),
  ev(
    'agent',
    'Reporting Agent',
    'read',
    'Unregistered Scratchpad',
    'route closes · PS-001 raised',
    'red',
  ),
  ev(
    'decision',
    'SENTRA',
    'withdraw',
    'Condition C-07a',
    'justification gone · D-07 needs review',
    'red',
  ),
  ev('gateway', 'Gateway', 'hold', 'Outbox · r-0412', 'pre-authorised hold rule H-2', 'blue'),
  ev(
    'decision',
    'Operator',
    'dictate',
    'Tell SENTRA',
    'via Wispr Flow · read-back prepared',
    'blue',
  ),
  ev('decision', 'Operator', 'confirm', 'Read-back', 'D-07 renewed at epoch 4 for r-0413', 'blue'),
  ev('gateway', 'Gateway', 'cancel', 'Run r-0412', 'affected run stopped', 'ink'),
  ev(
    'gateway',
    'Gateway',
    'revoke',
    'Reporting → read → Scratchpad',
    'only the read is severed',
    'ink',
  ),
  ev(
    'gateway',
    'Reporting Agent',
    'send',
    'External Webhook',
    'REJECTED · stale epoch 3 < 4',
    'red',
  ),
  ev(
    'agent',
    'Reporting Agent',
    'read',
    'Internal Report Store',
    'r-0413 · fresh context',
    'green',
  ),
  ev(
    'decision',
    'SENTRA',
    'preserve',
    'Draft “Q3 support digest”',
    'edited by Priya since agent wrote it · kept',
    'amber',
  ),
  ev(
    'agent',
    'Reporting Agent',
    'send',
    'External Webhook',
    'r-0413 delivered under epoch 4',
    'green',
  ),
  ev(
    'decision',
    'SENTRA',
    'verify',
    'Contained graph',
    '0 open findings · declared work 6 of 6 intact',
    'green',
  ),
  ev(
    'decision',
    'Operator',
    'dictate',
    'Tell SENTRA',
    'standing order · via Wispr Flow · read-back prepared',
    'blue',
  ),
  ev(
    'decision',
    'Operator',
    'confirm',
    'Standing order SO-1',
    'kept for every later session · cites PS-001',
    'blue',
  ),
  ev(
    'agent',
    'Support Agent',
    'write',
    'Unregistered Scratchpad',
    'a week later · still allowed',
    'amber',
  ),
  ev(
    'gateway',
    'Reporting Agent',
    'read',
    'Unregistered Scratchpad',
    'REFUSED · standing order SO-1 · no route forms',
    'red',
  ),
  ev(
    'agent',
    'Reporting Agent',
    'send',
    'External Webhook',
    'r-0420 delivered · nothing paused',
    'green',
  ),
];

/** Colour of a ledger mark, and of a note, for each tone. */
export const TONE: Record<Tone, string> = {
  ok: C.line,
  ink: C.ink,
  amber: C.amberLine,
  red: C.red,
  blue: C.blue,
  green: C.green,
};
export const NOTE: Record<Tone, string> = {
  ok: C.mute,
  ink: C.ink,
  amber: C.amber,
  red: C.red,
  blue: C.blue,
  green: C.green,
};

export const CHAPTERS = [
  {
    s: 0,
    short: 'Approved',
    title: 'The approved workflow',
    body: 'Reporting may proceed because it receives only sanitized summaries. SENTRA records that condition and every run authorised under it.',
  },
  {
    s: 1,
    short: 'Connection',
    title: 'An unexpected connection',
    body: 'Support starts writing to a scratchpad nobody declared. Each action is permitted on its own. No finding yet — nothing has taken data out.',
  },
  {
    s: 3,
    short: 'Route',
    title: 'Four permitted hops compose a route',
    body: 'Reporting reads the scratchpad. Restricted records now have a path to the outside. SENTRA flags a possible route — not proof of a leak.',
  },
  {
    s: 6,
    short: 'Withdrawn',
    title: 'The justification no longer holds',
    body: 'SENTRA links the finding to D-07. Its condition fails, no other basis remains, and an external report is queued. A pre-authorised hold pauses it.',
  },
  {
    s: 8,
    short: 'Decide',
    title: 'The operator decides, in plain words',
    body: 'Dictated into Tell SENTRA with Wispr Flow. The instruction is read back as concrete gateway steps — nothing runs until it is confirmed.',
  },
  {
    s: 10,
    short: 'Recover',
    title: 'A narrow recovery',
    body: 'Cancel the affected run, remove its access, rebuild from approved sources. A late send is rejected. A human edit survives.',
  },
  {
    s: 16,
    short: 'Verified',
    title: 'Measured, not assumed',
    body: 'The rules re-run over the contained graph. The route is gone, the old run cannot send, and the replacement did its approved job.',
  },
  {
    s: 17,
    short: 'Remember',
    title: 'Remembered for next time',
    body: 'Say what should always hold. SENTRA reads it back with the incident behind it — PS-001, run r-0412 — and keeps it only when you confirm.',
  },
  {
    s: 19,
    short: 'Next week',
    title: 'A week later, nothing to stop',
    body: 'Reporting tries the scratchpad again. The gateway refuses that one read, citing SO-1. No route forms, no approval falls, and the report goes out on time.',
  },
];

export const visibleCount = (b: number) => (b === 0 ? 7 : 7 + b);
export const chapterOf = (b: number) => CHAPTERS.reduce((acc, c, i) => (b >= c.s ? i : acc), 0);
export const isChapterStart = (b: number) => CHAPTERS.some((c) => c.s === b);

/** How far each chapter's progress bar is filled, 0..1. */
export function chapterFill(i: number, b: number): number {
  const c = CHAPTERS[i];
  const end = i < CHAPTERS.length - 1 ? CHAPTERS[i + 1].s : LAST_BEAT + 1;
  if (b < c.s) return 0;
  if (b >= end) return 1;
  return (b - c.s + 1) / (end - c.s);
}

/** The ledger mark an event jumps to: the beat at which it became visible. */
export const beatOfEvent = (i: number) => Math.max(0, i + 1 - 7);

// ---------------------------------------------------------------------------
// The interaction map

export type NodeId =
  'crm' | 'support' | 'tickets' | 'analytics' | 'reports' | 'reporting' | 'scratch' | 'webhook';

/** Node centres on a 1000 × 600 canvas. */
export const POS: Record<NodeId, [number, number]> = {
  crm: [110, 80],
  support: [330, 80],
  tickets: [520, 230],
  analytics: [710, 230],
  reports: [900, 230],
  reporting: [900, 385],
  scratch: [420, 465],
  webhook: [900, 555],
};
export const NODE_IDS = Object.keys(POS) as NodeId[];

export const EDGES: [string, NodeId, NodeId][] = [
  ['e1', 'crm', 'support'],
  ['e2', 'support', 'tickets'],
  ['e3', 'tickets', 'analytics'],
  ['e4', 'analytics', 'reports'],
  ['e5', 'reports', 'reporting'],
  ['e6', 'reporting', 'webhook'],
  ['e7', 'support', 'scratch'],
  ['e8', 'scratch', 'reporting'],
];
const ROUTE = ['e1', 'e7', 'e8', 'e6'];

export const pathD = (a: NodeId, b: NodeId) => {
  const [x1, y1] = POS[a];
  const [x2, y2] = POS[b];
  const m = (y1 + y2) / 2;
  return `M${x1} ${y1} C${x1} ${m}, ${x2} ${m}, ${x2} ${y2}`;
};

type Glyph = 'store' | 'agent' | 'scratch' | 'ext';
export const NODES: Record<NodeId, { name: string; kind: string; g: Glyph; declared: string[] }> = {
  crm: {
    name: 'Fictional CRM',
    kind: 'DATA STORE · RESTRICTED',
    g: 'store',
    declared: ['Support Agent may read'],
  },
  support: {
    name: 'Support Agent',
    kind: 'AGENT · SUPPORT',
    g: 'agent',
    declared: ['read Fictional CRM', 'write Approved Ticket Store'],
  },
  tickets: {
    name: 'Approved Ticket Store',
    kind: 'DATA STORE · APPROVED',
    g: 'store',
    declared: ['Support writes · Analytics reads'],
  },
  analytics: {
    name: 'Analytics Agent',
    kind: 'AGENT · ANALYTICS',
    g: 'agent',
    declared: ['read Approved Ticket Store', 'write Internal Report Store'],
  },
  reports: {
    name: 'Internal Report Store',
    kind: 'DATA STORE · SANITIZED',
    g: 'store',
    declared: ['Analytics writes · Reporting reads'],
  },
  reporting: {
    name: 'Reporting Agent',
    kind: 'AGENT · REPORTING · UNDER D-07',
    g: 'agent',
    declared: ['read Internal Report Store', 'send External Webhook'],
  },
  scratch: {
    name: 'Unregistered Scratchpad',
    kind: 'SHARED STATE · NOT IN MANIFEST',
    g: 'scratch',
    declared: ['nothing — absent from manifest'],
  },
  webhook: {
    name: 'External Webhook',
    kind: 'EXTERNAL · SIMULATED DESTINATION',
    g: 'ext',
    declared: ['Reporting Agent may send'],
  },
};

/** The composed route is drawn from the moment Reporting reads the scratchpad until it is cut. */
export const routeOpen = (b: number) => b >= 5 && b <= 10;

type NodeTone = 'base' | 'red' | 'amber' | 'green';
type TagTone = 'green' | 'amber' | 'blue' | 'ink';

export interface NodeView {
  id: NodeId;
  name: string;
  sub: string;
  tone: NodeTone;
  tag: [string, TagTone] | null;
  visible: boolean;
}

export function nodeView(id: NodeId, b: number): NodeView {
  const on = routeOpen(b);
  let tone: NodeTone = 'base';
  let sub = '';
  let tag: [string, TagTone] | null = null;
  let visible = true;
  switch (id) {
    case 'crm':
      sub = 'restricted · customer records';
      if (on) tone = 'red';
      break;
    case 'support':
      sub =
        b >= 19
          ? 'a week later · same work'
          : b >= 14
            ? 'runs untouched'
            : 'reads CRM · writes tickets';
      if (on) tone = 'red';
      if (b >= 14) {
        tone = 'green';
        tag = ['PRESERVED', 'green'];
      }
      break;
    case 'tickets':
      sub = 'approved state';
      break;
    case 'analytics':
      sub = 'summarises tickets';
      break;
    case 'reports':
      sub = b >= 14 ? 'Priya’s draft edit kept' : 'sanitized summaries';
      if (b >= 13) tone = 'green';
      if (b >= 14) tag = ['CONFLICT · KEPT', 'amber'];
      break;
    case 'reporting':
      sub =
        b < 4
          ? 'run r-0411 · delivered'
          : b < 7
            ? 'run r-0412 · send queued'
            : b < 10
              ? 'run r-0412 · held'
              : b < 13
                ? 'run r-0412 · cancelled'
                : b < 15
                  ? 'run r-0413 · fresh context'
                  : b < 19
                    ? 'run r-0413 · delivered'
                    : b < 21
                      ? 'run r-0420 · scratchpad read refused'
                      : 'run r-0420 · delivered';
      if (on && b < 10) tone = 'red';
      if (b >= 15) tone = 'green';
      if (b >= 7 && b <= 9) tag = ['HELD', 'blue'];
      else if (b >= 10 && b <= 12) tag = ['CANCELLED', 'ink'];
      else if (b >= 13 && b <= 14) tag = ['REBUILDING', 'blue'];
      else if (b >= 21) tag = ['r-0420 ✓', 'green'];
      else if (b >= 20) tag = ['SO-1 · READ REFUSED', 'blue'];
      else if (b >= 15) tag = ['r-0413 ✓', 'green'];
      break;
    case 'scratch':
      sub =
        b >= 19
          ? 'a week later · Support’s notes allowed'
          : b >= 11
            ? 'isolated · read revoked'
            : 'not in manifest';
      visible = b >= 1;
      tone = on ? 'red' : 'amber';
      if (b >= 1) tag = ['UNDECLARED', 'amber'];
      break;
    case 'webhook':
      sub = 'simulated · external';
      if (on) tone = 'red';
      if (b >= 15) tone = 'green';
      break;
  }
  return { id, name: NODES[id].name, sub, tone, tag, visible };
}

export interface EdgeView {
  id: string;
  d: string;
  stroke: string;
  width: number;
  opacity: number;
  dash?: string;
  march: boolean;
  halo: boolean;
  packets: number;
  packetColor: string;
  packetDur: number;
}

export function edgeViews(b: number): EdgeView[] {
  const on = routeOpen(b);
  const out: EdgeView[] = [];
  for (const [id, a, z] of EDGES) {
    let stroke: string = C.line;
    let dash: string | undefined;
    let width = 1.6;
    let opacity = 1;
    let packetColor: string = C.faint;
    let packets = 2;
    let march = false;
    if (id === 'e7') {
      if (b < 1) continue;
      stroke = C.amberLine;
      if (b === 1) {
        dash = '2 5';
        opacity = 0.8;
        packets = 0;
      } else {
        dash = '6 5';
        packetColor = C.amberLine;
      }
    }
    if (id === 'e8') {
      if (b < 3) continue;
      if (b < 5) {
        stroke = C.amberLine;
        dash = '2 5';
        opacity = 0.8;
        packets = 0;
      } else if (b <= 10) {
        stroke = C.red;
        dash = '6 5';
        packetColor = C.red;
      } else {
        stroke = C.faint;
        dash = '2 6';
        opacity = 0.6;
        packets = 0;
      }
    }
    if (id === 'e6') {
      if (b >= 4 && b < 15) packets = 0;
      if (b >= 15) {
        stroke = C.green;
        packetColor = C.green;
        packets = 3;
      }
    }
    if (id === 'e5' && b >= 13) {
      stroke = C.green;
      packetColor = C.green;
      packets = 3;
    }
    const onRoute = on && ROUTE.includes(id);
    if (onRoute) {
      stroke = C.red;
      width = 2;
      march = true;
      packetColor = C.red;
      packets = id === 'e6' ? 0 : 3;
    }
    out.push({
      id,
      d: pathD(a, z),
      stroke,
      width,
      opacity,
      dash: march ? '7 7' : dash,
      march,
      halo: onRoute,
      packets,
      packetColor,
      packetDur: id === 'e7' || id === 'e8' ? 2.4 : 3.6,
    });
  }
  return out;
}

export interface Marker {
  x: number;
  y: number;
  text: string;
  color: string;
  bg: string;
  pulse: boolean;
}

export function markers(b: number): Marker[] {
  const m: Marker[] = [];
  const mk = (x: number, y: number, text: string, color: string, bg: string, pulse = false) =>
    m.push({ x, y, text, color, bg, pulse });
  if (b >= 2 && b <= 4) mk(375, 300, 'undeclared write · #09', C.amber, C.amberBg);
  if (b >= 5 && b <= 10) mk(640, 440, 'route closes · #12', C.red, C.redBg);
  if (b >= 11 && b < 20) mk(660, 455, 'read revoked · #18', C.ink, C.card);
  if (b >= 20) mk(660, 455, '✕ read refused · SO-1 · #27', C.red, C.redBg, b === 20);
  if (b >= 7 && b <= 11) mk(900, 470, 'HELD · H-2', C.blue, C.blueBg, b <= 9);
  if (b >= 12 && b <= 14) mk(872, 470, '✕ send rejected · epoch 3 < 4', C.red, C.redBg);
  return m;
}

/** What the map's detail card says about a node, given what has been observed so far. */
export function observed(id: NodeId, b: number): string[] {
  const obs: string[] = [];
  if (id === 'support' && b >= 2) obs.push('write Unregistered Scratchpad · #09');
  if (id === 'reporting' && b >= 5)
    obs.push(
      b >= 11
        ? 'read Unregistered Scratchpad · #12 · revoked #18'
        : 'read Unregistered Scratchpad · #12',
    );
  if (id === 'scratch' && b >= 2) obs.push('Support writes · #09');
  if (id === 'scratch' && b >= 5) obs.push('Reporting reads · #12');
  return obs;
}

// ---------------------------------------------------------------------------
// The case file

export function decision(b: number) {
  let status = 'VALID · EPOCH 3';
  let color: string = C.green;
  let bg: string = C.greenBg;
  if (b === 6) {
    status = 'NEEDS REVIEW';
    color = C.red;
    bg = C.redBg;
  }
  if (b === 7 || b === 8) {
    status = 'BASIS WITHDRAWN · RUN HELD';
    color = C.red;
    bg = C.redBg;
  }
  if (b >= 9) {
    status = 'RENEWED · EPOCH 4';
    color = C.blue;
    bg = C.blueBg;
  }
  let cond = 'holds';
  let condColor: string = C.green;
  if (b === 5) {
    cond = 'checking · new evidence #12';
    condColor = C.amber;
  }
  if (b >= 6 && b < 9) {
    cond = 'withdrawn · #12';
    condColor = C.red;
  }
  if (b >= 9 && b < 13) {
    cond = 'withdrawn for r-0412 · renewed scope pending';
    condColor = C.blue;
  }
  if (b >= 13) {
    cond = 'holds for r-0413';
    condColor = C.green;
  }
  return {
    status,
    color,
    bg,
    cond,
    condColor,
    showBasis: b >= 6 && b < 9,
    meta:
      b >= 9
        ? 'approved #01 · renewed #16 by operator · epoch 4'
        : 'approved by operator · #01 · epoch 3',
  };
}

export function runs(b: number) {
  const out = [
    { id: 'r-0411', state: 'delivered before the change · #07', color: C.mute as string },
  ];
  if (b >= 4)
    out.push({
      id: 'r-0412',
      color: b >= 12 ? C.red : b >= 7 ? C.blue : C.ink,
      state:
        b < 7
          ? 'send queued in outbox · #11'
          : b < 10
            ? 'held by H-2 at the gateway · #14'
            : b < 12
              ? 'cancelled · #17'
              : 'cancelled · late send rejected · #19',
    });
  if (b >= 13)
    out.push({
      id: 'r-0413',
      color: b >= 15 ? C.green : C.blue,
      state:
        b >= 15 ? 'delivered from approved sources · #22' : 'running · approved sources only · #20',
    });
  if (b >= 19)
    out.push({
      id: 'r-0420',
      color: b >= 21 ? C.green : C.blue,
      state:
        b >= 21
          ? 'a week later · delivered, nothing paused · #28'
          : b >= 20
            ? 'a week later · scratchpad read refused under SO-1 · #27'
            : 'a week later · running under D-07',
    });
  return out;
}

export function hops(b: number) {
  return (
    [
      ['1', 'Fictional CRM → Support Agent', 'ingest', '#02', true],
      ['2', 'Support Agent → Scratchpad', 'deposit', '#09', false],
      ['3', 'Scratchpad → Reporting Agent', 'withdrawal', '#12', false],
      ['4', 'Reporting Agent → External Webhook', 'egress', '#07', true],
    ] as const
  ).map(([i, route, kind, ev, declared]) => {
    const cut = i === '3' && b >= 11;
    return {
      i,
      route,
      kind,
      ev,
      flag: cut ? 'SEVERED' : declared ? 'DECLARED' : 'UNDECLARED',
      color: cut ? C.ink : declared ? C.mute : C.amber,
      bg: cut ? 'oklch(0.93 0.006 80)' : declared ? 'oklch(0.95 0.006 80)' : C.amberBg,
    };
  });
}

export function controls(b: number) {
  return (
    [
      ['Block Reporting → read → Scratchpad', true, 'cheapest viable'],
      ['Block Support → write → Scratchpad', true, 'viable · touches Support runs'],
      ['Quarantine Scratchpad', true, 'viable · broader'],
      ['Block Reporting → send → Webhook', false, 'rejected · severs declared reporting'],
      ['Block Support → read → CRM', false, 'rejected · severs declared support'],
    ] as const
  ).map(([name, keepsWork, verdict], i) => {
    const rec = i === 0;
    return {
      name,
      keepsWork,
      verdict: rec
        ? b >= 11
          ? 'APPLIED · #18 · VERIFIED'
          : b >= 9
            ? 'RECOMMENDED · CONFIRMED'
            : 'RECOMMENDED · AWAITING OPERATOR'
        : verdict.toUpperCase(),
      verdictColor: rec ? (b >= 11 ? C.green : C.blue) : keepsWork ? C.mute : C.red,
      textColor: keepsWork ? C.ink : C.mute,
      bg: rec ? (b >= 11 ? C.greenBg : C.blueBg) : 'transparent',
    };
  });
}

// ---------------------------------------------------------------------------
// Tell SENTRA: words to read-back steps

export type StepKey = 'cancel' | 'revoke' | 'rebuild' | 'keep';

const GRAMMAR: { k: StepKey; re: RegExp; label: string; detail: string }[] = [
  {
    k: 'cancel',
    re: /\b(stop|cancel|halt|kill|pause)\b/i,
    label: 'Cancel run r-0412',
    detail: 'reject any later send carrying epoch 3',
  },
  {
    k: 'revoke',
    re: /(scratchpad|access|revoke|remove)/i,
    label: 'Remove Reporting Agent’s scratchpad access',
    detail: 'block read · Unregistered Scratchpad · discovery kept',
  },
  {
    k: 'rebuild',
    re: /(rebuild|fresh|approved|redo|regenerate|re-run|rerun)/i,
    label: 'Rebuild the report as r-0413',
    detail: 'context: Internal Report Store only · renew D-07 at epoch 4',
  },
  {
    k: 'keep',
    re: /(keep|preserve|leave|don.t touch)/i,
    label: 'Keep the support work',
    detail: 'check current state before any write · protect human edits',
  },
];

export interface PlanStep {
  k: StepKey;
  label: string;
  detail: string;
  on: boolean;
}

export const parse = (text: string): PlanStep[] =>
  GRAMMAR.map(({ k, re, label, detail }) => ({ k, label, detail, on: re.test(text) }));

export type StepState = 'done' | 'run' | 'wait' | 'conflict' | 'skip';

export function recoverySteps(plan: PlanStep[], b: number) {
  return (['cancel', 'revoke', 'rebuild', 'keep'] as const).map((k) => {
    const requested = plan.find((s) => s.k === k)?.on;
    if (!requested)
      return {
        k,
        label: GRAMMAR.find((s) => s.k === k)!.label,
        state: 'skip' as StepState,
        sub: 'not requested — left as it is',
        subColor: C.mute as string,
      };
    if (k === 'cancel')
      return {
        k,
        label: 'Cancel run r-0412',
        state: (b >= 10 ? 'done' : 'run') as StepState,
        sub:
          b >= 12
            ? 'Late send attempt rejected at the gateway — it still carried epoch 3 (#19).'
            : 'Queued send withdrawn from the outbox.',
        subColor: b >= 12 ? C.red : C.mute,
      };
    if (k === 'revoke')
      return {
        k,
        label: 'Remove scratchpad access',
        state: (b >= 11 ? 'done' : b >= 10 ? 'run' : 'wait') as StepState,
        sub: 'Only the read is severed. Support’s own discovery of the scratchpad is kept.',
        subColor: C.mute as string,
      };
    if (k === 'rebuild')
      return {
        k,
        label: 'Rebuild from approved summaries',
        state: (b >= 15 ? 'done' : b >= 13 ? 'run' : 'wait') as StepState,
        sub:
          b >= 15
            ? 'r-0413 delivered via the approved path (#22).'
            : 'Fresh run — the old one may still hold what it read.',
        subColor: b >= 15 ? C.green : C.mute,
      };
    return {
      k,
      label: 'Keep the support work',
      state: (b >= 14 ? 'conflict' : 'wait') as StepState,
      sub:
        b >= 14
          ? 'Priya edited the internal draft after the agent wrote it. Her version is kept; review requested.'
          : 'Current state will be checked before any write.',
      subColor: b >= 14 ? C.amber : C.mute,
    };
  });
}

export const CHECKS = [
  ['Route removed', 'PS-001 re-run over the contained graph · 0 findings · #23'],
  ['Held action prevented', 'r-0412 send rejected at the gateway · #19'],
  ['Replacement completed', 'r-0413 delivered under D-07 epoch 4 · #22'],
  ['Unrelated work survived', 'Support runs untouched · Priya’s edit preserved · #21'],
] as const;

// ---------------------------------------------------------------------------
// Remember: words to a standing order

const ORDER_LINES = [
  'Standing order SO-1 · agents that send outside never read undeclared storage',
  'Checked as NoUndeclaredReads(senders)',
  'Because of PS-001 · run r-0412 · 4 calls cited',
  'Holds in every later session until you revoke it',
];

/** A standing order starts "from now on" (or similar) and is about undeclared storage. */
export function parseOrder(text: string): { ok: boolean; lines: string[] } {
  const ok =
    /\b(from now on|going forward|from today|always)\b/i.test(text) &&
    /(declar|undeclared|nobody)/i.test(text);
  return { ok, lines: ORDER_LINES };
}
