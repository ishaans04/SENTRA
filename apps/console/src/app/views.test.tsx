import { act, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Console } from '../console/Console';
import { GuidedDemo } from '../landing/GuidedDemo';
import { Landing } from '../landing/Landing';
import { App } from './App';

const INTERNAL_NAMES = /\bsentra_core\b|\bSENTRA_[A-Z]/;

beforeEach(() => {
  window.location.hash = '';
});

afterEach(() => {
  vi.useRealTimers();
});

describe('routing', () => {
  it('opens the landing page by default and the console on #/console', () => {
    const { unmount } = render(<App />);
    expect(screen.getByText('Watch it happen')).toBeInTheDocument();
    unmount();
    window.location.hash = '#/console';
    render(<App />);
    expect(screen.getByText('One ledger, three lanes')).toBeInTheDocument();
  });
});

describe('landing page', () => {
  it('names only SENTRA', () => {
    render(<Landing />);
    expect(document.body.textContent).toContain('SENTRA');
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });

  it('sets SENTRA against a plain LLM, point by point', () => {
    render(<Landing />);
    expect(screen.getByText(/A chatbot gives advice/)).toBeInTheDocument();
    expect(screen.getAllByText('A plain LLM')).toHaveLength(3);
    expect(screen.getByText('Three differences that matter at work.')).toBeInTheDocument();
    expect(screen.getByText('Why teams choose it.')).toBeInTheDocument();
  });

  it('reads back dictated words and confirms them', () => {
    vi.useFakeTimers();
    render(<Landing />);
    fireEvent.click(screen.getByRole('button', { name: 'Speak' }));
    act(() => vi.advanceTimersByTime(6000));
    expect(screen.getByText('SENTRA WILL:')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Yes, do it' }));
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText(/Only the report was redone/)).toBeInTheDocument();
  });

  it('names four things it does, the fourth being Remember', () => {
    render(<Landing />);
    expect(screen.getByText('Four things. Done carefully.')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Remember/ }));
    expect(screen.getByText('REMEMBER · LIVE')).toBeInTheDocument();
    expect(screen.getByText(/Refused before it started/)).toBeInTheDocument();
  });

  it('shuts everything down, or pauses only the report', () => {
    render(<Landing />);
    fireEvent.click(screen.getByRole('button', { name: 'Shut everything down' }));
    expect(screen.getAllByText('Stopped')).toHaveLength(8);
    fireEvent.click(screen.getByRole('button', { name: 'Use SENTRA' }));
    expect(screen.getByText('Paused')).toBeInTheDocument();
  });
});

describe('guided walkthrough', () => {
  it('steps forward with the keyboard', () => {
    render(<GuidedDemo />);
    expect(screen.getByText('Meet the team')).toBeInTheDocument();
    fireEvent.keyDown(window, { key: 'ArrowRight' });
    expect(screen.getByText('Something new shows up')).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });

  it('keeps a standing order, then shows the week after', () => {
    vi.useFakeTimers();
    render(<GuidedDemo />);
    fireEvent.click(screen.getByRole('button', { name: /Step 8: Remember it for next time/ }));
    expect(screen.getByText('STEP 08 OF 08')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Speak →' }));
    expect(screen.getByText(/never reads from a store nobody declared/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Yes, keep it →' }));
    act(() => vi.advanceTimersByTime(2000));
    expect(screen.getByText('A WEEK LATER')).toBeInTheDocument();
    expect(screen.getByText(/Turned away at the gateway/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });
});

describe('console', () => {
  it('waits for the operator, then runs the confirmed read-back', () => {
    render(<Console />);
    expect(screen.getByText('The approved workflow')).toBeInTheDocument();
    const next = screen.getByRole('button', { name: 'Next event' });
    for (let i = 0; i < 8; i++) fireEvent.click(next);
    expect(screen.getByText('The operator decides, in plain words')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /Confirm read-back and run/ }));
    expect(screen.getByText(/CONFIRMED #16/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });

  it('remembers the incident, then refuses the read a week later', () => {
    vi.useFakeTimers();
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /08 Remember/ }));
    expect(screen.getByText('Remembered for next time')).toBeInTheDocument();
    const box = screen.getByRole('textbox', { name: /Tell SENTRA to remember/ });
    fireEvent.change(box, { target: { value: 'hello there' } });
    const keep = screen.getByRole('button', { name: /Keep this standing order/ });
    expect(keep).toBeDisabled();
    fireEvent.change(box, {
      target: {
        value:
          'From now on, an agent that can send outside never reads from a store nobody declared.',
      },
    });
    fireEvent.click(keep);
    expect(screen.getByText(/CONFIRMED · SO-1/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /09 Next week/ }));
    expect(screen.getByText('A week later, nothing to stop')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next event' }));
    expect(screen.getAllByText(/REFUSED · standing order SO-1/).length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });

  it('jumps to the instruction box with Ctrl+K', () => {
    render(<Console />);
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    expect(screen.getByRole('textbox', { name: /Tell SENTRA/ })).toBeInTheDocument();
  });

  it('cannot confirm words that ask for nothing', () => {
    render(<Console />);
    fireEvent.keyDown(window, { key: 'k', ctrlKey: true });
    fireEvent.change(screen.getByRole('textbox', { name: /Tell SENTRA what to do/ }), {
      target: { value: 'hello there' },
    });
    expect(screen.getByRole('button', { name: /Confirm read-back and run/ })).toBeDisabled();
  });

  it('moves the case file into glass from the route chapter on', () => {
    render(<Console />);
    const next = screen.getByRole('button', { name: 'Next event' });
    for (let i = 0; i < 2; i++) fireEvent.click(next);
    expect(screen.queryByRole('complementary', { name: 'Case file' })).not.toBeInTheDocument();
    expect(screen.getByText('What people approved, and why')).toBeInTheDocument();
    fireEvent.click(next);
    const glass = screen.getByRole('complementary', { name: 'Case file' });
    expect(glass).toHaveClass('is-open');
    expect(glass).toHaveTextContent('What people approved, and why');
    // The page itself no longer shows the case file, open or closed.
    expect(screen.getAllByText('What people approved, and why')).toHaveLength(1);

    fireEvent.click(screen.getByRole('button', { name: 'Close case file' }));
    expect(glass).not.toHaveClass('is-open');
    expect(screen.getAllByText(/DECISION D-07/)).toHaveLength(1);
    fireEvent.click(screen.getByRole('button', { name: /Case file/ }));
    expect(glass).toHaveClass('is-open');

    fireEvent.click(screen.getByRole('button', { name: 'Previous event' }));
    expect(screen.queryByRole('complementary', { name: 'Case file' })).not.toBeInTheDocument();
  });

  it('pops the outcome record up, then docks it in the case file', () => {
    vi.useFakeTimers();
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /07 Verified/ }));
    expect(screen.getByRole('dialog', { name: 'Outcome record' })).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(3000));
    act(() => vi.advanceTimersByTime(600));
    expect(screen.queryByRole('dialog', { name: 'Outcome record' })).not.toBeInTheDocument();
    const glass = screen.getByRole('complementary', { name: 'Case file' });
    expect(glass).toHaveClass('is-open');
    expect(glass).toHaveTextContent('OUTCOME RECORD · REPLAYABLE');
  });

  it('plays to the record and offers a replay', () => {
    vi.useFakeTimers();
    render(<Console />);
    const next = screen.getByRole('button', { name: 'Next event' });
    for (let i = 0; i < 8; i++) fireEvent.click(next);
    fireEvent.click(screen.getByRole('button', { name: /Confirm read-back and run/ }));
    for (let i = 0; i < 8; i++) act(() => vi.advanceTimersByTime(3500));
    expect(screen.getByText('OUTCOME RECORD · REPLAYABLE')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Replay from the start' })).toBeInTheDocument();
  });
});

describe('ask SENTRA', () => {
  const askBox = () => screen.getByRole('textbox', { name: 'Ask SENTRA a question' });
  const NUDGE = 'Faster to say it than type it.';

  it('opens Ask from the header at the route, ready for dictation', () => {
    vi.useFakeTimers();
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: 'Ask SENTRA' }));
    expect(screen.getByText('Four permitted hops compose a route')).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(500));
    expect(askBox()).toHaveFocus();
  });

  it('answers how it happened and lights up the route', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: 'Ask SENTRA' }));
    fireEvent.change(askBox(), { target: { value: 'How did this happen?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask the question' }));
    expect(screen.getByText(/No single step broke a rule/)).toBeInTheDocument();
    expect(document.querySelectorAll('.cx-node.is-asked')).toHaveLength(5);
    expect(document.querySelectorAll('.is-cited')).toHaveLength(3);
    expect(document.body.textContent).not.toMatch(INTERNAL_NAMES);
  });

  it('keeps the Tell read-back waiting when Ctrl+Enter is pressed in Ask', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /05 Decide/ }));
    fireEvent.change(askBox(), { target: { value: 'Why was the report held?' } });
    fireEvent.keyDown(askBox(), { key: 'Enter', ctrlKey: true });
    expect(screen.getByText(/pre-authorised hold stopped run r-0412/)).toBeInTheDocument();
    expect(screen.queryByText(/CONFIRMED #16/)).toBeNull();
    expect(screen.getByText('The operator decides, in plain words')).toBeInTheDocument();
  });

  it('pauses the replay, and a step clears the answer', () => {
    vi.useFakeTimers();
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /04 Withdrawn/ }));
    fireEvent.click(screen.getByRole('button', { name: /▶\s+Play/ }));
    expect(screen.getByRole('button', { name: /Pause/ })).toBeInTheDocument();
    act(() => askBox().focus());
    expect(screen.getByRole('button', { name: /▶\s+Play/ })).toBeInTheDocument();
    fireEvent.change(askBox(), { target: { value: 'Did data actually leak?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask the question' }));
    expect(screen.getByText(/Not that SENTRA can show/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next event' }));
    expect(screen.queryByText(/Not that SENTRA can show/)).toBeNull();
    expect(document.querySelectorAll('.cx-node.is-asked')).toHaveLength(0);
  });

  it('keeps the Wispr Flow tip closed once closed', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /04 Withdrawn/ }));
    fireEvent.keyDown(askBox(), { key: 'h' });
    expect(screen.getByText(NUDGE)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Close tip' }));
    expect(screen.queryByText(NUDGE)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /01 Approved/ }));
    fireEvent.click(screen.getByRole('button', { name: /04 Withdrawn/ }));
    fireEvent.keyDown(askBox(), { key: 'h' });
    expect(screen.queryByText(NUDGE)).toBeNull();
  });

  it('keeps Ctrl+Shift+Enter in Ask away from the Tell read-back', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /05 Decide/ }));
    fireEvent.keyDown(askBox(), { key: 'Enter', ctrlKey: true, shiftKey: true });
    expect(screen.queryByText(/CONFIRMED #16/)).toBeNull();
    expect(screen.getByText('The operator decides, in plain words')).toBeInTheDocument();
  });

  it('does not bring a cleared answer back when stepping back to its beat', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /04 Withdrawn/ }));
    fireEvent.change(askBox(), { target: { value: 'How did this happen?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask the question' }));
    expect(screen.getByText(/No single step broke a rule/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Next event' }));
    fireEvent.click(screen.getByRole('button', { name: 'Previous event' }));
    expect(screen.queryByText(/No single step broke a rule/)).toBeNull();
    expect(document.querySelectorAll('.cx-node.is-asked')).toHaveLength(0);
  });

  it('shows Ask, Tell, Remember as one flow', () => {
    render(<Console />);
    fireEvent.click(screen.getByRole('button', { name: /05 Decide/ }));
    const flows = screen.getAllByRole('list', { name: 'Ask, tell, remember' });
    expect(flows).toHaveLength(2);
    expect(within(flows[1]).getByText('TELL')).toHaveAttribute('aria-current', 'step');
  });
});
