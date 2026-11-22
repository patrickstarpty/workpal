import {render, screen} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {expect, it, vi} from 'vitest';
import {WorkflowTickets} from './workflow-tickets';
import {loadWorkflowTickets} from './workflow-tickets-data';
vi.mock('./workflow-tickets-data', () => ({loadWorkflowTickets: vi.fn(), workflowSlug:'workpal-team'}));
it('groups persisted tickets by stage independently of status and links to the same ticket', async () => {
 vi.mocked(loadWorkflowTickets).mockResolvedValue([
  {id:'delivery', identifier:'TAP-1', title:'Recover uploads', status:'in_review', metadata:{workflow_stage:'build',work_scope:'Full delivery'}},
  {id:'design', identifier:'TAP-2', title:'Design recovery', status:'done', metadata:{workflow_stage:'design',work_scope:'Design only'}},
 ]);
 const {rerender}=render(<WorkflowTickets stage="build"/>);
 expect(await screen.findByRole('link',{name:/Recover uploads/})).toHaveAttribute('href','#/workpal-team/issues/delivery');
 expect(screen.queryByText('Design recovery')).toBeNull();
 await userEvent.selectOptions(screen.getByLabelText('Work status'),'done');
 expect(screen.getByText('No tickets match this stage and status.')).toBeVisible();
 rerender(<WorkflowTickets stage="design"/>);
 expect(await screen.findByRole('link',{name:/Design recovery/})).toBeVisible();
});
it('shows a recoverable load error instead of authored fallback tickets', async()=>{
 vi.mocked(loadWorkflowTickets).mockRejectedValue(new Error('offline'));
 render(<WorkflowTickets stage="plan"/>);
 expect(await screen.findByRole('alert')).toHaveTextContent('Unable to load workflow tickets');
 expect(screen.getByRole('button',{name:'Try again'})).toBeVisible();
});
