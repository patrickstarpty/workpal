"use client";

import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useActorName } from "@workpal/core/workspace/hooks";
import { TranscriptButton } from "../../../common/task-transcript";
import type { AgentTask } from "@workpal/core/types";
import { getApi } from "@workpal/core/api";
import { useWorkspaceId } from "@workpal/core/hooks";
import { Button } from "@workpal/ui/components/ui/button";

type Revision = {id:string; title:string; kind:string; version:number; content:string; sha256:string; run_id:string|null; activity_id:string; input_ids:string[]};
type Review = {id:string; review_of:string; decision:string; reviewer_id:string; scope:string; remaining:string; created_at:string};
type Inventory = {revisions:Revision[]; reviews:Review[]; runs?:Record<string,AgentTask>; inputs?:Record<string,Revision>; requirements:Record<string,string[]>};

export function EvidenceRegister({issueId,onLocate}:{issueId:string;onLocate?:(id:string)=>void}) {
  const {getActorName} = useActorName();
  const workspaceId = useWorkspaceId();
  const cache = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [kind, setKind] = useState('requirements');
  const [previous, setPrevious] = useState<Revision|null>(null);
  const [review, setReview] = useState<Revision|null>(null);
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  async function request(body?: Record<string,unknown>):Promise<Inventory> {
    const api = getApi();
    const token = api.getToken();
    const response = await fetch(`${api.getBaseUrl()}/api/issues/${encodeURIComponent(issueId)}/evidence`, {
      method:body ? 'POST':'GET', credentials:'include',
      headers:{'X-Workspace-ID':workspaceId ?? '', ...(token ? {Authorization:`Bearer ${token}`} : {}), 'Content-Type':'application/json'},
      ...(body ? {body:JSON.stringify(body)} : {}),
    });
    const data = await response.json();
    if(!response.ok) throw new Error(data.error || 'Unable to load delivery evidence');
    return data;
  }
  const query = useQuery({queryKey:['delivery-evidence',workspaceId,issueId], queryFn:()=>request(), enabled:!!workspaceId});
  async function save(event:React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setSaving(true); setError('');
    const fields = Object.fromEntries(new FormData(event.currentTarget).entries());
    try {
      await request(review ? {...fields,review_of:review.id} : {...fields,kind, ...(previous ? {previous_id:previous.id}:{}), input_ids:String(fields.input_ids || '').split(',').map(v=>v.trim()).filter(Boolean)});
      setEditing(false); setReview(null); setPrevious(null);
      await cache.invalidateQueries();
    } catch(e) {setError(e instanceof Error ? e.message : 'Unable to save');}
    finally {setSaving(false);}
  }
  const inputClass = 'w-full rounded-md border border-border bg-background p-2 text-sm';
  return <section className="space-y-3 p-3 text-sm" aria-label="Delivery evidence">
    <h3 className="font-medium">Delivery evidence</h3>
    {query.isPending ? <p role="status">Loading evidence…</p> : query.isError ? <><p role="alert">Unable to load delivery evidence.</p><Button onClick={()=>query.refetch()}>Retry</Button></> : <>
      <p className="text-muted-foreground">{query.data.revisions.length ? 'Submitted documents require review. Decisions apply only to the named revision.' : 'No deliverables submitted yet.'}</p>
      {query.data.revisions.map(item=><details key={item.id} className="rounded-md border border-border p-2">
        <summary className="cursor-pointer">{item.title} · v{item.version} · {item.kind}</summary>
        <div className="space-y-2 pt-2">
          <p className="break-all text-xs">Revision: {item.id}<br/>Activity: {item.activity_id}<br/>Run: {item.run_id || 'Human-authored — no execution run'}<br/>SHA-256: {item.sha256}</p>
          <pre className="whitespace-pre-wrap break-words font-sans text-sm">{item.content}</pre>
          {item.run_id && query.data.runs?.[item.run_id] && <TranscriptButton task={query.data.runs[item.run_id]!} agentName={getActorName("agent",query.data.runs[item.run_id]!.agent_id)} isLive={false} title="View producing Run"/>}
          {onLocate && <Button variant="outline" size="sm" onClick={()=>onLocate(item.activity_id)}>View Activity</Button>}
          {item.input_ids.map(id=>{const input=query.data.inputs?.[id];return <details key={id}><summary className="break-all">Input: {input ? `${input.title} · v${input.version}` : id}</summary><pre className="whitespace-pre-wrap break-words font-sans">{input?.content || 'Input unavailable'}</pre></details>;})}
          {query.data.reviews.filter(r=>r.review_of===item.id).map(r=><div key={r.id} className="border-t pt-2"><p>{r.decision} · {r.created_at}</p><p className="break-all">Reviewer: {getActorName("member",r.reviewer_id)} ({r.reviewer_id})</p><p>Scope: {r.scope}</p><p>Remaining: {r.remaining}</p></div>)}
          <Button variant="outline" size="sm" onClick={()=>{setReview(item);setEditing(false);setError('');}}>Record review</Button>{' '}
          <Button variant="outline" size="sm" onClick={()=>{setPrevious(item);setKind(item.kind);setEditing(true);setReview(null);setError('');}}>New revision</Button>
        </div>
      </details>)}
      <Button variant="outline" size="sm" onClick={()=>{setEditing(true);setPrevious(null);setReview(null);setError('');}}>Add deliverable</Button>
      {(editing || review) && <form key={review?.id || previous?.id || 'new'} onSubmit={save} className="space-y-2">
        <p>{review ? `Review ${review.title} · v${review.version}` : previous ? `Revise ${previous.title}` : 'Submit full deliverable'}</p>
        {review ? <><label className="block">Decision<select aria-label="Decision" className={inputClass} name="decision"><option value="reviewed">Reviewed</option><option value="changes_requested">Changes requested</option><option value="accepted">Accepted</option></select></label>{['scope','remaining'].map(name=><label key={name} className="block capitalize">{name}<textarea className={inputClass} name={name} required /></label>)}</> : <>
          <label className="block">Type<select aria-label="Type" className={inputClass} value={kind} disabled={!!previous} onChange={e=>setKind(e.target.value)}>{Object.keys(query.data.requirements).map(k=><option key={k}>{k}</option>)}</select></label>
          <label className="block">Title<input className={inputClass} name="title" required defaultValue={previous?.title} readOnly={!!previous}/></label>
          <label className="block">Full document<textarea className={inputClass} name="content" required rows={8}/></label>
          {(query.data.requirements[kind] || []).map(name=><label key={name} className="block capitalize">{name}<textarea className={inputClass} name={name} required /></label>)}
          <label className="block">Producing Run ID (optional)<input className={inputClass} name="run_id"/></label>
          <label className="block">Input revision IDs (comma separated)<input className={inputClass} name="input_ids" required={kind==='handoff'}/></label>
          <p className="text-muted-foreground">Include actual evidence. State “not run” or uncovered scope explicitly; submission does not certify a result.</p>
        </>}
        <Button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Save record'}</Button>{' '}<Button type="button" variant="outline" disabled={saving} onClick={()=>{setEditing(false);setReview(null);}}>Cancel</Button>
      </form>}
      {error && <p role="alert">{error}</p>}
    </>}
  </section>;
}
