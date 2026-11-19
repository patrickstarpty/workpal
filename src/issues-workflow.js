// Issue lifecycle overview. Uses the same project review destinations as the model.
globalThis.WorkpalIssueFlow = (() => {
  'use strict';
  let app;
  const preferences=new Map();
  const titles={backlog:'Backlog',todo:'To do',active:'In progress',review:'In review',blocked:'Blocked',done:'Done',archived:'Archived',gate:'Delivery checks'};
  function prefs(){
    const id=app.workspace().id;
    if(!preferences.has(id))preferences.set(id,{open:true,project:app.getDb().projects[0]||'',selected:'review'});
    return preferences.get(id);
  }
  function describe(db,project){
    const config=(db.projectSettings||[]).find(p=>p.project===project)||{};
    const workflow=(db.workflows||[]).find(w=>w.id===config.workflowId)||{name:'Default',steps:[]};
    const review=workflow.steps.find(s=>s.status==='review');
    const valid=(value,fallback)=>Object.hasOwn(WorkpalStudio.states,value)?value:fallback;
    const approved=valid(review?.next,'done'),rejected=valid(review?.rejected,'active');
    const completion=config.deliveryRules?.completion||'workflow';
    return {config,workflow,approved,rejected,completion,gated:approved==='done'&&completion!=='workflow'};
  }
  function page(){
    const db=app.getDb(),p=prefs(),esc=app.esc;
    if(p.project&&!db.projects.includes(p.project))p.project=db.projects[0]||'';
    const flow=describe(db,p.project),{config,workflow,approved,rejected,gated,completion}=flow;
    const keys=['backlog','todo','active','review',...(gated?['gate']:[]),'done','archived'];
    const index=Object.fromEntries(keys.map((key,i)=>[key,i]));
    const width=keys.length*190,center=key=>95+index[key]*190;
    const owner=key=>{
      const step=workflow.steps.find(s=>s.status===key);
      return step?.owner==='Project lead'?(config.lead||'Project lead'):step?.owner||'Keep assignee';
    };
    const details={
      backlog:['Capture the request','Define the problem, context and acceptance criteria. Prioritize into To do, or start work directly when ready.'],
      todo:['Ready to start','Assign a person, agent or squad. Starting an execution run moves a Backlog or To do issue into In progress.'],
      active:['Work and verify','Submit a current delivery with artifacts and acceptance evidence to enter In review. Finishing a run alone does not complete an issue.'],
      review:['Human review',`Inspect the current artifacts and acceptance evidence. Request changes → ${titles[rejected]}. Approve → ${gated?'In review until delivery checks are complete':titles[approved]}.`],
      blocked:['Resolve a blocker','Move an issue to Blocked when work cannot continue. Resolve the dependency, then explicitly choose the next status; there is no automatic resume.'],
      gate:['Before completion',`Approval keeps the issue In review. Record every pull request for the current delivery as merged, covering every repository captured at launch. ${completion==='acceptance'?'Then complete the issue with a manual acceptance reason.':db.codeSettings?.afterMerge==='complete'?'The final merge can complete the issue once all requirements are met.':'Then explicitly complete the issue with a reason.'}`],
      done:['Completed work','Done is a completed issue, not a deleted record. Browse it in pages or archive completed tickets to keep the daily view focused. Manual completion requires a reason and must satisfy delivery rules.'],
      archived:['Retained history','Archive only completed issues. They leave the daily list and board while their comments, artifacts and delivery history remain available. Restore returns them to Done.']
    };
    if(!Object.hasOwn(details,p.selected)||p.selected==='gate'&&!gated)p.selected='review';
    const subtitles={backlog:'Define the request',todo:'Assign & prioritize',active:'Implement & verify',review:'Evidence + decision',gate:'Still In review',done:'Complete & retain',archived:'Out of the daily board'};
    const node=(key,x,y,w=150)=>`<g class="issue-flow-node ${p.selected===key?'selected':''}" role="button" tabindex="0" aria-pressed="${p.selected===key}" aria-label="${esc(titles[key]+': '+details[key][0])}" data-issue-flow-node="${key}"><title>${esc(details[key].join('. '))}</title><rect x="${x}" y="${y}" width="${w}" height="82" rx="8"/><circle class="flow-status flow-status-${key}" cx="${x+16}" cy="${y+22}" r="4"/><text class="flow-node-title" x="${x+28}" y="${y+26}">${titles[key]}</text><text x="${x+12}" y="${y+47}">${subtitles[key]||'Resolve & choose next'}</text><text class="flow-node-owner" x="${x+12}" y="${y+65}">${esc(['gate','done','archived','blocked'].includes(key)?({gate:'Merge / acceptance',done:'Paginated history',archived:'Restore → Done',blocked:'Manual transition'})[key]:owner(key).length>22?owner(key).slice(0,21)+'…':owner(key))}</text></g>`;
    const edge=(from,to,label)=>`<path class="flow-edge" d="M ${center(from)+75} 101 H ${center(to)-80}" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${(center(from)+center(to))/2}" y="48" text-anchor="middle">${esc(label)}</text>`;
    let edges=edge('backlog','todo','Prioritize')+edge('todo','active','Start work')+edge('active','review','Submit delivery');
    if(gated)edges+=edge('review','gate','Approve')+edge('gate','done','Complete');
    else if(approved==='done')edges+=edge('review','done','Approve');
    else if(approved!=='blocked'){
      const dest=center(approved),start=center('review');
      edges+=`<path class="flow-edge" d="M ${start} 60 V 18 H ${dest} V 55" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${(start+dest)/2}" y="12" text-anchor="middle">Approve → ${titles[approved]}</text>`;
    }
    edges+=edge('done','archived','Archive');
    const archivedX=center('archived'),doneX=center('done');
    edges+=`<path class="flow-edge flow-return" d="M ${archivedX} 142 V 185 H ${doneX} V 147" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${(archivedX+doneX)/2}" y="202" text-anchor="middle">Restore to Done</text>`;
    const rejectionX=rejected==='blocked'?center('active'):center(rejected);
    edges+=`<path class="flow-edge flow-return" d="M ${center('review')} 142 V 220 H ${rejectionX} V ${rejected==='blocked'?243:147}" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${(center('review')+rejectionX)/2}" y="236" text-anchor="middle">Request changes → ${titles[rejected]}</text>`;
    if(approved==='blocked')edges+=`<path class="flow-edge" d="M ${center('review')+58} 142 V 250 H ${center('active')+80}" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${center('review')+70}" y="272">Approve → Blocked</text>`;
    edges+=`<path class="flow-edge flow-return" d="M ${center('active')-40} 147 V 243" marker-start="url(#issue-flow-arrow)" marker-end="url(#issue-flow-arrow)"/><text class="flow-edge-label" x="${center('active')-50}" y="190" text-anchor="end">Pause / resume</text>`;
    const nodes=keys.map((key,i)=>node(key,20+i*190,60)).join('')+node('blocked',center('active')-75,248);
    const step=workflow.steps.find(s=>s.status===p.selected),detail=details[p.selected];
    return `<section class="issue-flow" aria-label="Issue workflow"><header class="issue-flow-header"><button type="button" data-issue-flow-toggle aria-expanded="${p.open}" aria-controls="issue-flow-content">${app.icon('chevronDown')}<strong>Workflow overview</strong><span>Request → delivery → archive</span></button></header><div id="issue-flow-content" ${p.open?'':'hidden'}><div class="issue-flow-tools"><label>Project <select aria-label="Workflow project" data-issue-flow-project><option value="" ${!p.project?'selected':''}>Default workflow</option>${db.projects.map(project=>`<option value="${esc(project)}" ${p.project===project?'selected':''}>${esc(project)}</option>`).join('')}</select></label><span>${esc(workflow.name)} · Select a stage to see its rules</span><small class="issue-flow-pan-hint">Scroll sideways to explore →</small></div><div class="issue-flow-scroll" tabindex="0" role="region" aria-label="Workflow diagram, scroll horizontally to see all stages"><svg class="issue-flow-map" viewBox="0 0 ${width} 340" style="min-width:${keys.length*160}px" role="group" aria-label="Issue lifecycle and return paths"><defs><marker id="issue-flow-arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z"/></marker></defs>${edges}${nodes}<text class="flow-edge-label" x="20" y="275">Any open stage ↔ Blocked</text><text x="20" y="295">Resolve the blocker, then choose a status.</text></svg></div><div class="issue-flow-detail" role="status" aria-live="polite"><strong>${esc(titles[p.selected]+' · '+detail[0])}</strong><p>${esc(detail[1])}</p>${step?.owner?`<p>Hand off to <b>${esc(owner(p.selected))}</b> on entry.</p>`:''}${step?.instructions?`<p class="issue-flow-instructions">${esc(step.instructions)}</p>`:''}</div><p class="issue-flow-footnote">Project defaults shown; existing runs keep their captured delivery requirements. Status can also be changed manually. Archive preserves the Done status and all history.</p></div></section>`;
  }
  function init(context){
    app=context;
    document.addEventListener('click',event=>{
      if(event.target.closest('[data-issue-flow-toggle]')){
        const p=prefs();p.open=!p.open;app.render();document.querySelector('[data-issue-flow-toggle]')?.focus();return;
      }
      const node=event.target.closest('[data-issue-flow-node]');
      if(node){prefs().selected=node.dataset.issueFlowNode;app.render();document.querySelector(`[data-issue-flow-node="${prefs().selected}"]`)?.focus({preventScroll:true});}
    });
    document.addEventListener('change',event=>{
      if(event.target.matches('[data-issue-flow-project]')){prefs().project=event.target.value;app.render();document.querySelector('[data-issue-flow-project]')?.focus({preventScroll:true});}
    });
    document.addEventListener('keydown',event=>{
      const node=event.target.closest('[data-issue-flow-node]');if(!node)return;
      if(event.key==='Enter'||event.key===' '){event.preventDefault();node.dispatchEvent(new MouseEvent('click',{bubbles:true}));}
      if(event.key==='ArrowRight'||event.key==='ArrowLeft'){
        event.preventDefault();const nodes=[...node.closest('svg').querySelectorAll('[data-issue-flow-node]')],index=nodes.indexOf(node),next=nodes[(index+(event.key==='ArrowRight'?1:-1)+nodes.length)%nodes.length];
        next.focus();
      }
    });
  }
  return {init,page,describe};
})();
