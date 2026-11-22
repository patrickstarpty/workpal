import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect, it, vi} from 'vitest';
vi.mock('./workflow-tickets-data',()=>({workflowSlug:'workpal-team',loadWorkflowTickets:vi.fn().mockResolvedValue([])}));
import {Overview} from './overview';
import {capabilityView} from './routes';

it('updates a lifecycle stage in place and opens the referenced skill', async () => {
  const open = vi.fn();
  render(<Overview onOpenSkill={open} onNavigate={vi.fn()} onStartStage={vi.fn()}/>);
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

it('offers only the selected stage action and starts that stage without navigating on selection', async () => {
  const start = vi.fn();
  render(<Overview onOpenSkill={vi.fn()} onNavigate={vi.fn()} onStartStage={start}/>);
  const user = userEvent.setup();
  expect(screen.getByRole('button', {name: 'Let’s plan'})).toBeVisible();
  await user.click(screen.getByRole('button', {name: /^Build: Code;/}));
  expect(start).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', {name: 'Let’s plan'})).toBeNull();
  await user.click(screen.getByRole('button', {name: 'Let’s build'}));
  expect(start).toHaveBeenCalledExactlyOnceWith(2);
});

it('does not repeat the top navigation as footer promotions',()=>{
 render(<Overview onOpenSkill={vi.fn()} onNavigate={vi.fn()} onStartStage={vi.fn()}/>);
 expect(screen.queryByRole('button',{name:'Explore skills'})).toBeNull();
 expect(screen.queryByRole('button',{name:'Explore squads'})).toBeNull();
});

it('shows workflow tickets for the selected stage',()=>{
 render(<Overview onOpenSkill={vi.fn()} onNavigate={vi.fn()} onStartStage={vi.fn()}/>);
 expect(screen.getByLabelText('Workflow tickets')).toBeVisible();
});
