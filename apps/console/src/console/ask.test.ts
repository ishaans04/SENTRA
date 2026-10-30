import { describe, expect, it } from 'vitest';

import { ASK_SUGGESTIONS, WISPR_URL, answerQuestion, classify, isTyping } from './ask';
import { LAST_BEAT, ROUTE_BEAT, visibleCount } from './story';

const beats = Array.from({ length: LAST_BEAT - ROUTE_BEAT + 1 }, (_, i) => ROUTE_BEAT + i);
const key = (k: string, mods: Partial<Record<'ctrlKey' | 'metaKey' | 'altKey', boolean>> = {}) => ({
  key: k,
  ctrlKey: false,
  metaKey: false,
  altKey: false,
  ...mods,
});

describe('ask SENTRA: which question was asked', () => {
  it('routes each suggested question to its own intent', () => {
    expect(ASK_SUGGESTIONS.map(classify)).toEqual([
      'how',
      'talk',
      'allowed',
      'held',
      'leak',
      'next',
    ]);
  });

  it('routes everyday phrasings', () => {
    expect(classify('How was the scratchpad used without permission?')).toBe('allowed');
    expect(classify('how did the agents communicate')).toBe('talk');
    expect(classify('did any customer data get out')).toBe('leak');
    expect(classify('why did this happen')).toBe('how');
    expect(classify('what is the weather')).toBeNull();
    expect(classify('   ')).toBeNull();
    expect(classify('Who approved D-07?')).toBe('held');
    expect(classify('Who approved this?')).toBeNull();
    expect(classify('Who approved the scratchpad?')).toBe('allowed');
  });
});

describe('ask SENTRA: the answers', () => {
  it('never cites an event that has not happened yet', () => {
    for (const q of ASK_SUGGESTIONS)
      for (const b of beats) {
        const a = answerQuestion(q, b);
        const inText = [...a.text.matchAll(/#(\d{2})/g)].map((m) => Number(m[1]));
        for (const n of [...a.cites, ...inText]) expect(n).toBeLessThanOrEqual(visibleCount(b));
      }
  });

  it('answers change as the story moves', () => {
    expect(answerQuestion('Why was the report held?', 5).text).toMatch(/^Not yet\./);
    expect(answerQuestion('Why was the report held?', 7).text).toContain('(#14)');
    expect(answerQuestion('Who allowed the scratchpad?', 20).text).toContain('SO-1');
  });

  it('lights up the route for how it happened', () => {
    expect(answerQuestion('How did this happen?', ROUTE_BEAT).nodes).toEqual([
      'crm',
      'support',
      'scratch',
      'reporting',
      'webhook',
    ]);
  });

  it('admits what it cannot answer', () => {
    const a = answerQuestion('what is the weather', 8);
    expect(a.intent).toBeNull();
    expect(a.cites).toEqual([]);
    expect(a.nodes).toEqual([]);
    expect(a.text).toMatch(/^I can only answer/);
  });

  it('names only SENTRA', () => {
    const all = ASK_SUGGESTIONS.flatMap((q) => beats.map((b) => answerQuestion(q, b).text)).join(
      ' ',
    );
    expect(all).not.toMatch(/HAEGIS|AEGIS|HIVE|sentra_core|SENTRA_[A-Z]/);
  });
});

describe('ask SENTRA: typing or dictation', () => {
  it('tells typing from dictation', () => {
    expect(isTyping(key('h'))).toBe(true);
    expect(isTyping(key('v', { ctrlKey: true }))).toBe(false);
    expect(isTyping(key('Enter'))).toBe(false);
    expect(isTyping(key('Process'))).toBe(false);
    expect(isTyping(key('a', { metaKey: true }))).toBe(false);
  });

  it('points to Wispr Flow', () => {
    expect(WISPR_URL).toBe('https://wisprflow.ai/');
  });
});
