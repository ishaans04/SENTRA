import { describe, expect, it } from 'vitest';

import {
  CHAPTERS,
  DICTATION,
  EVENTS,
  LAST_BEAT,
  NODES,
  REMEMBER_BEAT,
  REMEMBER_DICTATION,
  VERIFIED_BEAT,
  beatOfEvent,
  chapterFill,
  chapterOf,
  edgeViews,
  nodeView,
  parse,
  parseOrder,
  recoverySteps,
  visibleCount,
} from './story';

describe('the recorded session', () => {
  it('shows every event by the last beat, and the baseline at beat 0', () => {
    expect(EVENTS).toHaveLength(28);
    expect(visibleCount(0)).toBe(7);
    expect(visibleCount(LAST_BEAT)).toBe(EVENTS.length);
  });

  it('jumps from a ledger mark to the beat that revealed it', () => {
    expect(beatOfEvent(0)).toBe(0);
    expect(beatOfEvent(6)).toBe(0);
    expect(beatOfEvent(22)).toBe(VERIFIED_BEAT);
    expect(beatOfEvent(27)).toBe(LAST_BEAT);
    for (let i = 7; i < EVENTS.length; i++) expect(visibleCount(beatOfEvent(i))).toBe(i + 1);
  });

  it('maps beats to chapters and fills each bar once', () => {
    expect(chapterOf(0)).toBe(0);
    expect(chapterOf(8)).toBe(4);
    expect(chapterOf(VERIFIED_BEAT)).toBe(6);
    expect(chapterOf(REMEMBER_BEAT)).toBe(7);
    expect(chapterOf(LAST_BEAT)).toBe(CHAPTERS.length - 1);
    expect(CHAPTERS).toHaveLength(9);
    expect(chapterFill(0, 0)).toBe(1);
    expect(chapterFill(6, 15)).toBe(0);
    expect(chapterFill(6, VERIFIED_BEAT)).toBe(1);
    expect(chapterFill(8, LAST_BEAT)).toBe(1);
  });

  it('never shows internal code names', () => {
    const shown = JSON.stringify([EVENTS, CHAPTERS, NODES]);
    expect(shown).not.toMatch(/\bsentra_core\b|\bSENTRA_[A-Z]/);
  });
});

describe('the map', () => {
  const red = (b: number) =>
    edgeViews(b)
      .filter((e) => e.march)
      .map((e) => e.id);

  it('draws the composed route only while it is open', () => {
    expect(red(4)).toEqual([]);
    expect(red(5)).toEqual(['e1', 'e6', 'e7', 'e8']);
    expect(red(10)).toHaveLength(4);
    expect(red(11)).toEqual([]);
  });

  it('reveals the scratchpad and its edges as they are observed', () => {
    expect(nodeView('scratch', 0).visible).toBe(false);
    expect(nodeView('scratch', 1).visible).toBe(true);
    expect(edgeViews(0).some((e) => e.id === 'e7')).toBe(false);
    expect(edgeViews(2).some((e) => e.id === 'e8')).toBe(false);
    expect(edgeViews(3).some((e) => e.id === 'e8')).toBe(true);
  });

  it('holds, cancels, then rebuilds the reporting run', () => {
    expect(nodeView('reporting', 8).tag?.[0]).toBe('HELD');
    expect(nodeView('reporting', 11).tag?.[0]).toBe('CANCELLED');
    expect(nodeView('reporting', 13).tag?.[0]).toBe('REBUILDING');
    expect(nodeView('reporting', 15).tone).toBe('green');
  });
});

describe('the read-back', () => {
  it('turns the suggested words into all four steps', () => {
    expect(parse(DICTATION).every((s) => s.on)).toBe(true);
  });

  it('requests nothing for empty or unrelated words', () => {
    expect(parse('').some((s) => s.on)).toBe(false);
    expect(parse('what a lovely day').some((s) => s.on)).toBe(false);
  });

  it('skips steps that were not asked for', () => {
    const plan = parse('cancel the run');
    const steps = recoverySteps(plan, 12);
    expect(steps.find((s) => s.k === 'cancel')?.state).toBe('done');
    expect(steps.find((s) => s.k === 'rebuild')?.state).toBe('skip');
  });

  it('keeps the human edit as a conflict, never an overwrite', () => {
    const steps = recoverySteps(parse(DICTATION), 14);
    expect(steps.find((s) => s.k === 'keep')?.state).toBe('conflict');
  });
});

describe('the standing order', () => {
  it('reads the suggested words back as a standing order', () => {
    const order = parseOrder(REMEMBER_DICTATION);
    expect(order.ok).toBe(true);
    expect(order.lines[1]).toBe('Checked as NoUndeclaredReads(senders)');
  });

  it('keeps nothing for words that are not a standing order', () => {
    expect(parseOrder('').ok).toBe(false);
    expect(parseOrder('hello there').ok).toBe(false);
    expect(parseOrder('from now on be nice').ok).toBe(false);
  });

  it('refuses the read a week later, so no route ever opens', () => {
    const red = (b: number) => edgeViews(b).filter((e) => e.march);
    expect(red(19)).toEqual([]);
    expect(red(LAST_BEAT)).toEqual([]);
    expect(nodeView('scratch', 19).sub).toBe('a week later · Support’s notes allowed');
    expect(nodeView('reporting', LAST_BEAT).tag).toEqual(['r-0420 ✓', 'green']);
    expect(EVENTS[26].note).toBe('REFUSED · standing order SO-1 · no route forms');
  });
});
