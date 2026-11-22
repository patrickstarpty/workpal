import {fireEvent, render, screen, within} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {describe, expect, it} from 'vitest';
import {SkillHub} from './skill-hub';

describe('Skill Hub', () => {
  it('keeps the search input and caret while typing and delays filtering until IME commits', async () => {
    render(<SkillHub/>);
    const user = userEvent.setup();
    const input = screen.getByRole('searchbox', {name: 'Search skills'}) as HTMLInputElement;
    await user.type(input, 'code');
    expect(input).toHaveValue('code');
    input.setSelectionRange(2, 2);
    await user.keyboard('X');
    expect(input).toHaveValue('coXde');
    expect(input.selectionStart).toBe(3);
    expect(screen.getByRole('searchbox')).toBe(input);
    await user.clear(input);
    const count = screen.getByRole('status').textContent;
    fireEvent.compositionStart(input);
    fireEvent.change(input, {target: {value: '测试'}});
    expect(screen.getByRole('status')).toHaveTextContent(count!);
    fireEvent.compositionEnd(input, {data: '测试'});
    expect(screen.getByRole('status')).toHaveTextContent('0 of 203 entries');
  });
  it('opens a source-linked detail, focuses it, and returns to the same skill card', async () => {
    render(<SkillHub/>);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', {name: 'Show more'}));
    const cards = screen.getAllByRole('button', {name: /^View skill:/});
    const card = cards.at(-1)!;
    await user.click(card);
    const detail = screen.getByRole('region', {name: /Skill details/});
    expect(within(detail).getByRole('heading')).toHaveFocus();
    expect(screen.queryByRole('searchbox')).toBeNull();
    expect(screen.queryByRole('button', {name: 'Show more'})).toBeNull();
    expect(within(detail).getByRole('link', {name: 'Read SKILL.md'})).toHaveAttribute('href', expect.stringMatching(/^https:\/\//));
    await user.click(within(detail).getByRole('button', {name: 'Back to Skill Hub'}));
    expect(screen.getByRole('button', {name: card.getAttribute('aria-label')!})).toHaveFocus();
  });
  it('filters by independent source and type and lets the chart reset to its full category', async () => {
    render(<SkillHub/>);
    const user = userEvent.setup();
    await user.click(screen.getByRole('button', {name: 'Anthropic Skills'}));
    await user.selectOptions(screen.getByLabelText('Skill type'), 'documents');
    expect(screen.getAllByRole('button', {name: /^View skill:/}).length).toBeGreaterThan(0);
    for (const card of screen.getAllByRole('button', {name: /^View skill:/})) expect(card).toHaveTextContent('Anthropic');
    await user.click(screen.getByRole('button', {name: /^Browse Testing & review,/}));
    expect(screen.getByLabelText('Skill type')).toHaveValue('quality');
    expect(screen.getByLabelText('Skill type')).toHaveFocus();
    expect(screen.getByRole('button', {name: 'All sources'})).toHaveAttribute('aria-pressed', 'true');
  });
});
