/**
 * Ask SENTRA: plain questions about the incident, answered from the recorded
 * session. A question is matched to one of six intents and answered for the
 * current beat only, so an answer never cites an event the replay has not
 * reached. Nothing here calls a model or changes the replay.
 */

import { BRAND } from '../shared/theme';
import { OPERATOR_BEAT, REMEMBER_BEAT, visibleCount, type NodeId } from './story';

export type AskIntent = 'how' | 'talk' | 'allowed' | 'held' | 'leak' | 'next';

export interface Answer {
  intent: AskIntent | null;
  text: string;
  /** Event numbers, 1-based, as the ledger shows them (#01 … #28). */
  cites: number[];
  nodes: NodeId[];
}

export const ASK_SUGGESTIONS: readonly string[] = [
  'How did this happen?',
  'How did the agents talk to each other?',
  'Who allowed the scratchpad?',
  'Why was the report held?',
  'Did data actually leak?',
  'What should I do now?',
];

export const WISPR_URL = 'https://wisprflow.ai/';

/** First match wins, so the narrower intents come before the catch-all "how". */
const INTENTS: [AskIntent, RegExp][] = [
  ['leak', /leak|exfiltrat|escap|got out|get out|left the|sent out|outside/i],
  ['held', /held|hold|paus|withdr|approval|d-07/i],
  ['talk', /talk|communicat|messag|each other|between|shar/i],
  // "Approved" alone is not here: the answer starts "Nobody", which is only true of the scratchpad.
  ['allowed', /allow|permi|declar|who let|without asking|unregistered|scratchpad|notepad/i],
  ['next', /what (should|do|can) i\b|what now|fix|next step|undo|recover/i],
  ['how', /how|why|what happened|explain|cause/i],
];

export function classify(question: string): AskIntent | null {
  const q = question.trim();
  if (!q) return null;
  return INTENTS.find(([, re]) => re.test(q))?.[0] ?? null;
}

const ROUTE_NODES: NodeId[] = ['crm', 'support', 'scratch', 'reporting', 'webhook'];

function reply(intent: AskIntent, b: number): Omit<Answer, 'intent'> {
  const parts: string[] = [];
  const cites: number[] = [];
  const add = (cond: boolean, text: string, ...ev: number[]) => {
    if (!cond) return;
    parts.push(text);
    cites.push(...ev);
  };
  let nodes: NodeId[] = [];

  switch (intent) {
    case 'how':
      add(
        true,
        'No single step broke a rule. Support began writing to a scratchpad nobody declared (#09). Reporting found it (#10) and read it (#12). Reporting is allowed to send outside, so customer records gained a path to the External Webhook: four allowed steps, one route (PS-001).',
        9,
        10,
        12,
      );
      add(b >= 6, 'That broke the reason behind your approval D-07 (#13).', 13);
      add(b >= 7, 'The gateway held the queued report before it left (#14).', 14);
      nodes = ROUTE_NODES;
      break;
    case 'talk':
      add(
        true,
        'They never messaged each other. They met in shared storage: Support wrote to the Unregistered Scratchpad (#09) and Reporting read from it (#12). Each call was allowed on its own, which is why none of them looked wrong.',
        9,
        12,
      );
      add(b >= 20, 'A week later the same read was refused under SO-1 (#27).', 27);
      nodes = ['support', 'scratch', 'reporting'];
      break;
    case 'allowed':
      add(
        true,
        `Nobody. The scratchpad is not in the manifest, so no one ever approved it. ${BRAND} saw Support find it (#08) and marked it UNDECLARED. Every call still went through the gateway, and each one was allowed on its own: no rule covered undeclared storage yet.`,
        8,
      );
      add(b >= 18, 'Standing order SO-1 covers it now (#25).', 25);
      add(b >= 20, 'Reporting’s read was refused under it (#27).', 27);
      nodes = ['scratch'];
      break;
    case 'held':
      if (b < 7) {
        add(
          true,
          'Not yet. Run r-0412 is queued to send (#11). Your approval D-07 lets Reporting send only because it reads sanitized summaries, and since #12 that is no longer true.',
          11,
          12,
        );
        add(b >= 6, 'D-07 now needs review (#13).', 13);
      } else {
        add(
          true,
          `Your approval D-07 let Reporting send only because it read sanitized summaries. At #12 it read the scratchpad, so that reason stopped being true. ${BRAND} withdrew the basis (#13), and a pre-authorised hold stopped run r-0412 at the gateway before it left (#14).`,
          12,
          13,
          14,
        );
        add(b >= 12, 'Its late send was rejected (#19).', 19);
      }
      nodes = ['reporting', 'webhook'];
      break;
    case 'leak':
      if (b < 7) {
        add(
          true,
          `Not that ${BRAND} can show. A route exists (#12), but the report queued at #11 has not been sent. A route is a possible path, not proof either way.`,
          11,
          12,
        );
      } else {
        add(
          true,
          `Not that ${BRAND} can show. The report that could have carried it, r-0412, was held at the gateway before it was sent (#14).`,
          14,
        );
        add(b >= 12, 'Its late send was rejected (#19).', 19);
        add(true, 'A route is a possible path, not proof either way.');
      }
      nodes = ['crm', 'scratch', 'reporting', 'webhook'];
      break;
    case 'next':
      if (b < OPERATOR_BEAT)
        add(
          true,
          `Your turn comes at Decide. Say what to stop, rebuild and keep in Tell ${BRAND}. Nothing runs until you confirm the read-back.`,
        );
      else if (b === OPERATOR_BEAT)
        add(
          true,
          `It’s your turn. Say what to stop, rebuild and keep in Tell ${BRAND}, just below. Nothing runs until you confirm the read-back.`,
        );
      else if (b < REMEMBER_BEAT)
        add(
          true,
          `You already told ${BRAND} what to do (#16). To stop this happening again, keep a standing order when the replay reaches Remember.`,
          16,
        );
      else if (b === REMEMBER_BEAT)
        add(
          true,
          `Say what should always hold in Remember for next time, below. ${BRAND} keeps it only when you confirm.`,
        );
      else
        add(
          true,
          'Nothing more. Standing order SO-1 is kept (#25) and holds in every later session until you revoke it.',
          25,
        );
      break;
  }
  const seen = visibleCount(b);
  return { text: parts.join(' '), cites: cites.filter((n) => n <= seen), nodes };
}

export function answerQuestion(question: string, beat: number): Answer {
  const intent = classify(question);
  if (!intent)
    return {
      intent: null,
      text: 'I can only answer from what this session recorded. Try one of these:',
      cites: [],
      nodes: [],
    };
  return { intent, ...reply(intent, beat) };
}

/** A key the person pressed to type a character. Dictation pastes, so it never counts. */
export const isTyping = (e: {
  key: string;
  ctrlKey: boolean;
  metaKey: boolean;
  altKey: boolean;
}): boolean => e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey;
