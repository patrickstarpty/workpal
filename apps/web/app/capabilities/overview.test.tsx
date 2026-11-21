import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect, it, vi} from 'vitest';
import {Overview} from './overview';
import {capabilityView} from './routes';

it('updates a lifecycle stage in place and opens the referenced skill', async () => {
  const open = vi.fn();
  render(<Overview onOpenSkill={open} onNavigate={vi.fn()}/>);
  const user = userEvent.setup();
  await user.click(screen.getByRole('button', {name: /^Build: Code;/}));
  expect(screen.getByRole('button', {name: /^Build: Code;/})).toHaveFocus();
  expect(screen.getByRole('heading', {name: 'Turn the accepted design into a change.'})).toBeVisible();
  await user.click(screen.getByRole('button', {name: /^Build: Code;/}));
  expect(screen.getByRole('button', {name: /^Build: Code;/})).toHaveFocus();
  expect(screen.getByText('Review scope changes and technical risks')).toBeVisible();
  await user.click(screen.getByRole('button', {name: 'test-driven-development'}));
  expect(open).toHaveBeenCalledWith('superpowers:skills/test-driven-development/SKILL.md');
});

it('only treats explicit entry routes as capability views, preserving workspace deep links', () => {
  expect(capabilityView('/home')).toBe('overview');
  expect(capabilityView('/home/skills')).toBe('skills');
  expect(capabilityView('/home/team')).toBe('team');
  expect(capabilityView('/workspaces')).toBeNull();
  expect(capabilityView('/landing/skills')).toBeNull();
  expect(capabilityView('/landing')).toBeNull();
  expect(capabilityView('/welcome/projects')).toBeNull();
  expect(capabilityView('/review/issues/task-123')).toBeNull();
  expect(capabilityView('/home/unknown')).toBeNull();
  expect(capabilityView('/%ZZ/projects')).toBeNull();
});
