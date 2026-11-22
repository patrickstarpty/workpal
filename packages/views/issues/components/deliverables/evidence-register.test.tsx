import { beforeEach, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { EvidenceRegister } from './evidence-register';
vi.mock('@workpal/core/workspace/hooks',()=>({useActorName:()=>({getActorName:()=> 'Reviewer'})}));
vi.mock('../../../common/task-transcript',()=>({TranscriptButton:()=>null}));
vi.mock('@workpal/core/hooks',()=>({useWorkspaceId:()=> 'workspace'}));
vi.mock('@workpal/core/api',()=>({getApi:()=>({getBaseUrl:()=>'',getToken:()=> 'token'})}));
const fetcher=vi.fn();
beforeEach(()=>{vi.stubGlobal('fetch',fetcher);fetcher.mockReset();});
function show(){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><EvidenceRegister issueId="ticket"/></QueryClientProvider>);}
it('shows pending evidence and submits the full report without asserting success', async()=>{
 const data={revisions:[],reviews:[],requirements:{requirements:['criteria','exclusions'],test:['method','results','failures','uncovered']}};
 fetcher.mockResolvedValue({ok:true,json:async()=>data});show();
 expect(await screen.findByText(/No deliverables submitted yet/)).toBeTruthy();
 fireEvent.click(screen.getByText('Add deliverable'));
 fireEvent.change(screen.getByLabelText('Type'),{target:{value:'test'}});
 for(const [label,value] of Object.entries({'Title':'Regression','Full document':'Case 1','method':'Manual','results':'Not run','failures':'Unknown','uncovered':'All'})) fireEvent.change(screen.getByLabelText(label),{target:{value}});
 fireEvent.click(screen.getByText('Save record'));
 await waitFor(()=>expect(fetcher.mock.calls.some(([,options])=>options.method==='POST')).toBe(true));
 const options=fetcher.mock.calls.find(([,options])=>options.method==='POST')![1];
 expect(JSON.parse(options.body)).toMatchObject({kind:'test',results:'Not run',content:'Case 1'});
 expect(options.headers['X-Workspace-ID']).toBe('workspace');
});
it('renders document text safely and retains exact revision reviews',async()=>{
 fetcher.mockResolvedValue({ok:true,json:async()=>({requirements:{design:[]},revisions:[{id:'r1',title:'Design',kind:'design',version:1,content:'<script>bad()</script>',sha256:'hash',activity_id:'a1',input_ids:[]}],reviews:[{id:'review',review_of:'r1',decision:'accepted',reviewer_id:'person',scope:'Design only',remaining:'Tests pending',created_at:'2026-11-22'}]})});
 const view=show();
 expect(await screen.findByText('<script>bad()</script>')).toBeTruthy();
 expect(view.container.querySelector('script')).toBeNull();
 expect(screen.getByText('Remaining: Tests pending')).toBeTruthy();
});
