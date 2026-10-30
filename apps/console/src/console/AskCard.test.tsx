import { fireEvent, render, screen, within } from '@testing-library/react';
import { useRef, useState } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { Answer } from './ask';
import { AskCard } from './AskCard';

function Harness({
  nudgeClosed = false,
  onCloseNudge = () => {},
  onReply = () => {},
}: {
  nudgeClosed?: boolean;
  onCloseNudge?: () => void;
  onReply?: (a: Answer) => void;
}) {
  const [reply, setReply] = useState<Answer | null>(null);
  const ref = useRef<HTMLTextAreaElement>(null);
  return (
    <AskCard
      beat={8}
      reply={reply}
      nudgeClosed={nudgeClosed}
      onCloseNudge={onCloseNudge}
      onStart={() => {}}
      onReply={(a) => {
        onReply(a);
        setReply(a);
      }}
      inputRef={ref}
    />
  );
}

const box = () => screen.getByRole('textbox', { name: 'Ask SENTRA a question' });
const NUDGE = 'Faster to say it than type it.';

afterEach(() => {
  vi.restoreAllMocks();
});

describe('Ask card', () => {
  it('answers a question and shows it', () => {
    render(<Harness />);
    fireEvent.change(box(), { target: { value: 'How did this happen?' } });
    fireEvent.click(screen.getByRole('button', { name: 'Ask the question' }));
    expect(screen.getByText(/No single step broke a rule/)).toBeInTheDocument();
  });

  it('does nothing for an empty question', () => {
    const onReply = vi.fn();
    render(<Harness onReply={onReply} />);
    fireEvent.change(box(), { target: { value: '   ' } });
    expect(screen.getByRole('button', { name: 'Ask the question' })).toBeDisabled();
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(onReply).not.toHaveBeenCalled();
  });

  it('offers suggestions, and all six after a question it cannot place', () => {
    const { container } = render(<Harness />);
    expect(container.querySelectorAll('.cx-chip')).toHaveLength(3);
    fireEvent.change(box(), { target: { value: 'what is the weather' } });
    fireEvent.keyDown(box(), { key: 'Enter' });
    expect(screen.getByText(/I can only answer/)).toBeInTheDocument();
    expect(container.querySelectorAll('.cx-chip')).toHaveLength(6);
    fireEvent.click(screen.getByRole('button', { name: 'Who allowed the scratchpad?' }));
    expect(screen.getByText(/^Nobody\./)).toBeInTheDocument();
  });

  it('keeps Ctrl+Enter to itself', () => {
    const onWindowKey = vi.fn();
    window.addEventListener('keydown', onWindowKey);
    render(<Harness />);
    fireEvent.change(box(), { target: { value: 'Why was the report held?' } });
    fireEvent.keyDown(box(), { key: 'Enter', ctrlKey: true });
    window.removeEventListener('keydown', onWindowKey);
    expect(screen.getByText(/pre-authorised hold stopped run r-0412/)).toBeInTheDocument();
    expect(onWindowKey).not.toHaveBeenCalled();
  });

  it('nudges typists to Wispr Flow, not dictation', () => {
    const onCloseNudge = vi.fn();
    const { rerender } = render(<Harness onCloseNudge={onCloseNudge} />);
    fireEvent.change(box(), { target: { value: 'How did' } });
    expect(screen.queryByText(NUDGE)).toBeNull();
    fireEvent.keyDown(box(), { key: 'v', ctrlKey: true });
    expect(screen.queryByText(NUDGE)).toBeNull();
    fireEvent.keyDown(box(), { key: 'h' });
    expect(screen.getByText(NUDGE)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Try Wispr Flow ↗' });
    expect(link).toHaveAttribute('href', 'https://wisprflow.ai/');
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    fireEvent.click(screen.getByRole('button', { name: 'Close tip' }));
    expect(onCloseNudge).toHaveBeenCalledOnce();
    rerender(<Harness nudgeClosed onCloseNudge={onCloseNudge} />);
    fireEvent.keyDown(box(), { key: 'j' });
    expect(screen.queryByText(NUDGE)).toBeNull();
  });

  it('marks its own step', () => {
    render(<Harness />);
    const steps = screen.getByRole('list', { name: 'Ask, tell, remember' });
    expect(within(steps).getByText('ASK')).toHaveAttribute('aria-current', 'step');
    expect(within(steps).getByText('TELL')).not.toHaveAttribute('aria-current');
  });
});
