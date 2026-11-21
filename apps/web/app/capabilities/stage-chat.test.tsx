import {render, screen, waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {beforeEach, expect, it, vi} from 'vitest';

const mocks = vi.hoisted(() => ({workspace: null as string | null}));
vi.mock('@tanstack/react-query', () => ({useQuery: () => ({data: [{id:'w1',slug:'team',name:'Team'}]})}));
vi.mock('@workpal/core/workspace/queries', () => ({workspaceListOptions: () => ({})}));
vi.mock('@workpal/core/platform', () => ({setCurrentWorkspace: (slug: string | null) => {mocks.workspace=slug;}, getCurrentSlug: () => mocks.workspace}));
vi.mock('@workpal/core/paths', () => ({WorkspaceSlugProvider: ({children}: any) => children}));
vi.mock('@workpal/core/chat', async () => {
 const {create} = await import('zustand');
 const store = create<any>((set) => ({isOpen:false, activeSessionId:null, inputDrafts:{__new__:'My existing requirements'}, startNewChat: () => set({isOpen:true,activeSessionId:null}), setOpen:(isOpen:boolean)=>set({isOpen}), setInputDraft:(key:string,value:string)=>set((s:any)=>({inputDrafts:{...s.inputDrafts,[key]:value}}))}));
 return {DRAFT_NEW_SESSION:'__new__',useChatStore:store};
});
vi.mock('@workpal/views/chat', () => ({ChatWindow: ({contextBar}: any) => <div>{contextBar}</div>}));
vi.mock('@workpal/views/layout', () => ({AppBottomBar: () => <footer>Ask Workpal</footer>}));
import {StageChat} from './stage-chat';
import {useChatStore} from '@workpal/core/chat';
beforeEach(() => {useChatStore.setState({isOpen:false,activeSessionId:null,inputDrafts:{__new__:'My existing requirements'}});});
it('opens an unsent stage draft, preserves user text and replaces stage context on re-entry', async () => {
 const props={stage:0,onStageChange:vi.fn(),onClose:vi.fn()};
 const first=render(<StageChat {...props}/>);
 await screen.findByRole('combobox', {name:'Conversation stage'});
 expect(mocks.workspace).toBe('team');
 expect(useChatStore.getState().inputDrafts.__new__).toContain('My existing requirements');
 expect(useChatStore.getState().activeSessionId).toBeNull();
 await userEvent.setup().selectOptions(screen.getByRole('combobox'), '2');
 expect(props.onStageChange).toHaveBeenCalledWith(2);
 expect(useChatStore.getState().inputDrafts.__new__).toMatch(/^\[03 · Build\]/);
 first.unmount();
 render(<StageChat {...props} stage={1}/>);
 await waitFor(()=>expect(useChatStore.getState().inputDrafts.__new__).toMatch(/^\[02 · Design\]/));
 expect(useChatStore.getState().inputDrafts.__new__).not.toContain('[03 · Build]');
 expect(useChatStore.getState().inputDrafts.__new__).toContain('My existing requirements');
});
