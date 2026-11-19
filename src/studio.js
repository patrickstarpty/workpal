(() => {
  'use strict';
  let db = WorkpalStudio.db;
  const workspace = () => WorkpalStudio.workspace;
  const {states,teams,stages,handoffs,save,count,next,start,decide,report}=WorkpalStudio;
  const esc=WorkpalData.escapeHtml;
  const $=selector=>document.querySelector(selector);
  const themeKey='workpal.theme';
  let theme='warm';
  try{theme=localStorage.getItem(themeKey)==='neutral'?'neutral':'warm';}catch{}
  function applyTheme(value){
    theme=value==='neutral'?'neutral':'warm';
    document.documentElement.dataset.theme=theme;
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content',theme==='warm'?'#f7f6f3':'#f3f3f4');
  }
  applyTheme(theme);
  function appearance(){
    return box('Appearance',`<div class="appearance-setting"><div><label for="workspace-theme">Theme</label><p id="theme-description">Applies across your workspaces. Saved in this browser.</p></div><select id="workspace-theme" name="workspaceTheme" aria-describedby="theme-description">${options({neutral:'Neutral',warm:'Warm'},theme)}</select></div>`);
  }
  const routes={overview:'Overview',tasks:'All issues',projects:'Projects',workflow:'Runs',agents:'Agents',skills:'Skill Hub',stats:'Analytics',reports:'Reports',inbox:'Inbox',mine:'My work',settings:'Settings',chatroom:'Chat',squads:'Squads',auto:'Autopilots',views:'Saved views',workflows:'Workflows',runtimes:'Runtimes'};
  const icon=k=>`<svg class="icon" aria-hidden="true" viewBox="0 0 24 24"><path d="${WorkpalIcons[k]||WorkpalIcons.layers}"/></svg>`;
  const btn=(text,act,id='',cls='')=>{const label=cls.match(/aria-label="([^"]+)/)?.[1];return `<button type="button" class="btn ${cls}" ${label?'title="'+esc(label)+'"':''} data-act="${act}" data-id="${esc(id)}">${text}</button>`;};
  const tool=(text,type,arg='',cls='')=>btn(text,'surface',type+'|'+arg,cls);
  const nav=(page)=>`<a href="#${scoped(page)}" class="nav ${route().page===page?'active':''}">${icon(page)}<span>${routes[page]}</span>${page==='tasks'?'<small>'+db.tasks.length+'</small>':page==='mine'?'<small>'+db.tasks.filter(t=>t.owner==='Patrick').length+'</small>':''}</a>`;
  const badge=(status)=>`<span class="status ${esc(status)}"><i></i>${esc(states[status]||status)}</span>`;
  const opt=(value,label,selected)=>`<option value="${esc(value)}" ${value===selected?'selected':''}>${esc(label)}</option>`;
  const options=(obj,selected)=>Object.entries(obj).map(([k,v])=>opt(k,v,selected)).join('');
  const field=(label,control)=>`<label>${label}${control}</label>`;
  const select=(name,obj,value)=>`<select name="${name}">${options(obj,value)}</select>`;
  const strings=a=>Object.fromEntries(a.map(x=>[x,x]));
  const input=(name,value='',required=true)=>`<input name="${name}" value="${esc(value)}" maxlength="180" ${required?'required':''}>`;
  const box=(title,body,after='')=>`<section class="panel"><header><h2>${title}</h2>${after}</header>${body}</section>`;
  const empty=t=>`<p class="empty">${t}</p>`;
  const date=t=>new Date(t).toLocaleString('en-US',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
  function scoped(path, id=workspace().id){
    return (id==='tap'?'':'w/'+id+'/')+path;
  }
  function route(){
    const [path,query]=location.hash.slice(1).split('?');
    const segments=path.split('/');
    const nested=segments[0]==='w';
    const page=nested?segments[2]:path;
    return {workspaceId:nested?segments[1]:'tap',page:Object.hasOwn(routes,page)?page:'overview',params:new URLSearchParams(query)};
  }
  let chat=false, mobileMenu=false, focusReturn, modalSurface, timer;
  db.panels ??= [];
  let taskFilter='',skillFilter='',skillStage='',layout='list',filtersOpen=false,navCollapsed=false;
  function issuePrefs(){return db.issueDisplay??={layout:'list',hidden:[],collapsed:[],properties:['priority','project','assignee','due','children']};}
  function issuePropertyVisible(name){return issuePrefs().properties.includes(name);}
  function toast(text){$('#toast').textContent=text;$('#toast').classList.add('on');clearTimeout(timer);timer=setTimeout(()=>$('#toast').classList.remove('on'),2800);}
  function write(){if(!save())toast('Browser storage is unavailable. Export your review before closing.');}
  function form(type,fields,submit,id=''){return `<form data-form="${type}" data-id="${esc(id)}" data-workspace="${esc(workspace().id)}">${fields}<button class="btn primary" type="submit">${esc(submit)} ${icon('arrow')}</button></form>`;}
  const draftTypes=new Set(['deliver','decision','comment','threadReply','note','assignWork','issue','issueProperty','selectDelivery']);
  let draftTab;
  try {draftTab=sessionStorage.getItem('workpal.draftTab')||crypto.randomUUID();sessionStorage.setItem('workpal.draftTab',draftTab);}catch{draftTab=crypto.randomUUID();}
  const draftCache=new Map();
  const draftStorageKey=space=>'workpal.drafts.'+space+'.'+draftTab;
  function draftRecords(space){
    if(!draftCache.has(space)){let data={};try{data=JSON.parse(localStorage.getItem(draftStorageKey(space)))||{};}catch{}draftCache.set(space,data);}
    return draftCache.get(space);
  }
  const draftId=f=>f.dataset.form+'|'+(f.dataset.id||'');
  function persistFormDraft(f){
    if(!f||!draftTypes.has(f.dataset.form)||f.dataset.draftSaved)return;
    const space=f.dataset.workspace||(f.dataset.workspace=workspace().id),record={};
    for(const el of f.elements){if(!el.name||el.type==='hidden'||el.type==='submit')continue;record[el.name]=el.type==='checkbox'?el.checked:el.value;}
    draftRecords(space)[draftId(f)]=record;
    try{localStorage.setItem(draftStorageKey(space),JSON.stringify(draftRecords(space)));}catch{toast('Draft is held in this tab. Browser storage is unavailable.');}
  }
  function captureDrafts(root=document){root.querySelectorAll('form[data-form]').forEach(persistFormDraft);}
  function syncIssueForm(f){
    if(!['issue','issueProperty'].includes(f.dataset.form))return;
    const old=db.tasks.find(t=>t.id===f.dataset.id),status=f.elements.status?.value||old?.status||'todo',owner=f.elements.owner?.value||old?.owner||'Unassigned';
    const toggle=f.querySelector('.dispatch-option'),manual=f.querySelector('.manual-completion');
    if(toggle){toggle.hidden=['backlog','done'].includes(status);f.elements.startAgent.disabled=toggle.hidden;}
    if(manual){manual.hidden=status!=='done'||old?.status==='done';f.elements.manualReason.required=!manual.hidden;}
    const project=f.elements.project?.value??old?.project??'',step=WorkpalStudio.workflowFor(project).steps.find(s=>s.status===status);
    const handoff=(!old&&owner==='Unassigned'||old&&status!==old.status)&&step?.owner;
    const nextOwner=handoff?(step.owner==='Project lead'?projectConfig(project).lead:step.owner):owner;
    const agent=WorkpalStudio.handlingAgent(nextOwner),dispatch=!old||owner!==old.owner||status!==old.status;
    const willQueue=dispatch&&f.elements.startAgent?.checked&&!f.elements.startAgent.disabled&&agent;
    const previousAgent=old&&WorkpalStudio.handlingAgent(old.owner);
    const stopped=old&&nextOwner!==old.owner?db.runs.filter(r=>r.task===old.id&&r.agent===previousAgent?.name&&['queued','running'].includes(r.status)):[];
    let preview=f.querySelector('.operation-preview');if(!preview){preview=document.createElement('p');preview.className='operation-preview';preview.setAttribute('aria-live','polite');f.insertBefore(preview,f.querySelector('button[type=submit]'));}
    preview.textContent='After saving: '+states[status]+' · '+nextOwner+'. '+(willQueue?'Queue one '+(status==='review'?'review':'execution')+' run for '+agent.name+'.':'No new run.')+(stopped.length?' Stop '+stopped.map(r=>r.id).join(', ')+' for the previous assignee.':'')+(status==='done'&&old?.status!=='done'?' Record manual completion; no delivery is approved.':'');
  }
  function restoreDrafts(root=document){
    root.querySelectorAll('form[data-form]').forEach(f=>{
      if(!draftTypes.has(f.dataset.form))return;
      f.dataset.workspace??=workspace().id;
      const values=draftRecords(f.dataset.workspace)[draftId(f)]||{};
      for(const el of f.elements){if(!el.name||!Object.hasOwn(values,el.name)||el.type==='hidden')continue;if(el.type==='checkbox')el.checked=values[el.name];else el.value=values[el.name];}
      syncIssueForm(f);
      if(f.dataset.form==='decision'&&f.elements.choice){const approval=f.elements.choice.value==='approve';f.querySelector('.review-ack')?.toggleAttribute('hidden',!approval);if(f.elements.acknowledged)f.elements.acknowledged.required=approval;if(f.elements.note)f.elements.note.required=!approval;}
      if(f.dataset.form==='assignWork'&&f.elements.status.value==='backlog'){f.elements.queueRun.disabled=true;f.elements.queueRun.checked=false;}
    });
  }
  function clearFormDraft(f){
    f.dataset.draftSaved='true';const space=f.dataset.workspace||workspace().id;
    delete draftRecords(space)[draftId(f)];
    try{localStorage.setItem(draftStorageKey(space),JSON.stringify(draftRecords(space)));}catch{}
    document.querySelectorAll('form[data-form]').forEach(other=>{if(other!==f&&other.dataset.workspace===space&&draftId(other)===draftId(f))other.dataset.draftSaved='true';});
  }
  function showSaveError(err){
    toast(err.message);
    if(err.code!=='WORKSPACE_CONFLICT')return;
    captureDrafts();
    let warning=$('#storage-conflict');if(!warning){warning=document.createElement('aside');warning.id='storage-conflict';warning.setAttribute('role','alert');document.body.append(warning);}
    ($('#dialog').open?$('#dialog'):document.body).append(warning);
    warning.innerHTML='<strong>Another tab changed this record.</strong><p>Your edits and drafts are still here. Export them, or reload the saved workspace; a recovery copy is kept locally.</p>'+actionList([btn('Export unsaved work','exportUnsaved'),btn('Keep recovery copy and reload','reloadSaved')]);
  }
  function actionList(items){return '<div class="actions">'+items.join('')+'</div>';}
  const actorEmoji=name=>db.agents.find(a=>a.name===name)?.emoji||db.memberAvatars?.[name]||'';
  const avatar=(name,cls='')=>'<span class="avatar '+cls+(actorEmoji(name)?' emoji-avatar':'')+'" title="'+esc(name)+'">'+(actorEmoji(name)?esc(actorEmoji(name)):db.agents.some(a=>a.name===name)?icon('agents'):db.squads.some(a=>a.name===name)?icon('squads'):esc(name==='Unassigned'?'—':Array.from(name).slice(0,2).join('')))+'</span>';
  const emojiChoices=['🤖','🧠','🛠️','🔍','🎨','🚀','🦊','🐼','🐙','🦉','🐳','🦄','🌱','🌟','🔥','⚡','💎','🎯','🧪','📚','💻','🛰️','🧭','🦋'];
  function avatarEditor(arg){
    const {name,squad=''}=JSON.parse(arg),value=actorEmoji(name);
    if(!db.agents.some(a=>a.name===name)&&name!=='Patrick')return empty('Member unavailable.');
    return form('avatarEditor','<div class="avatar-editor-identity"><span class="avatar-choice-preview">'+(value?esc(value):icon('agents'))+'</span><div><strong>'+esc(name)+'</strong><small>Used across this workspace</small></div></div>'+
      '<div class="emoji-palette" role="group" aria-label="Suggested emoji">'+emojiChoices.map(emoji=>'<button type="button" data-act="pickEmoji" data-id="'+esc(emoji)+'" aria-label="Use '+esc(emoji)+'" aria-pressed="'+(emoji===value)+'">'+emoji+'</button>').join('')+'</div>'+
      field('Emoji','<input name="emoji" maxlength="32" value="'+esc(value)+'" placeholder="Choose above or paste one emoji" autocomplete="off">')+
      '<input type="hidden" name="name" value="'+esc(name)+'"><input type="hidden" name="squad" value="'+esc(squad)+'">'+btn('Use default avatar','pickEmoji',''),'Save avatar',name);
  }
  function assignWorkEditor(target){
    const squad=db.squads.find(s=>s.name===target),agent=WorkpalStudio.handlingAgent(target);
    if(!squad&&!agent)return empty('Assignee unavailable.');
    return '<div class="assignment-composer">'+form('assignWork',
      '<input class="assignment-title" aria-label="Issue title" name="title" required maxlength="180" placeholder="What needs to be done?">'+
      '<textarea class="assignment-description" aria-label="Description" name="description" rows="4" placeholder="Describe the goal and the context…"></textarea>'+
      '<div class="assignment-properties"><span class="assignment-owner">'+avatar(target)+esc(target)+'</span>'+field('Status',select('status',{todo:'To do',backlog:'Backlog'},'todo'))+field('Priority',select('priority',strings(['Low','Normal','High','Urgent']),'Normal'))+field('Project',select('project',{'':'No project',...strings(db.projects)},db.projects[0]||''))+'</div>'+
      '<details class="assignment-criteria"><summary>Acceptance criteria</summary>'+field('One criterion per line','<textarea name="checks" rows="3" placeholder="What must the delivery demonstrate?"></textarea>')+'</details>'+
      '<div class="assignment-hint"><p>'+ (squad?'Assigned to <strong>'+esc(squad.name)+'</strong>. '+esc(squad.leader)+' is the coordination lead. Member roles and squad instructions are included in the run context.':'Assigned to '+esc(target)+'.')+'</p>'+(!agent?'<p>The leader is unavailable. You can save the issue without a run.</p>':'')+
      '<label class="assign-option"><input type="checkbox" name="queueRun" '+(agent?'checked':'disabled')+'> Queue '+(squad?'leader':'agent')+' run after creation</label><small>Runtime offline. Queuing records the request; it does not execute work.</small></div>','Create issue',target)+'</div>';
  }
  function boardCard(t){
    const children=db.tasks.filter(c=>c.parent===t.id),due=t.due?new Date(t.due+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'}):'';
    const properties=(issuePropertyVisible('project')&&t.project?'<span class="issue-project">'+icon('projects')+esc(t.project)+'</span>':'')+(issuePropertyVisible('labels')?(t.tags||[]).map(tag=>'<span class="issue-project">'+esc(tag)+'</span>').join(''):'');
    return `<button class="issue issue-card" draggable="true" data-act="surface" data-id="issue|${esc(t.id)}"><span class="card-top">${issuePropertyVisible('priority')?'<span class="issue-priority '+esc(t.priority.toLowerCase())+'" title="'+esc(t.priority)+' priority">'+icon('priority')+'</span>':''}<span class="issue-id">${esc(t.id)}</span></span><strong class="issue-title">${esc(t.title)}</strong>${properties?'<span class="card-properties">'+properties+'</span>':''}<span class="card-footer">${issuePropertyVisible('assignee')?avatar(t.owner):''}<span class="card-metadata">${issuePropertyVisible('due')&&due?'<span>'+icon('calendar')+esc(due)+'</span>':''}${issuePropertyVisible('children')&&children.length?'<span>'+icon('tasks')+children.filter(c=>c.status==='done').length+'/'+children.length+'</span>':''}</span></span></button>`;
  }
  function issueList(items, draggable=false){return items.length?items.map(t=>draggable?boardCard(t):`<button class="issue row" data-act="surface" data-id="issue|${esc(t.id)}"><span class="issue-priority ${esc(t.priority.toLowerCase())}" title="${esc(t.priority)} priority">${icon('priority')}</span><span class="issue-id">${esc(t.id)}</span><span class="issue-mark ${esc(t.status)}" title="${esc(states[t.status])}"></span><strong class="issue-title">${esc(t.title)}</strong><span class="issue-project">${icon('projects')}${esc(t.project||'No project')}</span><span class="issue-date">${t.due?esc(new Date(t.due+'T12:00').toLocaleDateString('en-US',{month:'short',day:'numeric'})):''}</span>${avatar(t.owner)}</button>`).join(''):draggable?'':empty('No matching issues.');}
  function runList(items){return items.length?items.map(r=>`<button class="row" data-act="surface" data-id="run|${esc(r.id)}"><span class="tile">${icon('workflow')}</span><span class="grow"><small>${esc(r.id)} / ${esc(r.task||'Chat')} · Offline ${esc(r.kind||'execution')}</small><strong>${esc(db.tasks.find(t=>t.id===r.task)?.title||r.title||'Chat message')}</strong></span>${badge(r.status)}${icon('chevron')}</button>`).join(''):empty('Launch a workflow to record its first decision.');}
  function skillList(items){return items.length?items.map(s=>`<button class="row" data-act="surface" data-id="skill|${esc(s.id)}"><span class="tile">${icon('skills')}</span><span class="grow"><strong>${esc(s.name)}</strong><small>${esc(s.author)} · ${stages[s.stage]}</small></span>${icon('chevron')}</button>`).join(''):empty('No matching skills.');}
  function overview(){
    if(!db.projects.length)return box('Start your first project','<p>Create a project in '+esc(workspace().name)+' to organize issues and agent runs.</p>'+tool('Create project','newProject','','primary'));
    const counts=count(db.tasks);
    return `<div class="section-intro"><h2>Workspace overview</h2><p>Keep track of delivery across ${esc(workspace().name)}.</p>${tool(icon('plus')+' New issue','issue','','primary')}</div>
      <div class="metrics">${[[db.tasks.length,'Total issues','tasks'],[counts.active,'In progress','stats'],[counts.review,'In review','stats'],[db.runs.filter(r=>r.status==='queued').length,'Queued runs','workflow']].map(([v,k,r])=>`<a href="#${scoped(r)}"><small>${k}</small><b>${v}</b>${icon(r)}</a>`).join('')}</div>
      <div class="split">${box('Review queue',issueList(db.tasks.filter(t=>t.status==='review')),'<a href="#'+scoped('tasks')+'">View all '+icon('arrow')+'</a>')}${box('Assigned to me',issueList(db.tasks.filter(t=>t.owner==='Patrick')))}</div>
      ${box('Recent runs',runList(db.runs.slice(0,5)),tool('New run','launch'))}`;
  }
  function stats(team=''){
    team=Object.hasOwn(teams,team)?team:'';
    const items=db.tasks.filter(t=>!team||t.team===team),counts=count(items);
    return `${team?tool('← All teams','stats'):''}<div class="metrics">${Object.entries(states).map(([k,v])=>`<div><small>${v}</small><b>${counts[k]}</b></div>`).join('')}</div>
      ${team?box(esc(teams[team])+' issues',issueList(items)):box('Workload by team',Object.entries(teams).map(([id,name])=>{
        const group=items.filter(t=>t.team===id),dist=count(group);return `<button class="team-row" data-act="surface" data-id="stats|${id}"><span>${name}</span><span class="bars">${Object.keys(states).map(k=>`<i class="${k}" style="width:${100*dist[k]/Math.max(1,items.length)}%"></i>`).join('')}</span><b>${group.length}</b>${icon('chevron')}</button>`;}).join('')+'<div class="legend">'+Object.keys(states).map(badge).join('')+'</div>')}${tool('Generate '+(team?'team':'workspace')+' summary','summary',team)}`;}
  function panelConfig(arg='') {
    const [rawTeam, rawGroup]=arg.split(':');
    const team=Object.hasOwn(teams,rawTeam)?rawTeam:'';
    const group=['project','status','owner'].includes(rawGroup)?rawGroup:'status';
    return {team,group,key:team+':'+group};
  }
  function generatedPanel(arg) {
    const {team,group,key}=panelConfig(arg);
    const items=db.tasks.filter(t=>!team||t.team===team);
    const series=new Map();
    for(const task of items){
      const label=group==='status'?states[task.status]:task[group];
      series.set(label,(series.get(label)||0)+1);
    }
    const largest=Math.max(1,...series.values());
    const chart=[...series].sort((a,b)=>b[1]-a[1]).map(([label,n])=>
      `<div class="data-bar"><span>${esc(label)}</span><i><b style="width:${100*n/largest}%"></b></i><strong>${n}</strong></div>`).join('');
    const pinned=db.panels.includes(key);
    return `<div class="panel-config">${form('panel',field('Team scope',select('team',{'':'All teams',...teams},team))+field('Group issues by',select('group',{status:'Status',project:'Project',owner:'Assignee'},group)),'Update panel')}</div>
      ${box(esc(teams[team]||'Workspace')+' issues',chart||empty('No issues in this scope.'),'<small>'+items.length+' total</small>')}
      ${actionList([btn(pinned?'Unpin panel':'Pin to insights','pin',key),tool('Generate scope summary','summary',team)])}`;
  }
  function pinnedPanels() {
    return box('Pinned panels',db.panels.length?actionList(db.panels.map(key=>{
      const p=panelConfig(key);return tool(esc(teams[p.team]||'Workspace')+' by '+p.group,'panel',p.key);
    })):empty('Build a panel from issue data and pin its configuration here.'),tool('Build panel','panel'));
  }
  const {openRun, changeRun, log} = WorkpalStudio;
  const agentNames = () => db.agents.map(a => a.name);
  const ownerOptions = () => strings(['Unassigned','Patrick',...agentNames(),...db.squads.map(s=>s.name),...db.tasks.map(t=>t.owner)]);
  function issueEditor(id='', draft='', project='', parent, nextStatus='', assignee=''){

    const task=db.tasks.find(t=>t.id===id);
    const current=task && openRun(id);
    const owner=task?.owner||assignee||'Unassigned';
    const status=nextStatus||task?.status||'todo';
    return form('issue', (parent?'<input type="hidden" name="parent" value="'+esc(parent.id)+'"><p>Parent issue · '+esc(parent.id)+' · '+esc(parent.title)+'</p>':'')+field('Issue title',input('title',task?.title||draft))+
      field('Description',`<textarea name="description" rows="3">${esc(task?.description||'')}</textarea>`)+
      '<div class="fields">'+field('Project',select('project',{'':'No project',...strings(db.projects)},task?task.project:(project||db.projects[0])))+
      field('Team',select('team',teams,task?.team||parent?.team||'unassigned'))+
      field('Assignee',select('owner',ownerOptions(),owner))+
      field('Status',select('status',states,status))+
      field('Priority',select('priority',strings(['Low','Normal','High','Urgent']),task?.priority||'Normal'))+
      field('Due date','<input type="date" name="due" value="'+esc(task?.due||'')+'">')+
      field('Labels',input('tags',(task?.tags||[]).join(', '),false))+'</div>'+
      field('Acceptance criteria · one per line',`<textarea name="checks" rows="2">${esc(task?.checks.join('\n')||'')}</textarea>`)+
      `<label class="assign-option dispatch-option" ${!['backlog','done'].includes(status)?'':'hidden'}><input type="checkbox" name="startAgent" checked> Queue the assigned agent or workflow handler</label><label class="manual-completion" ${status==='done'&&task?.status!=='done'?'':'hidden'}>Manual completion reason<textarea name="manualReason" ${status==='done'&&task?.status!=='done'?'required':''} placeholder="Explain why this issue is complete without approving a delivery."></textarea></label>`+
      '',task?'Save changes':'Create issue',id);
  }
  function issueDetail(id,dedicated=false){
    const t=db.tasks.find(t=>t.id===id);
    if(!t)return empty('Issue not found.');
    const children=db.tasks.filter(child=>child.parent===id);
    const active=openRun(id), runs=db.runs.filter(r=>r.task===id), latest=WorkpalStudio.currentDelivery(id);
    return (chat?'<h3>'+esc(id)+' · '+esc(t.title)+'</h3>':'')+`<div class="detail-grid issue-detail-grid"><div class="detail-main"><div class="detail-reading">${dedicated?'<div class="heading"><h1>'+esc(t.title)+'</h1></div>':''}${box('Description','<p class="preserve">'+esc(t.description||'No description.')+'</p>'+
        (t.checks.length?'<h4>Acceptance criteria</h4><ul>'+t.checks.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul>':''),tool('Edit issue','editIssue',id))}
      ${t.completion?box('Completion record','<p><strong>'+(t.completion.kind==='manual'?'Completed manually':'Delivery accepted')+'</strong> · '+date(t.completion.at)+'</p><p class="preserve">'+esc(t.completion.reason||'Acceptance decision recorded.')+'</p><small>This is a historical decision; the current issue status is '+esc(states[t.status])+'.</small>'):''}
      ${box('Deliveries',deliveryHistory(id),latest?tool('Open current delivery','run',latest.run):'')}
      ${box('Sub-issues'+(children.length?' · '+children.filter(c=>c.status==='done').length+'/'+children.length:''),issueList(children),tool('Add sub-issue','childIssue',id))}
      ${box('Activity',t.activity.map(e=>'<div class="entry"><small>'+esc(e.author)+' · '+date(e.at)+'</small><p>'+esc(e.text)+'</p>'+(e.kind==='comment'?'<details '+(e.resolved?'':'open')+'><summary>'+((e.replies||[]).length)+' replies'+(e.resolved?' · Resolved':'')+'</summary>'+(e.replies||[]).map(r=>'<p class="thread-reply"><small>'+esc(r.author)+'</small> '+esc(r.text)+'</p>').join('')+actionList([tool('Reply','threadReply',id+'|'+e.id),btn(e.resolved?'Reopen':'Resolve','resolveThread',id+'|'+e.id)])+'</details>':'')+'</div>').join(''),btn(t.subscribed?'Unsubscribe':'Subscribe','subscribe',id))}
      </div><div class="issue-comment"><form data-form="comment" data-id="${esc(id)}" class="issue-composer"><textarea name="text" aria-label="Add a comment" rows="2" required placeholder="Leave a comment…"></textarea><button type="submit" class="send" aria-label="Post comment" title="Post comment">${icon('arrow')}</button></form></div></div><div class="detail-properties">${box('Properties','<dl class="properties">'+Object.entries({Status:states[t.status],Assignee:t.owner,Priority:t.priority,Project:t.project||'No project',Team:teams[t.team],'Due date':t.due||'No date',Labels:(t.tags||[]).join(', ')||'None'}).map(([k,v])=>{
        const key={Status:'status',Assignee:'owner',Priority:'priority','Due date':'due'}[k];
        return '<dt>'+k+'</dt><dd>'+(key?tool(esc(v),'issueProperty',t.id+'|'+key,'property-button'):esc(v))+'</dd>';
      }).join('')+'</dl>'+(t.parent?tool('Parent issue · '+esc(t.parent),'issue',t.parent):''))}
      ${t.status==='review'&&latest?box('Review',tool('Review delivery v'+latest.version,'run',latest.run)):''}
      ${quickActionsView(t.id)}${wakeupList(t)}
      ${box('Agent runs',runList(runs),active?'':tool('Start run','launch',id))}</div></div>`;
  }
  const offlineNotice=()=>'';
  const evidenceStates={supported:'Evidence provided',missing:'Evidence missing',unmet:'Not met','not-applicable':'Not applicable · explain why'};
  function deliveryHistory(taskId){
    const deliveries=db.deliveries.filter(d=>d.task===taskId).sort((a,b)=>b.version-a.version);
    return deliveries.length?deliveries.map((d,i)=>`<button class="row delivery-row" data-act="surface" data-id="run|${esc(d.run)}"><span class="grow"><strong>Delivery v${d.version} · ${esc(d.summary)}</strong><small>${d.disposition==='current'?'Current':d.disposition==='candidate'?'Candidate':'Historical'} · ${esc(d.run)} · ${d.review?d.review.decision==='approve'?'Approved':'Changes requested':'Awaiting review'}</small></span>${icon('chevron')}</button>`).join(''):empty('No delivery yet. Submit a summary, an artifact and evidence for each acceptance criterion.');
  }
  function delegationContext(taskId,agentName,skillId){
    const t=db.tasks.find(t=>t.id===taskId),a=db.agents.find(a=>a.name===agentName);
    if(!t||!a)return empty('Choose an issue and agent.');
    const project=projectConfig(t.project),s=db.skills.find(s=>s.id===(skillId||a.skills[0])),existing=openRun(t.id,a.name,'execution'),prior=WorkpalStudio.currentDelivery(t.id);
    return '<h3>Delegation context</h3>'+ (existing?'<p class="review-warning">'+esc(existing.id)+' is already open. Reopening keeps its original input snapshot. Cancel or finish it to change inputs.</p>':'')+(prior?.review?'<div class="decision-receipt"><strong>Previous decision · Delivery v'+prior.version+'</strong><p>'+esc(prior.review.note||prior.review.decision)+'</p></div>':'')+propertyList({Goal:t.title,Agent:a.name,Project:t.project||'No project',Skill:s?s.name+' · '+(s.version||'unversioned'):'None',Runtime:'Offline',Instructions:a.instructions||a.role||'None'})+
      '<p class="preserve">'+esc(project.description||'No project context recorded.')+'</p><h4>Acceptance criteria</h4>'+(t.checks.length?'<ul>'+t.checks.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul>':empty('Add acceptance criteria before a delivery can be approved.'))+
      '<small>The issue, agent, project and selected skill are captured when this attempt is created. Retry uses the current settings shown here.</small>';
  }
  function launch(arg){
    const [selected,followUp]=arg.split('~'), task=db.tasks.find(t=>t.id===selected)||db.tasks[0];
    if(!task)return empty('Create an issue before starting a run.')+tool('Create issue','issue');
    if(!db.agents.length)return empty('Configure an agent for this workspace to start a run.')+tool('Configure agent','newAgent');
    const agent=WorkpalStudio.handlingAgent(task.owner)?.name||agentNames()[0];
    return offlineNotice()+form('launch',field('Issue',select('task',Object.fromEntries(db.tasks.map(t=>[t.id,t.id+' · '+t.title])),task.id))+
      field('Run agent',select('agent',strings(agentNames()),agent))+
      field('Skill',select('skill',{'':'Agent default',...Object.fromEntries(db.skills.map(s=>[s.id,s.name]))}))+
      field('On completion',select('followUp',{'':'Keep execution trace',report:'Generate execution report'},followUp))+
      '<div class="delegation-context">'+delegationContext(task.id,agent,'')+'</div>','Start workflow');
  }
  function deliveryContent(d){
    return '<p class="preserve">'+esc(d.summary)+'</p><h4>Artifacts</h4>'+(d.artifacts.length?d.artifacts.map(a=>'<details class="artifact" open><summary>'+esc(a.title)+'</summary><pre>'+esc(a.body)+'</pre></details>').join(''):empty('No artifact provided.'))+
      '<h4>Acceptance evidence</h4>'+(d.evidence.length?d.evidence.map(e=>'<div class="evidence-row"><strong>'+esc(e.criterion)+'</strong><small>'+esc(e.evidence?.trim()?(evidenceStates[e.status]||'Evidence provided'):'Evidence missing')+'</small><p class="preserve">'+esc(e.evidence||'No evidence provided.')+'</p></div>').join(''):empty('Original acceptance evidence is unavailable.'))+
      '<h4>Open questions and limitations</h4><p class="preserve">'+esc(d.limitations||'Not recorded.')+'</p>';
  }
  function deliveryView(d){
    const previous=db.deliveries.find(p=>p.id===d.supersedes),latest=WorkpalStudio.currentDelivery(d.task);
    return box('Delivery v'+d.version, '<p class="delivery-meta">'+esc(d.id)+' · '+esc(d.run)+' · '+date(d.createdAt)+' · '+(latest?.id===d.id?'Current delivery':d.disposition==='candidate'?'Candidate delivery':'Historical version')+'</p>'+(d.candidateReason?'<p class="review-warning">'+esc(d.candidateReason)+' This result has been kept without changing the current decision.</p>':'')+deliveryContent(d)+
      (d.review?'<div class="decision-receipt"><strong>'+ (d.review.decision==='approve'?'Approved':'Changes requested')+'</strong><p class="preserve">'+esc(d.review.note||d.review.reason||'')+'</p><small>'+esc(d.review.author||d.review.reviewer||'Patrick')+' · '+(d.review.at?date(d.review.at):'Original date unavailable')+' · This decision applies to v'+d.version+' only.</small></div>':'')+
      (previous?'<details class="delivery-comparison"><summary>Compare v'+previous.version+' → v'+d.version+'</summary><div class="delivery-columns"><section><h4>Previous · v'+previous.version+'</h4>'+deliveryContent(previous)+'</section><section><h4>Current · v'+d.version+'</h4>'+deliveryContent(d)+'</section></div>'+tool('Open previous delivery','run',previous.run)+'</details>':''));
  }
  function inputSnapshotView(r){
    const s=r.inputSnapshot;
    if(!s||r.snapshotUnavailable)return '<details class="artifact"><summary>Input snapshot unavailable</summary><p>Historical requirements were not captured. Start a new attempt to record current inputs.</p></details>';
    return '<details class="artifact"><summary>Input snapshot · '+date(s.capturedAt)+'</summary>'+(s.previousDelivery?'<div class="decision-receipt"><strong>Previous delivery · v'+s.previousDelivery.version+'</strong><p>'+esc(s.previousDelivery.review?.note||s.previousDelivery.summary)+'</p></div>':'')+propertyList({Goal:s.task.title,Project:s.task.project||'No project',Agent:s.agent.name,Skill:s.skill?s.skill.name+' · '+(s.skill.version||'unversioned'):'None'})+'<p class="preserve">'+esc(s.task.description)+'</p><ul>'+s.task.checks.map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul><details><summary>Agent, project and skill details</summary><pre>'+esc(JSON.stringify({agent:s.agent,context:s.context,skill:s.skill,workflow:s.workflow},null,2))+'</pre></details></details>';
  }
  function run(id){
    const r=db.runs.find(x=>x.id===id);
    if(!r)return empty('Run not found.');
    const t=db.tasks.find(t=>t.id===r.task);
    if(!t)return offlineNotice()+box(esc(r.title||'Chat run'),propertyList({Agent:r.agent,Status:r.status,Context:r.context?.project||'No project'})+'<ol class="trace">'+r.events.map(e=>'<li><code>'+esc(e.type)+'</code><span>'+esc(e.text)+'</span></li>').join('')+'</ol>'+btn('Open conversation','openThread',r.conversation));
    const d=db.deliveries.find(d=>d.run===id),checks=r.inputSnapshot?.task?.checks||[],kind=r.kind||'execution';
    let actions='';
    if(r.status==='queued')actions=btn('Start run','claimRun',id,'primary')+btn('Cancel run','cancel',id);
    if(r.status==='running'&&kind==='execution')actions=form('deliver',field('Summary','<textarea name="note" required placeholder="What changed, and what should the reviewer check?"></textarea>')+
      '<fieldset><legend>Artifact</legend>'+field('Artifact title',input('artifactTitle','',false))+field('Artifact content or reference','<textarea name="artifactBody" rows="4" placeholder="Paste a document, change excerpt, or reference for the reviewer. Text is saved locally."></textarea>')+'</fieldset>'+
      '<fieldset><legend>Acceptance evidence</legend><small>Record evidence or mark what is still missing.</small>'+checks.map((c,i)=>'<div class="evidence-input">'+field(esc(c),'<textarea name="evidence'+i+'" rows="2"></textarea>')+field('Evidence status · '+(i+1),select('evidenceStatus'+i,evidenceStates,'supported'))+'</div>').join('')+(checks.length?'':empty('No criteria captured. Add criteria to the issue and start a new attempt before approval.'))+'</fieldset>'+
      field('Open questions and limitations','<textarea name="limitations" placeholder="Record unresolved questions, scope limits, or explicitly state none."></textarea>'),'Submit for review',id)+actionList([btn('Finish without delivery','finishRun',id),btn('Cancel run','cancel',id)]);
    if(r.status==='running'&&kind==='review')actions=form('deliver',field('Review findings','<textarea name="note" required placeholder="Record findings, missing evidence and questions for the decision maker."></textarea>'),'Save review note',id)+actionList([(WorkpalStudio.currentDelivery?.(t.id)||WorkpalStudio.latestDelivery(t.id))?tool('Open delivery for review','run',(WorkpalStudio.currentDelivery?.(t.id)||WorkpalStudio.latestDelivery(t.id)).run):'',btn('Finish without delivery','finishRun',id),btn('Cancel run','cancel',id)]);
    if(kind==='reply'&&r.status==='running')actions=form('deliver',field('Response · recorded by you','<textarea name="note" required></textarea>'),'Save response',id)+btn('Cancel request','cancel',id);
    if(d&&!d.review){
      const unavailable=WorkpalStudio.reviewEligibility(d),approval=WorkpalStudio.approvalEligibility(d);
      const step=WorkpalStudio.workflowFor(t.project).steps.find(s=>s.status==='review');
      if(!unavailable)actions=form('decision',`<input type="hidden" name="stage" value="${r.stage}">`+
        '<p>Review delivery v'+d.version+'. Approval moves this issue to <strong>'+esc(states[step?.next||'done'])+'</strong>. Requesting changes moves it to '+esc(states[step?.rejected||'active'])+'.</p>'+
        (approval?'<p class="review-warning">'+esc(approval)+'</p>':'')+
        field('Decision',select('choice',approval?{return:'Request changes'}:{approve:'Approve → '+states[step?.next||'done'],return:'Request changes'},approval?'return':'approve'))+
        field('Review note','<textarea name="note" '+(approval?'required':'')+' placeholder="Explain the decision or the changes needed."></textarea>')+
        '<label class="assign-option review-ack" '+(approval?'hidden':'')+'><input type="checkbox" name="acknowledged" '+(approval?'':'required')+'> I reviewed the artifacts, each criterion and the limitations for v'+d.version+'.</label>','Record decision',id);
      else actions='<p class="review-warning">'+esc(unavailable)+'</p>'+ (WorkpalStudio.currentDelivery(t.id)?.id!==d.id&&WorkpalStudio.currentDelivery(t.id)?tool('Open current delivery','run',WorkpalStudio.currentDelivery(t.id).run):'')+form('selectDelivery','<p>Choosing this version makes it the current delivery and moves the issue to In review. Other results and decisions stay in the history.</p>'+field('Selection reason','<textarea name="reason" required></textarea>'),'Select for review',d.id);
    }
    if(kind==='execution'&&(['cancelled','failed'].includes(r.status)||r.reviewDecision==='return'||(r.status==='finished'&&!d)))actions=tool('Start another attempt','launch',t.id);
    return `<div class="run-title">${tool(esc(t.id),'issue',t.id)}${badge(r.status)}</div><h3>${esc(r.inputSnapshot?.task?.title||t.title)}</h3><p>${esc(r.agent||t.owner)} · ${esc(r.skill||'No attached skill')} · ${esc(kind)} · Runtime offline</p>`+offlineNotice()+inputSnapshotView(r)+
      (d?deliveryView(d):'')+`<div class="gate"><h3>${({queued:'Waiting for your input',failed:'Run failed',running:'In progress',cancelled:'Run cancelled',finished:'Run ended'})[r.status]||esc(r.status)}</h3><p>Issue status: ${esc(states[t.status])}. Ending a run does not approve its delivery.</p>${actions}</div>`+
      (!d&&r.artifacts.length?'<h4>Recorded notes</h4>'+r.artifacts.map(a=>'<details class="artifact"><summary>'+esc(a.title)+'</summary><pre>'+esc(a.body)+'</pre></details>').join(''):'')+
      `<h4>Execution log · local records</h4><ol class="trace">${r.events.slice().reverse().map(e=>'<li><code>'+esc(e.type)+'</code><span>'+esc(e.text)+'</span><small>'+date(e.at)+'</small></li>').join('')}</ol>${tool('Generate execution report','execution',id)}`;
  }
  let issueStatus='',issueOwner='';
  function tasks(){
    const items=db.tasks.filter(t=>(!issueStatus||t.status===issueStatus)&&(!issueOwner||t.owner===issueOwner)&&
      (t.id+' '+t.title+' '+t.project+' '+t.owner).toLowerCase().includes(taskFilter.toLowerCase()));
    const toolbar='<div class="toolbar issue-filters" '+(filtersOpen?'':'hidden')+'><div class="search-field">'+icon('search')+'<input aria-label="Filter issues" data-filter="task" placeholder="Search issues…" value="'+esc(taskFilter)+'"></div>'+
      '<select aria-label="Filter by status" data-issue-status>'+options({'':'All statuses',...states},issueStatus)+'</select>'+
      '<select aria-label="Filter by assignee" data-issue-owner>'+options({'':'All assignees',...ownerOptions()},issueOwner)+'</select>'+tool('Save view','saveView')+'</div>';
    const groupHeader=(key,label,number)=>'<header class="issue-group-header">'+(layout==='list'?btn(icon('chevronDown'),'collapseGroup',key,'group-toggle '+(issuePrefs().collapsed.includes(key)?'collapsed':'')+'" aria-label="'+(issuePrefs().collapsed.includes(key)?'Expand ':'Collapse ')+label):'')+'<span class="issue-mark '+key+'"></span><strong>'+label+'</strong><small>'+number+'</small><span class="group-actions">'+(layout==='board'?'<details class="column-options"><summary role="button" aria-label="More actions for '+label+'">'+icon('more')+'</summary><div class="column-menu">'+btn('Hide column','hideColumn',key)+'</div></details>':'')+tool(icon('plus'),'statusIssue',key,'icon-only" aria-label="New issue in '+label)+'</span></header>';
    const groups=Object.entries(states).filter(([key])=>!issuePrefs().hidden.includes(key));
    return toolbar+(layout==='list'?'<div class="issue-groups">'+(groups.map(([key,label])=>{const group=items.filter(t=>t.status===key);return group.length?'<section class="issue-group" data-group="'+key+'">'+groupHeader(key,label,group.length)+'<div '+(issuePrefs().collapsed.includes(key)?'hidden':'')+'>'+issueList(group)+'</div></section>':'';}).join('')||empty('No matching issues.'))+'</div>':'<div class="board" aria-label="Issue board">'+groups.map(([key,label])=>{const group=items.filter(t=>t.status===key);return '<section class="board-lane" data-drop-state="'+key+'">'+groupHeader(key,label,group.length)+'<div class="board-cards" tabindex="0" aria-label="'+label+' issues">'+issueList(group,true)+'</div></section>';}).join('')+'</div>');
  }
  function issueDisplay(){
    const prefs=issuePrefs();
    return '<details class="display-dropdown"><summary class="icon-only" role="button" aria-haspopup="menu" aria-label="Display" title="Display">'+icon(layout==='board'?'board':'list')+'</summary><div class="display-menu"><div class="layout-options">'+['board','list'].map(value=>btn(icon(value)+'<span>'+value[0].toUpperCase()+value.slice(1)+'</span>','setLayout',value,(layout===value?'selected':'')+'" aria-label="'+(value==='board'?'Board view':'List view'))).join('')+'</div><div class="display-setting"><span>Grouping</span><span>Status</span></div><h3>Columns</h3><div class="display-chips">'+Object.entries(states).map(([key,label])=>btn('<span class="issue-mark '+key+'"></span>'+label,'toggleColumn',key,prefs.hidden.includes(key)?'':'selected')).join('')+'</div><h3>Card properties</h3><div class="display-chips">'+Object.entries({priority:'Priority',assignee:'Assignee',due:'Due date',project:'Project',labels:'Labels',children:'Sub-issue progress'}).map(([key,label])=>btn(label,'toggleCardProperty',key,prefs.properties.includes(key)?'selected':'')).join('')+'</div></div></details>';
  }
  const projectConfig=name=>db.projectSettings.find(p=>p.project===name)||{project:name,lead:'Patrick',description:'',reviewer:'',due:''};
  function projectPage(name){
    if(!db.projects.includes(name))return empty('Project not found.');
    const p=projectConfig(name),items=db.tasks.filter(t=>t.project===name);
    return `<div class="detail-grid"><div>${box('Description','<p class="preserve">'+esc(p.description||'Add context for issues and agent runs.')+'</p>',tool('Edit project','projectConfig',name))}
      ${box('Project issues',issueList(items),tool('＋ New issue','projectIssue',name))}</div><div>${box('Properties',propertyList({Lead:p.lead,'Due date':p.due||'No date',Workflow:WorkpalStudio.workflowFor(name).name,Progress:items.filter(t=>t.status==='done').length+' / '+items.length}))}</div></div>`;
  }
  function propertyList(values){return '<dl class="properties">'+Object.entries(values).map(([k,v])=>'<dt>'+esc(k)+'</dt><dd>'+esc(v)+'</dd>').join('')+'</dl>';}
  function workflowsPage(){
    return box('Workflows','<p>Choose the handoff, brief and next status for each step. Projects can share a workflow.</p>'+
      db.workflows.map(w=>tool(esc(w.name),'workflowEditor',w.id,'thread-row')).join(''),tool('New workflow','workflowEditor'));
  }
  function workflowEditor(id){
    const w=db.workflows.find(w=>w.id===id);
    const steps=w?.steps||Object.keys(states).map(status=>({status,owner:'',instructions:'',next:status==='active'?'review':status==='review'?'done':status,rejected:'active'}));
    return form('workflowEditor',field('Workflow name',input('name',w?.name))+
      steps.map(step=>'<fieldset><legend>'+esc(states[step.status])+'</legend>'+
        field('Hand to',select(step.status+'Owner',{'':'Keep assignee','Project lead':'Project lead',Patrick:'Patrick',...strings(agentNames())},step.owner))+
        field('Instructions','<textarea name="'+step.status+'Instructions" rows="2">'+esc(step.instructions)+'</textarea>')+
        '<div class="fields">'+(step.status==='active'?'<div><strong>Delivery goes to In review</strong><p>Every submitted delivery needs a review decision.</p><input type="hidden" name="activeNext" value="review"></div>':field('When done, move to',select(step.status+'Next',states,step.next)))+
        field('If rejected, send back to',select(step.status+'Rejected',states,step.rejected))+'</div></fieldset>').join(''),'Save workflow',id);
  }
  function projectEditor(name){
    const p=projectConfig(name);
    return form('projectConfig',field('Description','<textarea name="description" rows="4">'+esc(p.description)+'</textarea>')+
      field('Project lead',select('lead',strings(['Patrick',...agentNames()]),p.lead))+field('Due date','<input name="due" type="date" value="'+esc(p.due)+'">')+
      field('Workflow',select('workflowId',{'default':'Default',...Object.fromEntries(db.workflows.map(w=>[w.id,w.name]))},p.workflowId||'default')),'Save project',name);
  }
  function squads(){
    return '<div class="agent-table squad-table"><div class="table-head"><span>Name</span><span>Leader</span><span>Members</span><span>Created by</span></div>'+db.squads.map(s=>'<button class="agent-row" data-act="surface" data-id="squad|'+esc(s.name)+'"><span class="actor-name" title="'+esc(s.description||s.name)+'">'+avatar(s.name)+'<strong>'+esc(s.name)+'</strong></span><span class="cell-meta">'+avatar(s.leader)+esc(s.leader)+'</span><span class="avatar-stack">'+s.members.slice(0,3).map(m=>avatar(m)).join('')+'<small>'+s.members.length+'</small></span><span class="cell-meta">'+avatar('Patrick')+'Patrick</span></button>').join('')+(db.squads.length?'':empty('No squads yet.'))+'</div>';
  }
  function squadEditor(name){
    if(!db.agents.length)return empty('Configure an agent to lead the squad.')+tool('Configure agent','newAgent');
    const s=db.squads.find(item=>item.name===name);
    const people=[...agentNames(),'Patrick'];
    const roster=people.map((person,i)=>'<div class="roster-edit"><label><input type="checkbox" name="members" value="'+esc(person)+'" '+(s?.members.includes(person)?'checked':'')+'> '+esc(person)+'</label>'+
      '<input aria-label="Role for '+esc(person)+'" name="memberRole'+i+'" placeholder="Role in this squad" value="'+esc(s?.roles?.find(r=>r.name===person)?.role||'')+'"></div>').join('');
    return form('squadEditor',field('Squad name',input('name',s?.name))+field('Description',input('description',s?.description||'',false))+
      field('Leader',select('leader',strings(agentNames()),s?.leader))+'<fieldset><legend>Members</legend>'+roster+'</fieldset>'+
      field('Instructions','<textarea name="instructions" rows="3">'+esc(s?.instructions||'')+'</textarea>'),'Save squad',name);
  }
  function squadPage(name){
    const s=db.squads.find(x=>x.name===name);if(!s)return empty('Squad unavailable.');
    const members=s.members.map(member=>'<div class="squad-member-row"><button type="button" class="member-avatar-button" data-act="surface" data-id="'+esc('avatarEditor|'+JSON.stringify({name:member,squad:name}))+'" aria-label="Change avatar for '+esc(member)+'">'+avatar(member)+'</button><div class="member-identity">'+(db.agents.some(a=>a.name===member)?tool(esc(member),'agent',member,'member-name'): '<strong>'+esc(member)+'</strong>')+'<small>'+esc(s.roles?.find(r=>r.name===member)?.role|| (member==='Patrick'?'Workspace member':'Agent'))+'</small></div><span class="member-role">'+(member===s.leader?'Leader':'Member')+'</span></div>').join('');
    return '<div class="detail-grid squad-detail"><div>'+box('Members · '+s.members.length,members,tool('Manage members','squadEditor',name))+
      box('Instructions','<p class="preserve">'+esc(s.instructions||'No instructions yet.')+'</p>',tool('Edit','squadEditor',name))+box('Recent work',issueList(db.tasks.filter(t=>t.owner===name)))+
      '</div><div>'+box('Properties','<p>'+esc(s.description||'')+'</p>'+propertyList({Leader:s.leader,Visibility:'Workspace','Created by':'Patrick'}))+'</div></div>';
  }

  function autopilots(){
    return '<div class="agent-table autopilot-table"><div class="table-head"><span>Name</span><span>Agent</span><span>Schedule</span><span>Status</span></div>'+db.autopilots.map(a=>'<button class="agent-row" data-act="surface" data-id="autopilot|'+esc(a.id)+'"><span class="actor-name">'+icon('auto')+'<strong>'+esc(a.name)+'</strong></span><span class="cell-meta">'+avatar(a.agent)+esc(a.agent)+'</span><span class="cell-meta">'+esc(a.time)+' daily</span><span class="availability"><i></i>'+(a.enabled?'Enabled':'Paused')+'</span></button>').join('')+(db.autopilots.length?'':empty('No autopilots yet.'))+'</div>';
  }
  function autoEditor(id){
    if(!db.agents.length)return empty('Add an agent to own this runbook.')+tool('Configure agent','newAgent');
    const a=db.autopilots.find(x=>x.id===id);
    return form('autoEditor',field('Name',input('name',a?.name))+field('Runbook','<textarea required name="prompt">'+esc(a?.prompt||'')+'</textarea>')+
      field('Assignee',select('agent',strings(agentNames()),a?.agent))+field('Project',select('project',{'':'No project',...strings(db.projects)},a?.project))+
      field('Output mode',select('mode',{issue:'Create issue',run:'Run only'},a?.mode))+
      field('Acceptance criteria · one per line','<textarea name="checks" rows="3">'+esc((a?.checks?.length?a.checks:['Provide the requested summary with sources and open questions.']).join('\n'))+'</textarea>')+
      field('Daily at · device time','<input type="time" required name="time" value="'+esc(a?.time||'09:00')+'">')+
      field('Schedule',select('enabled',{off:'Disabled',on:'Enabled while this workspace is open'},a?.enabled?'on':'off'))+'<p class="empty">Schedules are checked only while this workspace is selected and this page stays open. Switching workspace or closing the page pauses checks; missed triggers are not replayed.</p>','Save autopilot',id);
  }
  function autopilotPage(id){
    const a=db.autopilots.find(x=>x.id===id);if(!a)return empty('Autopilot not found.');
    return box(esc(a.name),'<p>'+esc(a.prompt)+'</p>'+propertyList({Agent:a.agent,Project:a.project||'No project',Output:a.mode==='run'?'Run only':'Create issue',Trigger:'Daily at '+a.time+' · '+(a.enabled?'Enabled':'Disabled')})+
      '<h4>Acceptance criteria</h4><ul>'+(a.checks?.length?a.checks:['Provide the requested summary with sources and open questions.']).map(c=>'<li>'+esc(c)+'</li>').join('')+'</ul><p class="empty">Scheduled checks pause when you leave this workspace or close this page. Missed triggers are not replayed.</p>'+actionList([btn('Run now','triggerAuto',id,'primary'),tool('Edit','autoEditor',id)]))+
      box('Run history',a.history.map(e=>'<div class="entry"><strong>'+esc(e.status)+'</strong><small> · '+esc(e.source)+' · '+date(e.at)+'</small><p>'+esc(e.note)+'</p>'+actionList([e.task?tool(esc(e.task),'issue',e.task):'',e.run?tool(esc(e.run),'run',e.run):''])+'</div>').join('')||empty('No deliveries yet.'));
  }
  function savedViews(){
    return box('Saved views',db.views.map(v=>btn(esc(v.name)+' <small>'+esc(states[v.status]||'All statuses')+'</small>','applyView',v.id,'thread-row')).join('')||empty('Save a filtered issue list to reuse it.'));
  }
  function projects(){return box('Project directory',db.projects.map(p=>`<button class="row" data-act="surface" data-id="project|${esc(p)}"><span class="tile">${icon('projects')}</span><span class="grow"><strong>${esc(p)}</strong><small>${db.tasks.filter(t=>t.project===p).length} issues</small></span>${icon('chevron')}</button>`).join(''),tool('＋ New project','newProject'));}
  function starterField(agent){
    return field('Conversation starters · one per line','<textarea name="starters" rows="2">'+esc((agent?.starters||[]).join('\n'))+'</textarea>');
  }
  const starterLines=text=>text.split('\n').map(x=>x.trim()).filter(Boolean);
  function runtimesPage(){
    return box('Runtimes',db.runtimes.map(r=>'<div class="row"><span class="grow"><strong>'+esc(r.name)+'</strong><small>'+esc(r.platform)+' · '+esc(r.directory||'No working directory')+'</small></span><span class="status">Offline</span>'+tool('Configure','runtimeEditor',r.id)+'</div>').join('')||empty('Register a runtime to bind agents to a computer.'),tool('Register runtime','runtimeEditor'));
  }
  function runtimeEditor(id){
    const r=db.runtimes.find(r=>r.id===id);
    return form('runtimeEditor',field('Device name',input('name',r?.name))+field('Platform',select('platform',strings(['macOS','Linux','Windows']),r?.platform))+
      field('Working directory',input('directory',r?.directory||'',false)),'Save runtime',id);
  }
  function runtimeFields(a){
    return field('Runtime',select('runtimeId',{'':'Not connected',...Object.fromEntries(db.runtimes.map(r=>[r.id,r.name+' · Offline']))},a?.runtimeId||''))+
      field('Concurrent runs','<input name="concurrency" type="number" min="1" max="16" value="'+(a?.concurrency||1)+'">');
  }
  function agentsView(){return '<div class="agent-table"><div class="table-head"><span>Name</span><span>Runtime</span><span>Skills</span><span>Status</span></div>'+db.agents.map(a=>`<button class="agent-row" data-act="surface" data-id="agent|${esc(a.name)}"><span class="actor-name" title="${esc(a.role)}">${avatar(a.name)}<strong>${esc(a.name)}</strong></span><span class="cell-meta">${icon('runtimes')}${esc(a.runtime)}</span><span>${a.skills.length} skills</span><span class="availability"><i></i>Offline</span></button>`).join('')+'</div>';}
  let directoryTab='all', sortSkills='rank';
  const skillAgents=id=>db.agents.filter(a=>a.skills.includes(id));
  const skillRuns=id=>db.runs.filter(r=>r.skill===id).length;
  const installCommand=s=>s.repo?'npx skills add https://github.com/'+s.repo+' --skill '+s.id:'';
  function skillsView(){
    const items=db.skills.filter(s=>(directoryTab!=='saved'||db.bookmarks.includes(s.id))&&
      (directoryTab!=='attached'||skillAgents(s.id).length)&&(!skillStage||stages[s.stage]===skillStage)&&
      [s.id,s.name,s.author,s.repo,s.description].join(' ').toLowerCase().includes(skillFilter.trim().toLowerCase()));
    items.sort((a,b)=>(sortSkills==='rank'?(a.rank??Infinity)-(b.rank??Infinity):sortSkills==='usage'?skillRuns(b.id)-skillRuns(a.id):0)||a.name.localeCompare(b.name));
    return `<div class="directory"><div class="directory-head"><div class="directory-tabs">${[['all','Directory'],['attached','On agents'],['saved','Saved']].map(([key,label])=>btn(label,'skillTab',key,key===directoryTab?'chosen':'')).join('')}</div>${tool('＋ Add skill','suggest')}</div>
      <div class="toolbar"><input data-filter="skill" aria-label="Search skills" placeholder="Search skills, publishers or repositories…" value="${esc(skillFilter)}">
      <select aria-label="Skill stage" data-stage-filter>${options({'':'All stages',...strings(stages)},skillStage)}</select>
      <select aria-label="Sort skills" data-sort-skills>${options({rank:'Skills.sh ranking',usage:'Most used in '+workspace().name,name:'Name A–Z'},sortSkills)}</select></div>
      <div class="skill-head"><span>Global rank</span><span>Skill / Repository</span><span>Stage</span><span>Local runs</span></div>
      ${items.map(s=>`<button class="skill-line" data-act="surface" data-id="skill|${esc(s.id)}"><code>${s.rank?'#'+s.rank:'—'}</code><span><strong>${esc(s.name)}</strong><small>${esc(s.repo||s.author)}</small></span><span>${esc(stages[s.stage])}</span><b>${skillRuns(s.id)}</b></button>`).join('')||empty('No skills match these filters.')}
      <footer><span>${items.length} skills · Skills.sh ranks as of Nov 18, 2026</span><a href="https://skills.sh" target="_blank" rel="noopener noreferrer">Explore global rankings ↗</a></footer></div>`;
  }
  function skill(id){
    const s=db.skills.find(x=>x.id===id);
    if(!s)return empty('Skill unavailable.');
    const assigned=skillAgents(id),command=installCommand(s);
    const related=db.skills.filter(other=>other.id!==id&&(other.stage===s.stage||other.repo===s.repo)).slice(0,3);
    return (chat?'<h3>'+esc(s.name)+'</h3>':'')+`<div class="detail-grid"><div>${box('Overview','<small class="mono">'+esc(s.repo||s.author)+'</small><p>'+esc(s.description)+'</p>'+
      (command?'<h4>Install with the CLI</h4><div class="command"><code>'+esc(command)+'</code>'+btn('Copy','copyCommand',id)+'</div>':'')+
      actionList([btn(db.bookmarks.includes(id)?'Unsave skill':'Save skill','bookmark',id),btn('Share skill','share',id),'<a class="btn" href="'+esc(s.source)+'" target="_blank" rel="noopener noreferrer">View source ↗</a>']))}
      ${box('Related skills',skillList(related))}</div><div>${box('Workspace usage','<dl class="properties"><dt>Stage</dt><dd>'+stages[s.stage]+'</dd><dt>Workspace runs</dt><dd>'+skillRuns(id)+'</dd></dl><h4>Attached agents</h4>'+
      assigned.map(a=>'<div class="binding">'+tool(esc(a.name),'agent',a.name)+btn('Remove','detach',JSON.stringify([id,a.name]))+'</div>').join('')+
      (assigned.length===0?empty('No agents attached.'):'')+
      (assigned.length<db.agents.length?form('attach',field('Agent',select('agent',strings(db.agents.filter(a=>!a.skills.includes(id)).map(a=>a.name)))),'Attach skill',id):''))}</div></div>`;
  }
  function reportList(){return box('Saved snapshots',db.reports.map(r=>`<button class="row" data-act="surface" data-id="document|${r.id}">${icon('reports')}<span class="grow"><small>${r.id} · ${date(r.at)}</small><strong>${esc(r.title)}</strong></span>${icon('chevron')}</button>`).join('')||empty('Generate a report to save its evidence here.'),tool('Create summary','summary'));}
  function notes(){return form('note',field('Reviewer',input('author','',false))+field('Review feedback','<textarea name="text" required rows="3"></textarea>'),'Save feedback')+db.notes.slice().reverse().map(n=>`<div class="note"><small>${esc(n.author||'Reviewer')} / ${esc(n.page)}</small><p>${esc(n.text)}</p></div>`).join('')+btn('Export notes','exportNotes');}
  function doc(id){const r=db.reports.find(r=>r.id===id);return r?`<small>${r.id} · ${date(r.at)} · ${esc(workspace().name)} snapshot</small><h3>${esc(r.title)}</h3><pre>${esc(r.body)}</pre>${btn('Export Markdown','exportDoc',id)}`:empty('Report unavailable.');}
  let inboxTab='active';
  function notificationActivity(task){
    const entries=(task?.activity||[]).flatMap(e=>[e,...(e.replies||[])]);
    const latest=entries.reduce((latest,e)=>e.at>=latest.at?e:latest,{at:0,text:'Assigned to you'});
    return {at:latest.at,text:latest.text,token:JSON.stringify(entries.map(e=>[e.id||'',e.at,e.text]))};
  }
  function notificationRead(state,activity){
    return state.readToken!==undefined?state.readToken===activity.token:state.readAt>=activity.at;
  }
  function inboxView(){
    const now=Date.now();
    const items=db.tasks.filter(t=>t.subscribed||t.owner==='Patrick').map(t=>{
      const state=db.inbox[t.id]||{},activity=notificationActivity(t);
      const archived=state.archivedToken!==undefined?state.archivedToken===activity.token:state.archivedAt>=activity.at,snoozed=state.until>now;
      return {t,state,activity,visible:inboxTab==='archived'?archived:inboxTab==='snoozed'?snoozed:!archived&&!snoozed};
    }).filter(x=>x.visible).sort((a,b)=>b.activity.at-a.activity.at);
    return '<div class="toolbar">'+['active','snoozed','archived'].map(key=>btn(key[0].toUpperCase()+key.slice(1),'inboxTab',key,key===inboxTab?'primary':'')).join('')+'</div>'+
      box('Inbox',items.map(({t,state,activity})=>'<article class="notification">'+tool(esc(t.title),'issue',t.id,'notification-title')+
        '<small>'+esc(t.id)+' · '+esc(states[t.status])+(notificationRead(state,activity)?'':' · Unread')+'</small><p>'+esc(activity.text)+'</p>'+
        actionList([btn(notificationRead(state,activity)?'Mark unread':'Mark read','inboxRead',t.id),btn(inboxTab==='archived'?'Restore':'Archive','inboxArchive',t.id),btn(inboxTab==='snoozed'?'Unsnooze':'Snooze 1 hour','inboxSnooze',t.id)])+'</article>').join('')||empty('You are all caught up.'));
  }
  function quickActionsView(taskId){
    return box('Quick actions',db.quickActions.map(a=>btn(esc(a.name),'runQuick',taskId+'|'+a.id,'thread-row')).join('')||empty('Save a frequent request.'),tool('Add','quickEditor',taskId));
  }
  function quickEditor(taskId){
    return form('quickEditor',field('Name',input('name'))+field('Runs as',select('agent',{'':'No target',...strings([...agentNames(),...db.squads.map(s=>s.name)])}))+
      field('Request','<textarea name="prompt" required rows="3"></textarea>'),'Save quick action',taskId);
  }
  function quickSuggestions(el){
    el.parentElement.querySelector('.comment-suggestions')?.remove();
    if(!['comment','threadReply'].includes(el.form?.dataset.form))return;
    const query=el.value.match(/^\/([^\n]*)$/)?.[1];
    if(query===undefined)return;
    const items=db.quickActions.filter(a=>!a.archived&&a.name.toLowerCase().includes(query.toLowerCase()));
    const menu=document.createElement('div');menu.className='comment-suggestions';
    menu.setAttribute('aria-label','Quick actions');
    menu.innerHTML=items.length?items.map(a=>btn(esc(a.name),'draftQuick',a.id,'thread-row')).join(''):'<small>No matching quick actions.</small>';
    el.after(menu);
  }
  function wakeupEditor(taskId){
    return form('wakeupEditor',field('When',select('condition',{reply:'Someone replies',children:'All sub-issues finish',time:'At a specific time'}))+
      field('Date and time','<input type="datetime-local" name="at">')+field('Wake',select('agent',strings(agentNames()),WorkpalStudio.handlingAgent(db.tasks.find(t=>t.id===taskId).owner)?.name))+
      field('Instructions','<textarea name="instructions" required rows="2"></textarea>'),'Create wakeup',taskId);
  }
  function wakeupList(t){
    return box('Wakeups',(db.wakeups.filter(w=>w.task===t.id).map(w=>'<div class="entry"><strong>'+esc({reply:'Someone replies',children:'All sub-issues finish',time:'At '+date(w.at)}[w.condition])+'</strong><p>'+esc(w.agent)+' · '+esc(w.state)+'</p>'+
      (w.state==='Waiting'?btn('Cancel','cancelWakeup',w.id):w.run?tool(esc(w.run),'run',w.run):'')+'</div>').join('')||empty('No wakeups.')),tool('Add','wakeupEditor',t.id));
  }
  function checkWakeups(){
    let changed=false;
    for(const w of db.wakeups.filter(w=>w.state==='Waiting')){
      const t=db.tasks.find(t=>t.id===w.task);if(!t)continue;
      const children=db.tasks.filter(c=>c.parent===t.id);
      const ready=w.condition==='time'?Date.now()>=w.at:w.condition==='children'?children.length>0&&children.every(c=>c.status==='done'):
        t.activity.some(e=>(e.kind==='comment'&&e.at>w.created)||(e.replies||[]).some(r=>r.at>w.created));
      if(!ready)continue;
      const agent=db.agents.find(a=>a.name===w.agent);if(!agent){w.state='Agent unavailable';changed=true;continue;}
      let r=db.runs.find(r=>r.task===t.id&&r.agent===w.agent&&['queued','running'].includes(r.status));
      if(!r){r={id:next('RUN',db.runs),task:t.id,agent:w.agent,kind:'reply',stage:t.stage||0,status:'queued',skill:agent.skills[0]||'',artifacts:[],events:[]};db.runs.unshift(r);}
      r.events.push({type:'wakeup.triggered',text:w.instructions,at:Date.now()});
      w.state='Triggered';w.run=r.id;log(t,'Wakeup triggered · '+r.id);changed=true;
    }
    if(changed)write();
  }
  const pages={runtimes:runtimesPage,workflows:workflowsPage,auto:autopilots,squads,views:savedViews,chatroom:chatPage,overview,tasks,projects,workflow:()=>box('Run history',runList(db.runs),tool('＋ Launch workflow','launch','','primary')),stats:()=>WorkpalAnalytics.page(),skills:skillsView,agents:agentsView,inbox:inboxView,mine:()=>box('Assigned to Patrick',issueList(db.tasks.filter(t=>t.owner==='Patrick'))),reports:reportList,settings:()=>appearance()+box('Workspace settings','<dl class="properties"><dt>Workspace</dt><dd>'+esc(workspace().name)+'</dd><dt>Owner</dt><dd>Patrick</dd><dt>Language</dt><dd>English</dd><dt>Storage</dt><dd>This browser</dd></dl>'+actionList([tool('Workflows','workflows'),tool('Workspace notes','notes')]))};
  // A surface descriptor selects a trusted renderer. Tools never supply executable HTML.
  const labels={...routes,avatarEditor:'Change avatar',statusIssue:'New issue',issueProperty:'Issue property',runtimeEditor:'Runtime settings',quickEditor:'New quick action',wakeupEditor:'Create wakeup',workflowEditor:'Configure workflow',conversationSettings:'Conversation settings',assignIssue:'Assign work',chatHelp:'Choose an action',chatHistory:'Chat history',threadReply:'Reply to comment',agentConfig:'Agent settings',projectConfig:'Project settings',saveView:'Save issue view',squad:'Squad',squadEditor:'Squad settings',autopilot:'Autopilot',autoEditor:'Autopilot settings',recipients:'New chat',workspaces:'Switch workspace',newWorkspace:'Create workspace',issue:'Issue',move:'Move issue',editIssue:'Edit issue',projectIssue:'Create project issue',childIssue:'Create sub-issue',launch:'Launch a workflow',run:'Run inspector',project:'Project issues',agent:'Agent profile',skill:'Skill detail',notes:'Review notes',document:'Report snapshot',summary:'Generate summary',execution:'Execution report',newAgent:'Configure agent',newProject:'Create project',suggest:'Recommend a skill',directory:'Workspace actions',panel:'Live data panel',search:'Search workspace',reviews:'Review queue'};

  function catalog(){return '<div class="catalog">'+Object.entries({...routes,workspaces:'Switch workspace',newWorkspace:'Create workspace',issue:'Create an issue',launch:'Launch a workflow',summary:'Workspace summary',execution:'Execution report',newAgent:'Configure agent',newProject:'Create project',suggest:'Recommend a skill',notes:'Review feedback',panel:'Build a live panel',search:'Search'}).map(([type,label])=>tool(label,type)).join('')+'</div>';}
  function surface(type,arg='',standalone=false){
    if(type==='stats')return (teams[arg] ? '<h3>'+esc(teams[arg])+'</h3>' : '')+stats(arg);
    if(type==='chatroom')return conversationList()+btn('New chat','chooseAgent');
    if(type==='overview'&&(chat||route().page==='chatroom'))return box('Workspace overview',`<p><b>${db.projects.length}</b> projects · <b>${db.tasks.length}</b> issues · <b>${db.runs.length}</b> runs</p>`+actionList([tool('Review queue','reviews'),tool('Team workload','stats'),tool('Runs','workflow')]));
    if(Object.hasOwn(pages,type))return pages[type]();
    switch(type){
      case 'chatHistory':return conversationList()+'<a class="btn" href="#'+scoped('chatroom')+'">All chats</a>';
      case 'conversationSettings':{
        const c=currentConversation();
        return form('conversationSettings',field('Title',input('title',c.title))+field('Project context',select('project',{'':'No project context',...strings(db.projects)},c.project)),'Save conversation')+
          actionList([btn(c.pinned?'Unpin':'Pin','pinChat'),btn(c.archived?'Unarchive':'Archive','archiveChat')]);
      }
      case 'recipients':return db.agents.map(a=>btn(esc(a.name),'startThread',a.name,'thread-row')).join('')||empty('Add an agent to start a conversation.')+tool('Configure agent','newAgent');
      case 'workspaces':return WorkpalStudio.listWorkspaces().map(w=>
        '<button type="button" class="row space-choice" data-act="switchSpace" data-id="'+esc(w.id)+'"><span class="tile">'+esc(Array.from(w.name)[0])+'</span><strong class="grow">'+esc(w.name)+'</strong>'+(w.id===workspace().id?'<small>Current</small>':'')+'</button>'
      ).join('')+tool('＋ Create workspace','newWorkspace','','primary');
      case 'newWorkspace':return form('newWorkspace',field('Workspace name','<input name="name" value="'+esc(arg)+'" maxlength="60" required autocomplete="off">'),'Create workspace');
      case 'directory':return catalog();
      case 'chatHelp':return '<p class="preserve">'+esc(arg)+'</p><p>Workspace actions use explicit commands and forms. Reports contain saved workspace records and decision trails.</p>'+actionList([tool('Organize as an issue','issue','draft:'+arg),tool('Choose workspace action','directory')]);
      case 'panel':return generatedPanel(arg);
      case 'reviews':return issueList(db.tasks.filter(t=>t.status==='review'));
      case 'issue':return arg.startsWith('draft:')?issueEditor('',arg.slice(6)):arg?issueDetail(arg,standalone):issueEditor();
      case 'issueProperty':{
        const [id,key]=arg.split('|'),t=db.tasks.find(t=>t.id===id);
        const fields={status:['Status',select('status',states,t.status)],owner:['Assignee',select('owner',ownerOptions(),t.owner)],priority:['Priority',select('priority',strings(['Low','Normal','High','Urgent']),t.priority)],due:['Due date','<input type="date" name="due" value="'+esc(t.due||'')+'">']};
        return form('issueProperty',field(...fields[key])+(['owner','status'].includes(key)?'<label class="assign-option dispatch-option"><input type="checkbox" name="startAgent" checked> Queue the assigned agent or workflow handler</label>':'')+(key==='status'?'<label class="manual-completion" hidden>Manual completion reason<textarea name="manualReason" placeholder="Explain why this issue is complete without approving a delivery."></textarea></label>':''),'Save',id);
      }
      case 'move':{const [id,status]=arg.split('|');return issueEditor(id,'','',null,status);}
      case 'editIssue':return issueEditor(arg);
      case 'childIssue':{const parent=db.tasks.find(t=>t.id===arg);return parent?issueEditor('','',parent.project,parent):empty('Issue not found.');}
      case 'assignIssue':return assignWorkEditor(arg);
      case 'avatarEditor':return avatarEditor(arg);
      case 'projectIssue':return issueEditor('','',arg);
      case 'statusIssue':return issueEditor('','','',undefined,arg);
      case 'launch':return launch(arg);
      case 'run':return run(arg);
      case 'project':return projectPage(arg);
      case 'runtimeEditor':return runtimeEditor(arg);
      case 'workflowEditor':return workflowEditor(arg);
      case 'projectConfig':return projectEditor(arg);
      case 'squad':return squadPage(arg);
      case 'squadEditor':return squadEditor(arg);
      case 'autopilot':return autopilotPage(arg);
      case 'autoEditor':return autoEditor(arg);
      case 'threadReply':return form('threadReply',field('Reply','<textarea name="text" required></textarea>'),'Post reply',arg);
      case 'quickEditor':return quickEditor(arg);
      case 'wakeupEditor':return wakeupEditor(arg);
      case 'saveView':return form('saveView',field('View name',input('name')),'Save view');
      case 'newProject':return form('newProject',field('Project name',input('name')),'Create project');
      case 'newAgent':return form('newAgent',field('Name',input('name'))+field('Responsibilities',input('role'))+field('Instructions','<textarea name="instructions" rows="3"></textarea>')+starterField()+field('Harness',select('runtime',strings(['Codex','Claude Code','Local runner'])))+runtimeFields()+field('Skill',select('skill',Object.fromEntries(db.skills.map(s=>[s.id,s.name])))),'Save agent');
      case 'agent':{
        const a=db.agents.find(x=>x.name===arg);if(!a)return empty('Agent unavailable.');
        const assigned=db.tasks.filter(t=>t.owner===a.name),runs=db.runs.filter(r=>r.agent===a.name);
        return '<div class="detail-grid"><div>'+box('Instructions','<p class="preserve">'+esc(a.instructions||a.role)+'</p>',tool('Edit','agentConfig',a.name))+
          box('Recent work',issueList(assigned))+box('Execution log',runList(runs))+'</div><div>'+
          box('Properties',propertyList({Owner:'Patrick',Harness:a.runtime,Runtime:db.runtimes.find(r=>r.id===a.runtimeId)?.name||'Not connected',Model:a.model||'Default',Access:'Workspace'})+actionList([tool('Assign work','assignIssue',a.name),btn('New chat','startThread',a.name)]))+
          box('Skills',skillList(db.skills.filter(s=>a.skills.includes(s.id))),tool('Manage skills','skills'))+'</div></div>';
      }
      case 'agentConfig':{
        const a=db.agents.find(x=>x.name===arg);
        return form('agentConfig',tool(avatar(a.name)+' Change avatar','avatarEditor',JSON.stringify({name:a.name}))+field('Instructions','<textarea name="instructions" rows="5" required>'+esc(a.instructions||a.role)+'</textarea>')+field('Harness',select('runtime',strings(['Codex','Claude Code','Local runner']),a.runtime))+field('Model',input('model',a.model||'Default'))+runtimeFields(a)+starterField(a),'Save settings',arg);
      }
      case 'skill':return skill(arg);
      case 'suggest':return form('suggest',field('Skill name',input('name'))+field('Source URL','<input type="url" name="url" required>')+field('Recommended use',input('reason'))+field('Stage',select('stage',Object.fromEntries(stages.map((stage,i)=>[i,stage])))),'Add to directory');
      case 'execution':return db.runs.length?form('execution',field('Run',select('run',Object.fromEntries(db.runs.map(r=>[r.id,r.id+' · '+r.task])),arg)),'Generate execution report'):launch('');
      case 'summary':return form('summary',field('Report scope',select('team',{'':'Entire workspace',...teams},arg)),'Generate summary');
      case 'document':return doc(arg);
      case 'notes':return notes();
      case 'search':return form('search',field('Search pages, issues and skills',input('q',arg)),'Search')+(arg?searchResults(arg):'');
      default:return catalog();
    }
  }
  function searchResults(q){const term=q.toLowerCase();const matches=[...Object.entries(routes).map(([k,v])=>[v,k,'']),...db.tasks.map(t=>[t.id+' '+t.title,'issue',t.id]),...db.skills.map(s=>[s.name,'skill',s.id]),...db.agents.map(a=>[a.name,'agent',a.name])].filter(([text])=>text.toLowerCase().includes(term));return matches.length ? actionList(matches.map(([label,type,id])=>tool(esc(label),type,id))) : empty('No results.');}
  function descriptor(type,arg='',text=''){return {id:crypto.randomUUID(),role:'assistant',text,surface:{type,arg},event:'TOOL_CALL_RESULT',at:Date.now()};}
  function parse(prompt){
    const text=prompt.trim(),p=text.toLowerCase().replace(/^please\s+/,'');
    const unsupported=()=>descriptor('chatHelp',text,'Choose an action to continue. Your message is saved in this conversation.');
    // Parse only the command prefix. Titles, quoted material and negations are data.
    if(/^(?:do not|don't|never|avoid|explain|what|why|how|can you explain|不要|别|解释)\b|^(?:不要|别|解释)/i.test(p))return unsupported();
    const createIssue=text.match(/^(?:please\s+)?(?:create|new|add)\s+(?:a |an )?(?:issue|task)(?:\s+(?:titled|called|named))?(?:\s*[:：]\s*|\s+)?(.*)$/i)||text.match(/^(?:创建|新建)任务[：:\s]*(.*)$/);
    if(createIssue){const title=createIssue[1]?.replace(/^['"]|['"]$/g,'')||'';return descriptor('issue',title?'draft:'+title:'');}
    if(/^(?:create|new|add) (?:a |an )?workspace\b(?!\s+(?:summary|report|panel|dashboard|issue)\b)|^(?:新建|创建)工作空间/.test(p)){
      const name=text.match(/workspace\s+(?:(?:named|called)\s+)?(.+)$/i)?.[1]||'';
      return descriptor('newWorkspace',name);
    }
    if(/^(?:switch|change) workspace\b|^切换工作空间/.test(p))return descriptor('workspaces');
    const issue=db.tasks.find(t=>p.includes(t.id.toLowerCase()));
    const run=db.runs.find(r=>p.includes(r.id.toLowerCase()))||db.runs.find(r=>r.task===issue?.id);
    const team=Object.entries(teams).find(([id,name])=>p.includes(id)||p.includes(name.toLowerCase())||p.includes(({quality:'质量组',engineering:'研发组',product:'产品组',unassigned:'未分配'})[id]))?.[0]||'';
    const latest=(currentConversation()?.messages||[]).slice().reverse().find(m=>m.surface?.type==='run');
    const rid=run?.id||latest?.surface.arg||db.runs.find(r=>r.task)?.id||'';
    const previousIssue=(currentConversation()?.messages||[]).slice().reverse().find(m=>m.surface?.type==='issue'&&db.tasks.some(t=>t.id===m.surface.arg));
    if(issue&&/^(?:assign|edit|update|指派|编辑)\b/.test(p))return descriptor('editIssue',issue.id);
    if(issue&&/^(?:comment|reply|评论)\b/.test(p))return descriptor('issue',issue.id);
    if(/^(?:launch|start)\b.*(?:workflow|run)|^run\s+workflow|^(?:启动|跑流程)/.test(p)){
      const selected=issue?.id||previousIssue?.surface.arg||'';
      return descriptor('launch',selected+(/report|报告/.test(p)?'~report':''),'Review the workflow configuration.');
    }
    if(/^(?:(?:generate|create|show|open)\s+.*(?:report|summary)|summarize\b|execution report$|workspace summary$|生成.*(?:报告|总结)|总结)/.test(p)){
      const execution=/execution|run|workflow|执行|流程/.test(p)||!!run;
      if(execution&&!rid)return descriptor('launch','','Start a workflow to capture execution evidence.');
      return descriptor(execution?'execution':'summary',execution?rid:team,'Review the report scope, then generate a snapshot.');
    }
    if(/^(?:approve|reject|handoff|advance|continue|退回|批准|推进)\b/.test(p))return rid?descriptor('run',rid,'Inspect the delivery and record your decision.'):descriptor('reviews');
    if(/^(?:panel|chart|plot)\b|^(?:create|generate|show)\b.*(?:panel|chart)|^按(?:项目|状态|负责人)|^生成.*面板/.test(p)){
      const group=/project|项目/.test(p)?'project':/assign|owner|负责人/.test(p)?'owner':'status';
      return descriptor('panel',team+':'+group);
    }
    if(/^(?:(?:quality|engineering|product|unassigned) )?(?:team )?(?:dashboard|insights?|stats|workload)$|^(?:show|open)\s+.*(?:dashboard|insights?|stats|workload)$|^(?:统计|面板)$/.test(p))return descriptor('stats',team);
    if(/^(?:new|create|add|configure|recommend)\b|^(?:创建|新建|推荐)/.test(p)){
      if(/^(?:(?:new|create|add|configure)\s+(?:a |an )?project|(?:创建|新建)项目)\b/.test(p))return descriptor('newProject');
      if(/^(?:(?:new|create|add|configure)\s+(?:a |an )?agent|(?:创建|新建)伙伴)\b/.test(p))return descriptor('newAgent');
      if(/^(?:recommend|add|new)\s+(?:a )?skill\b|^推荐/.test(p))return descriptor('suggest');
      return unsupported();
    }
    if(issue&&(/^(?:open|show|view)\b/.test(p)||p===issue.id.toLowerCase()))return /run|history|evidence|轨迹/.test(p)&&run?descriptor('run',run.id):descriptor('issue',issue.id);
    if(run&&(/^(?:open|show|view)\b/.test(p)||p===run.id.toLowerCase()))return descriptor('run',run.id);
    const lookup=p.replace(/^(?:open|show|view)\s+/,'');
    const project=db.projects.find(name=>lookup==='project '+name.toLowerCase()||lookup===name.toLowerCase()+' project');
    if(project)return descriptor('project',project);
    const agent=db.agents.find(a=>lookup===a.name.toLowerCase());if(agent)return descriptor('agent',agent.name);
    const skill=db.skills.find(s=>lookup===s.name.toLowerCase()||lookup===s.id);if(skill)return descriptor('skill',skill.id);
    if(/^(?:show )?(?:review queue|issues awaiting review|awaiting review|待评审)$/.test(p))return descriptor('reviews');
    if(/^(?:feedback|notes?|意见)$/.test(lookup))return descriptor('notes');
    if(/^(?:search|find|搜索)\s+/.test(p))return descriptor('search',text.replace(/^(?:please\s+)?(?:search|find|搜索)\s*/i,''));
    const page=Object.entries(routes).find(([k,v])=>lookup===k||lookup===v.toLowerCase());
    if(page)return descriptor(page[0]);
    if(/^(?:workflow|流程)$/.test(p))return descriptor('workflow');
    if(/^(?:issues?|tasks?|任务)$/.test(p))return descriptor('tasks');
    return unsupported();
  }
  // Local AG-UI-style event transport. The UI catalog binds only to known tools.
  // Resource URIs stay local; users can inspect the payload behind a generated card.
  function emitTurn(message) {
    const id=crypto.randomUUID();
    const toolId=crypto.randomUUID();
    const {type,arg}=message.surface;
    const resource={uri:'ui://workpal/'+type,mimeType:'application/vnd.workpal.surface+json',
      contents:{surfaceId:message.id,root:'result',components:[{id:'result',component:type,arguments:{selection:arg}}]}};
    const events=[
      {type:'RUN_STARTED',runId:id,threadId:currentConversation(true).id},
      {type:'TOOL_CALL_START',toolCallId:toolId,toolCallName:type},
      {type:'TOOL_CALL_ARGS',toolCallId:toolId,delta:JSON.stringify({selection:arg})},
      {type:'TOOL_CALL_END',toolCallId:toolId},
      {type:'TOOL_CALL_RESULT',toolCallId:toolId,messageId:message.id,content:JSON.stringify(resource)},
      {type:'RUN_FINISHED',runId:id,threadId:currentConversation(true).id},
    ];
    for(const event of events) {
      window.dispatchEvent(new CustomEvent('workpal:agent-event',{detail:event}));
      if(event.type==='TOOL_CALL_RESULT'){
        const payload=JSON.parse(event.content);
        const component=payload.contents.components.find(c=>c.id===payload.contents.root);
        if(!Object.hasOwn(labels,component.component))throw Error('Unknown surface.');
        message.surface={type:component.component,arg:component.arguments.selection};
        message.resource=payload;
      }
    }
    message.trace=events.map(event=>({type:event.type,at:Date.now()}));
    const c=currentConversation(true);c.messages.push(message);if(c.title==='New chat')c.title=labels[type]||'Workspace action';
  }
  function traceView(message) {
    if(!message.trace)return '';
    return `<details class="event-details"><summary>Tool events · ${message.trace.length}</summary>
      <code>${esc(message.resource.uri)}</code>
      <ol>${message.trace.map(ev=>'<li>'+esc(ev.type)+'</li>').join('')}</ol>
      <details><summary>Surface schema</summary><pre>${esc(JSON.stringify(message.resource.contents,null,2))}</pre></details></details>`;
  }
  let draftAgent='',draftText='',archivedChats=false;
  function prepareConversations(){
    if(db.conversations)return;
    db.conversations=[];
    if(db.messages?.length){
      const first=db.messages.find(m=>m.role==='user');
      const c={id:crypto.randomUUID(),agent:db.agents[0]?.name||'',title:first?.text?.slice(0,64)||'Workspace actions',messages:db.messages};
      db.conversations.push(c);db.currentChat=c.id;
    }
    db.messages=[];
    write();
  }
  function currentConversation(create=false){
    let c=db.conversations.find(item=>item.id===db.currentChat);
    if(!c&&create){
      c={id:crypto.randomUUID(),agent:draftAgent||db.agents[0]?.name||'',project:db.chatDraft?.project||'',title:'New chat',messages:[],draft:draftText};
      db.chatDraft=null;
      db.conversations.unshift(c);db.currentChat=c.id;
    }
    return c;
  }
  function persistDraft(text){
    draftText=text;
    const c=currentConversation();if(c)c.draft=text;else db.chatDraft={...db.chatDraft,agent:draftAgent||db.agents[0]?.name||'',text};
    write();
  }
  function loadDraft(){
    const c=currentConversation();draftAgent=c?.agent||db.chatDraft?.agent||'';draftText=c?.draft||(!c?db.chatDraft?.text:'')||'';
  }
  function conversationList(){
    const chats=db.conversations.filter(c=>!!c.archived===archivedChats).slice().sort((a,b)=>Number(!!b.pinned)-Number(!!a.pinned));
    return chats.map(c=>{const last=c.messages.at(-1);return `<button class="thread-row ${c.id===db.currentChat?'selected':''}" aria-label="${esc(c.title+' · '+(c.agent||'Workpal'))}" data-act="openThread" data-id="${esc(c.id)}">${avatar(c.agent||'Workpal')}<span class="thread-copy"><strong>${c.pinned?'☆ ':''}${esc(c.title)}</strong><small>${esc(last?.text||c.agent||'New conversation')}</small></span>${last?.at?'<time>'+new Date(last.at).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'})+'</time>':''}</button>`;}).join('')||empty('No conversations yet.');
  }
  function chatPage(){
    return `<div class="chat-page ${(currentConversation()||draftAgent)?'has-conversation':''}"><section class="thread-list"><header><div class="thread-title">${btn(icon('menu'),'menu','','mobile-only icon-only" aria-label="Workspace menu')}<h1>Chat</h1></div>${btn(icon('plus'),'chooseAgent','','icon-only" aria-label="New chat')}</header><div class="thread-scroll">${btn(archivedChats?'Show active':'Archived','archiveFilter','','quiet')}${conversationList()}</div></section><section id="chat-pane">${!currentConversation()&&!draftAgent?'<div class="chat-empty">'+icon('chatroom')+'<p>Select a conversation or start a new chat</p>'+btn('New chat','chooseAgent','','quiet')+'</div>':''}</section></div>`;
  }
  function assistant(full=false){
    const c=currentConversation(), name=c?.agent||draftAgent||db.agents[0]?.name||'';
    const messages=(c?.messages||[]).filter(m=>!m.surface||Object.hasOwn(labels,m.surface.type));
    const title=c?.title||'New chat',agent=db.agents.find(a=>a.name===name);
    const suggestions=agent?.starters?.length?agent.starters.slice(0,3):['Summarize workspace progress','Show issues awaiting review','Create an issue'];
    const starters=!messages.length&&name?'<div class="chat-welcome">'+avatar(name)+'<h2>Chat with '+esc(name)+'</h2><p>'+esc(agent?.role||'')+'</p><div class="starters">'+suggestions.map(t=>btn(esc(t),'starter',t)).join('')+'</div></div>':'';

    const agentButton=btn((name?avatar(name):'')+esc(name||'Choose agent')+icon('chevronDown'),'chooseAgent','','quiet');
    return `<aside id="assistant" class="${full?'full-chat':'float-chat'}" aria-label="Chat">
      <header>${full?btn(icon('back'),'chatBack','','mobile-only icon-only" aria-label="Back to conversations'): ''}<strong title="${esc(title)}">${esc(title)}</strong><div>${c?btn(icon('more'),'chatSettings',c.id,'icon-only" aria-label="Conversation settings'):''}${btn(icon('plus'),'chooseAgent','','icon-only" aria-label="New chat with an agent')}${full?'':btn(icon('expand'),'expandChat','','icon-only" aria-label="Open in Chat')}${btn(icon('close'),'closeChat','','icon-only" aria-label="Close chat')}</div></header>
      ${messages.length?'<div class="messages">'+messages.map((m,i)=>m.role==='user'?`<div class="user-turn"><p class="bubble">${esc(m.text)}</p>${m.queued?'<small>Queued · runtime offline</small>'+btn('Cancel','cancelChatRun',m.run,'quiet'):''}</div>`:`<section class="reply"><small>${esc(name||'Workspace')}</small>${m.text?'<p>'+esc(m.text)+'</p>':''}${m.surface?`<details class="resource" ${i===messages.length-1?'open':''}><summary>${icon('layers')}${esc(labels[m.surface.type]||'Workspace action')}</summary>${i===messages.length-1?'<div class="resource-body">'+surface(m.surface.type,m.surface.arg)+traceView(m)+'</div>':btn('Reopen card','surface',m.surface.type+'|'+m.surface.arg)}</details>`:''}</section>`).join('')+'</div>':''}
      ${starters}<div class="composer">${name?'<small class="runtime-state">'+esc(name)+' · Runtime offline</small>':''}${(c?.project||db.chatDraft?.project)?'<small class="context-label">Project · '+esc(c?.project||db.chatDraft.project)+'</small>':''}<form data-form="prompt"><textarea name="prompt" aria-label="Message" placeholder="Message ${esc(name||'workspace')}…" rows="2" required>${esc(draftText)}</textarea><div class="compose-actions">${btn(icon('plus'),'surface','directory|','icon-only" aria-label="Workspace actions')}${agentButton}<button type="submit" class="send" aria-label="Send message" ${name?'':'disabled'}>${icon('send')}</button></div></form></div></aside>`;
  }
  function paintChat(scroll=true){
    if($('#assistant'))captureDrafts($('#assistant'));
    $('#assistant')?.remove();
    const pane=$('#chat-pane');
    if(!chat&&!(pane&&(currentConversation()||draftAgent)))return;
    (pane||$('#app')).insertAdjacentHTML('beforeend',assistant(!!pane));restoreDrafts($('#assistant'));
    const m=$('#assistant .messages');
    if(scroll&&m){
      const latest=m.lastElementChild;
      if(latest?.classList.contains('reply')&&latest.querySelector('.resource[open]'))m.scrollTop+=latest.getBoundingClientRect().top-m.getBoundingClientRect().top-12;
      else m.scrollTop=m.scrollHeight;
    }
  }
  function newThread(name){
    dismiss();db.currentChat=null;draftAgent=name;draftText='';db.chatDraft={agent:name,text:'',project:''};write();
    chat=route().page!=='chatroom';render();$('#assistant textarea[name="prompt"]')?.focus();
  }
  const detailPages={autopilot:'auto',squad:'squads',issue:'tasks',project:'projects',skill:'skills',run:'workflow',agent:'agents',document:'reports'};
  function show(type,arg='',inside=chat){
    if(inside){emitTurn(descriptor(type,arg));write();paintChat();return;}
    if ((Object.hasOwn(detailPages,type)&&arg&&!arg.startsWith('draft:')&&!(type==='issue'&&!db.tasks.some(t=>t.id===arg)))||Object.hasOwn(routes,type)){
      dismiss();
      const hash=Object.hasOwn(routes,type)?type+(type==='stats'&&arg?'?team='+encodeURIComponent(arg):''):detailPages[type]+'?id='+encodeURIComponent(arg);
      if(location.hash.slice(1)===scoped(hash))render();else {location.hash=scoped(hash);enter();}
      return;
    }
    if($('#dialog').open)captureDrafts($('#dialog'));
    modalSurface={type,arg};const d=$('#dialog');focusReturn=d.open?focusReturn:document.activeElement;
    d.dataset.surface=type;d.innerHTML=`<header><h2 id="dialog-title">${esc(labels[type]||'Workspace')}</h2>${btn(icon('close'),'dismiss','','icon-only" aria-label="Close dialog')}</header><div class="modal-body">${surface(type,arg)}</div>`;
    restoreDrafts(d);if(!d.open)d.showModal();
  }
  function dismiss(){const d=$('#dialog');if(d.open){captureDrafts(d);d.close();focusReturn?.focus();}modalSurface=null;}
  const spaces=[
    {name:'Work',page:'tasks',icon:'tasks',pages:['overview','tasks','projects','inbox','mine','views','reports']},
    {name:'Team',page:'agents',icon:'squads',pages:['agents','squads','skills','workflow','workflows','runtimes','stats']},
    {name:'Chat',page:'chatroom',icon:'note',pages:['chatroom']},
    {name:'Auto',page:'auto',icon:'auto',pages:['auto']}
  ];
  function navigation(page){
    const space=spaces.find(s=>s.pages.includes(page))||spaces[0];
    const dock=spaces.map(s=>`<a class="dock-link ${space===s?'current':''}" href="#${scoped(s.page)}" title="${s.name}">${icon(s.icon)}<span>${s.name}</span></a>`).join('');
    function section(label,body){return '<section class="rail-group"><div class="rail-group-label"><small>'+label+'</small>'+icon('chevronDown')+'</div>'+body+'</section>';}
    let panel='';
    if(space.name==='Work')panel=section('Inbox',nav('inbox'))+section('Views',['tasks','mine','views'].map(nav).join('')+db.views.slice(0,3).map(v=>btn(icon('layers')+'<span>'+esc(v.name)+'</span>','applyView',v.id,'rail-item')).join(''))+
      section('Projects',nav('projects')+db.projects.slice(0,6).map(p=>tool(icon('projects')+'<span>'+esc(p)+'</span><small>'+db.tasks.filter(t=>t.project===p).length+'</small>','project',p,'rail-item')).join(''))+section('Workspace',['overview','reports'].map(nav).join(''));
    if(space.name==='Team')panel=section('Team',nav('agents')+nav('squads'))+section('Resources',nav('skills')+nav('runtimes')+nav('stats')+nav('workflow')+nav('workflows'));
    if(space.name==='Auto')panel=section('Automation',nav('auto')+db.autopilots.map(a=>tool(icon('auto')+'<span>'+esc(a.name)+'</span>','autopilot',a.id,'rail-item')).join(''));
    return `<aside class="rail"><div class="app-dock"><button class="workspace-tile" data-act="surface" data-id="workspaces|" aria-label="Switch workspace, ${esc(workspace().name)}" title="${esc(workspace().name)} · Workpal">${esc(Array.from(workspace().name)[0])}</button>
      ${btn(icon('edit'),'surface','issue|','dock-command" aria-label="New issue')}${btn(icon('search'),'surface','search|','dock-command" aria-label="Search workspace')}
      <nav aria-label="App navigation">${dock}</nav><div class="dock-bottom"><a class="dock-settings" href="#${scoped('settings')}" aria-label="Settings">${icon('settings')}</a><button class="account-avatar" data-act="surface" data-id="workspaces|" aria-label="Account and workspaces">P</button></div></div>
      <div class="space-panel"><header class="space-heading"><h2>${space.name}</h2>${btn(icon('panelLeft'),'collapseNav','','icon-only" aria-label="Collapse sidebar')}</header><div class="panel-scroll">${panel}</div></div></aside>`;
  }
  function chatLauncher(){
    return '<div class="chat-launcher" aria-label="Workspace chat">'+btn(icon('sparkles')+' Ask Workpal','chat','','ask-button')+
      btn(icon('history'),'surface','chatHistory|','history-button" aria-label="Chat history')+'</div>';
  }
  const scrollPositions=new Map();
  let renderedHash;
  function scrollRegions(){
    return [...document.querySelectorAll('main,.board,.board-cards,.issue-groups,.agent-table,.detail-reading,.detail-properties,.thread-scroll')];
  }
  function scrollKey(el){return el.classList.contains('board-cards')?'column:'+el.closest('[data-drop-state]').dataset.dropState:el.tagName==='MAIN'?'main':el.className;}
  function render(){
    captureDrafts();
    if(renderedHash)scrollPositions.set(renderedHash,new Map(scrollRegions().map(el=>[scrollKey(el),[el.scrollLeft,el.scrollTop]])));
    const {page,params}=route(),id=params.get('id');
    const type=Object.keys(detailPages).find(key=>detailPages[key]===page),detail=id&&type;
    const heading=detail?({issue:db.tasks.find(t=>t.id===id)?.title,skill:db.skills.find(s=>s.id===id)?.name})[type]||id:routes[page];
    const space=spaces.find(s=>s.pages.includes(page))?.name||'Work';
    const taskActions=page==='tasks'&&!detail;
    const createActions={agents:['newAgent','Configure agent'],squads:['squadEditor','New squad'],auto:['autoEditor','New autopilot']};
    const collectionAction=!detail&&createActions[page];
    document.title=heading+' · '+workspace().name+' · Workpal';
    $('#app').innerHTML=`<div class="shell ${mobileMenu?'menu-open':''} ${navCollapsed?'nav-collapsed':''}" data-page="${page}" data-space="${space}" data-detail="${detail?'true':'false'}" data-layout="${layout}">${navigation(page)}
    <div class="main"><header class="top">${page==='stats'?WorkpalAnalytics.header():`<div class="top-title">${btn(icon('menu'),'menu','','mobile-only icon-only" aria-label="Workspace menu')}${navCollapsed&&space!=='Chat'?btn(icon('panelLeft'),'collapseNav','','icon-only" aria-label="Expand sidebar'):''}${icon(page)}${detail?'<a href="#'+scoped(page)+'">'+routes[page]+'</a><span class="separator">/</span><span>'+esc(type==='issue'?id:heading)+'</span>':(page==='chatroom'?'<span>Chat</span>':'<h1>'+esc(heading)+'</h1>')}${taskActions?btn(icon('filter'),'filters','','icon-only" aria-label="Filter issues'):''}</div><div class="top-actions">${taskActions?issueDisplay()+tool(icon('edit'),'issue','','icon-only" aria-label="New issue'):collectionAction?tool(icon('plus'),collectionAction[0],'','icon-only" aria-label="'+collectionAction[1]):btn(icon('search'),'surface','search|','icon-only" aria-label="Search workspace')}</div>`}</header>
    <main id="main" tabindex="-1">${detail&&type!=='issue'?'<div class="heading"><div><div class="crumb">'+esc(workspace().name)+'<span>/</span>'+esc(type==='issue'?id:labels[type])+'</div><h1>'+esc(heading)+'</h1></div>'+(type==='squad'?tool(icon('plus')+' Assign work','assignIssue',id,'primary'):'')+'</div>':''}<div id="page-content">${detail?surface(type,id,true):pages[page]()}</div></main></div></div><footer class="bottom-bar"><span class="product-wordmark">Workpal</span><span class="workspace-caption">${esc(workspace().name)}</span></footer>${page==='chatroom'?'':chatLauncher()}`;
    paintChat();restoreDrafts();
    renderedHash=location.hash;
    const positions=scrollPositions.get(renderedHash);
    for(const el of scrollRegions()){
      const position=positions?.get(scrollKey(el));
      if(position){el.scrollLeft=position[0];el.scrollTop=position[1];}
    }
  }
  function download(name,body){const url=URL.createObjectURL(new Blob([body],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
  function refresh(){const prev=modalSurface;render();if(prev&&$('#dialog').open)show(prev.type,prev.arg,false);}
  function output(type,arg,text,inside){checkWakeups();write();if(inside){emitTurn(descriptor(type,arg,text));write();render();}else{dismiss();render();show(type,arg,false);}toast(text);}
  function saveIssue(data,id){
    const t=db.tasks.find(item=>item.id===id);
    return WorkpalStudio.updateIssue(t||null,{...data,checks:data.checks.split('\n').map(x=>x.trim()).filter(Boolean),tags:data.tags.split(',').map(x=>x.trim()).filter(Boolean)},
      {queueRun:data.startAgent==='on',manualReason:data.manualReason||''}).task;
  }

  function submit(f){
    const data=Object.fromEntries(new FormData(f));for(const k of Object.keys(data))data[k]=data[k].trim();
    const type=f.dataset.form, id=f.dataset.id, inside=!!f.closest('#assistant');
    if([...f.querySelectorAll('[required]')].some(c=>!c.value.trim()))throw Error('Complete the required fields.');
    if(type==='newWorkspace'){const space=WorkpalStudio.createWorkspace(data.name);openSpace(space);toast('Workspace created.');return;}
    if(type==='prompt'){
      const recipient=currentConversation()?.agent||draftAgent||db.agents[0]?.name;
      if(!db.agents.some(a=>a.name===recipient))throw Error('Choose an agent before sending.');
      const c=currentConversation(true),answer=parse(data.prompt);
      const run={id:next('RUN',db.runs),kind:'chat',conversation:c.id,task:null,agent:recipient,title:data.prompt.slice(0,80),
        status:answer?'finished':'queued',stage:0,artifacts:[],context:c.project?{...projectConfig(c.project)}:null,
        events:[{type:answer?'workspace.action':'run.queued',text:data.prompt,at:Date.now()}]};
      db.runs.unshift(run);
      if(!c.messages.length)c.title=data.prompt.slice(0,64);
      c.messages.push({role:'user',text:data.prompt,at:Date.now(),queued:!answer,run:run.id});
      if(answer)emitTurn(answer);
      draftText='';c.draft='';write();render();return;
    }
    const done=(kind,key,message)=>{write();clearFormDraft(f);return output(kind,key,message,inside);};
    if(type==='selectDelivery'){const d=WorkpalStudio.selectDelivery(id,data.reason);return done('run',d.run,'Current delivery selected.');}
    if(type==='assignWork'){
      const result=WorkpalStudio.assignWork(id,{...data,checks:data.checks.split('\n').map(x=>x.trim()).filter(Boolean),queueRun:data.queueRun==='on'});
      return done('issue',result.task.id,result.run?'Issue assigned. Leader run queued.':'Issue assigned without a run.');
    }
    if(type==='avatarEditor'){
      const emoji=data.emoji;
      if(emoji&&(!/\p{Extended_Pictographic}|\p{Regional_Indicator}|[#*0-9]\uFE0F?\u20E3/u.test(emoji)||[...new Intl.Segmenter('en',{granularity:'grapheme'}).segment(emoji)].length!==1))throw Error('Choose or paste one emoji.');
      const agent=db.agents.find(a=>a.name===data.name);
      if(agent)agent.emoji=emoji;
      else if(data.name==='Patrick'){db.memberAvatars??={};db.memberAvatars[data.name]=emoji;}
      else throw Error('Member unavailable.');
      return done(data.squad?'squad':'agent',data.squad||data.name,'Avatar saved.');
    }
    if(type==='conversationSettings'){Object.assign(currentConversation(),data);write();dismiss();render();return;}
    if(type==='issue'||type==='issueProperty'){
      let values=data;
      if(type==='issueProperty'){
        const t=db.tasks.find(t=>t.id===id);
        values={...t,checks:t.checks.join('\n'),tags:(t.tags||[]).join(', '),startAgent:'',...data};
      }
      const t=saveIssue(values,id);return done('issue',t.id,'Saved '+t.id+'.');
    }
    if(type==='threadReply'){
      const [taskId,entryId]=id.split('|'),t=db.tasks.find(t=>t.id===taskId),e=t.activity.find(e=>e.id===entryId);
      WorkpalStudio.comment(t,data.text,{replyTo:e.id});return done('issue',taskId,'Reply posted.');
    }
    if(type==='comment'){const t=db.tasks.find(t=>t.id===id);WorkpalStudio.comment(t,data.text);return done('issue',id,'Comment posted.');}
    if(type==='quickEditor'){db.quickActions.push({id:next('ACTION',db.quickActions),...data});return done('issue',id,'Quick action saved.');}
    if(type==='wakeupEditor'){
      if(data.condition==='time'&&(!data.at||new Date(data.at).getTime()<=Date.now()))throw Error('Choose a future date and time.');
      db.wakeups.push({id:next('WAKE',db.wakeups),task:id,condition:data.condition,at:data.at?new Date(data.at).getTime():null,agent:data.agent,instructions:data.instructions,created:Date.now(),state:'Waiting'});
      return done('issue',id,'Wakeup created.');
    }
    if(type==='attach'){const a=db.agents.find(a=>a.name===data.agent);if(!a.skills.includes(id))a.skills.push(id);return done('skill',id,'Attached to '+a.name+'.');}
    if(type==='deliver'){
      const sourceRun=db.runs.find(r=>r.id===id);
      const r=changeRun(sourceRun,'deliver',data.note,{artifacts:data.artifactTitle||data.artifactBody?[{title:data.artifactTitle||'Untitled artifact',body:data.artifactBody||''}]:[],evidence:(sourceRun.inputSnapshot?.task?.checks||[]).map((criterion,i)=>({criterion,evidence:data['evidence'+i]||'',status:data['evidenceStatus'+i]})),limitations:data.limitations||''});
      return done('run',id,r.kind==='reply'?'Response saved.':r.kind==='review'?'Review findings saved.':'Delivery saved.');
    }
    if(type==='launch'){
      const t=db.tasks.find(t=>t.id===data.task), agent=db.agents.find(a=>a.name===data.agent);
      if(!agent)throw Error('Choose an available agent.');
      const r=start(t,data.skill||agent.skills[0]||'',agent.name);
      if(data.followUp==='report')r.reportOnFinish=true;
      return done('run',r.id,'Opened '+r.id+'.');
    }
    if(type==='decision'){const r=decide(id,Number(data.stage),data.choice,data.note,{acknowledged:data.acknowledged==='on'});if(r.status==='finished'&&r.reportOnFinish&&r.reviewDecision==='approve'){const rec=report('execution','',r.id);return done('document',rec.id,'Decision recorded. Execution report saved.');}return done('run',r.id,'Decision recorded.');}
    if(type==='panel')return done('panel',panelConfig(data.team+':'+data.group).key,'Live panel updated.');
    if(type==='summary'||type==='execution'){const rec=report(type,data.team,data.run);return done('document',rec.id,'Report saved.');}
    if(type==='saveView'){db.views.push({id:next('VIEW',db.views),name:data.name,status:issueStatus,owner:issueOwner,query:taskFilter,layout});return done('views','','View saved.');}
    if(type==='runtimeEditor'){
      const r={id:id||next('RUNTIME',db.runtimes),...data};db.runtimes=db.runtimes.filter(item=>item.id!==r.id);db.runtimes.push(r);return done('runtimes','','Runtime settings saved.');
    }
    if(type==='workflowEditor'){
      const w={id:id||next('FLOW',db.workflows),name:data.name,steps:Object.keys(states).map(status=>({status,
        owner:data[status+'Owner'],instructions:data[status+'Instructions'],next:data[status+'Next'],rejected:data[status+'Rejected']}))};
      db.workflows=db.workflows.filter(item=>item.id!==w.id);db.workflows.push(w);return done('workflows','','Workflow saved.');
    }
    if(type==='projectConfig'){
      db.projectSettings=db.projectSettings.filter(p=>p.project!==id);
      db.projectSettings.push({project:id,...data});return done('project',id,'Project updated.');
    }
    if(type==='squadEditor'){
      const name=data.name;
      if(name!==id&&(db.squads.some(s=>s.name===name)||Object.hasOwn(ownerOptions(),name)))throw Error('Choose a unique squad name.');
      const members=[...new Set([data.leader,...new FormData(f).getAll('members')])];
      const roles=[...agentNames(),'Patrick'].map((person,i)=>({name:person,role:data['memberRole'+i]})).filter(r=>members.includes(r.name)&&r.role);
      if(id&&id!==name){
        for(const t of db.tasks)if(t.owner===id)t.owner=name;
        for(const v of db.views)if(v.owner===id)v.owner=name;
        for(const a of db.autopilots)if(a.agent===id)a.agent=name;
      }
      db.squads=db.squads.filter(s=>s.name!==id);db.squads.push({name,leader:data.leader,members,roles,description:data.description,instructions:data.instructions});
      return done('squad',name,'Squad saved.');
    }
    if(type==='autoEditor'){
      let a=db.autopilots.find(item=>item.id===id);
      if(!a){a={id:next('AUTO',db.autopilots),history:[]};db.autopilots.push(a);}
      Object.assign(a,data,{enabled:data.enabled==='on',checks:data.checks.split('\n').map(c=>c.trim()).filter(Boolean)});return done('autopilot',a.id,'Autopilot saved.');
    }
    if(type==='newProject'){if(db.projects.includes(data.name))throw Error('This project already exists.');db.projects.push(data.name);return done('project',data.name,'Project created.');}
    if(type==='agentConfig'){Object.assign(db.agents.find(a=>a.name===id),data,{starters:starterLines(data.starters)});return done('agent',id,'Settings saved.');}
    if(type==='newAgent'){if(Object.hasOwn(ownerOptions(),data.name))throw Error('This agent already exists.');db.agents.push({name:data.name,role:data.role,instructions:data.instructions,starters:starterLines(data.starters),runtime:data.runtime,runtimeId:data.runtimeId,concurrency:Number(data.concurrency),skills:[data.skill]});return done('agent',data.name,'Agent profile saved.');}
    if(type==='suggest'){
      const url=new URL(data.url);
      if(!['https:','http:'].includes(url.protocol))throw Error('Enter an HTTPS or HTTP source.');
      const slug=data.name.toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'')||'skill';
      if(db.skills.some(s=>s.source===url.href||s.id===slug))throw Error('This skill is already in the directory.');
      db.skills.push({id:slug,name:data.name,source:url.href,author:workspace().name,stage:Number(data.stage),description:data.reason});
      return done('skill',slug,'Added to the '+workspace().name+' directory.');
    }
    if(type==='note'){db.notes.push({id:crypto.randomUUID(),at:Date.now(),author:data.author||'Patrick',page:routes[route().page],text:data.text,date:date(Date.now())});return done('notes','','Note saved.');}
    if(type==='search')show('search',data.q,inside);
  }
  document.addEventListener('submit',ev=>{ev.preventDefault();try{submit(ev.target);}catch(err){showSaveError(err);}});
  document.addEventListener('click',async ev=>{
    try{
    document.querySelectorAll('.display-dropdown[open],.column-options[open]').forEach(menu=>{if(!menu.contains(ev.target))menu.open=false;});
    if(ev.target.closest('.skip-link')){ev.preventDefault();$('#main').focus();return;}
    const mobileLink=ev.target.closest('.rail a');
    if(mobileMenu&&mobileLink){ev.preventDefault();mobileMenu=false;if(location.hash===mobileLink.hash)render();else location.hash=mobileLink.hash;return;}
    const b=ev.target.closest('[data-act]');if(!b)return;
    if(mobileMenu&&b.closest('.rail')&&b.dataset.act!=='menu')mobileMenu=false;
    const id=b.dataset.id||'',inside=!!b.closest('#assistant');
    switch(b.dataset.act){
      case 'pickEmoji':{
        const f=b.closest('form');f.elements.emoji.value=id;
        f.querySelector('.avatar-choice-preview').textContent=id||'—';
        f.querySelectorAll('.emoji-palette button').forEach(button=>button.setAttribute('aria-pressed',String(button.dataset.id===id)));
        f.elements.emoji.focus();break;
      }
      case 'exportUnsaved':download('Workpal-unsaved.json',JSON.stringify({workspace:workspace(),data:db,drafts:draftRecords(workspace().id)},null,2));break;
      case 'reloadSaved':{
        captureDrafts();localStorage.setItem('workpal.recovery.'+crypto.randomUUID(),JSON.stringify({workspace:workspace(),data:db,drafts:draftRecords(workspace().id),at:Date.now()}));location.reload();break;
      }
      case 'switchSpace':openSpace(id);break;
      case 'menu':mobileMenu=!mobileMenu;render();break;
      case 'collapseNav':if(innerWidth<768)mobileMenu=false;else navCollapsed=!navCollapsed;render();break;
      case 'filters':filtersOpen=!filtersOpen;render();break;
      case 'inboxTab':inboxTab=id;refresh();break;
      case 'inboxRead':{const state=db.inbox[id]??={},activity=notificationActivity(db.tasks.find(t=>t.id===id)),unread=notificationRead(state,activity);state.readAt=unread?0:activity.at;state.readToken=unread?'':activity.token;write();refresh();break;}
      case 'inboxArchive':{const state=db.inbox[id]??={},activity=notificationActivity(db.tasks.find(t=>t.id===id));state.archivedAt=inboxTab==='archived'?0:activity.at;state.archivedToken=inboxTab==='archived'?'':activity.token;write();refresh();break;}
      case 'inboxSnooze':{const state=db.inbox[id]??={};state.until=inboxTab==='snoozed'?0:Date.now()+3600000;write();refresh();break;}
      case 'cancelWakeup':db.wakeups.find(w=>w.id===id).state='Cancelled';write();refresh();break;
      case 'runQuick':{const [taskId,actionId]=id.split('|');const a=db.quickActions.find(a=>a.id===actionId);WorkpalStudio.comment(db.tasks.find(t=>t.id===taskId),(a.agent?'@'+a.agent+' ':'')+a.prompt);output('issue',taskId,'Request posted.',inside);break;}
      case 'draftQuick':{
        const a=db.quickActions.find(a=>a.id===id),el=b.closest('form').elements.text;
        el.value=(a.agent?'@'+a.agent+' ':'')+a.prompt;b.closest('.comment-suggestions').remove();el.focus();break;
      }
      case 'subscribe':{const t=db.tasks.find(t=>t.id===id);t.subscribed=!t.subscribed;write();refresh();break;}
      case 'resolveThread':{const [taskId,entryId]=id.split('|');const e=db.tasks.find(t=>t.id===taskId).activity.find(e=>e.id===entryId);e.resolved=!e.resolved;write();refresh();break;}
      case 'triggerAuto':WorkpalStudio.triggerAutopilot(id);output('autopilot',id,'Trigger recorded.',inside);break;
      case 'applyView':{const v=db.views.find(v=>v.id===id);issueStatus=v.status;issueOwner=v.owner;taskFilter=v.query;layout=v.layout==='board'?'board':'list';issuePrefs().layout=layout;write();show('tasks','',inside);break;}
      case 'claimRun':{changeRun(db.runs.find(r=>r.id===id),'claim');output('run',id,'Run started.',inside);break;}
      case 'finishRun':{changeRun(db.runs.find(r=>r.id===id),'finish');output('run',id,'Run ended without a delivery.',inside);break;}
      case 'archiveFilter':archivedChats=!archivedChats;render();break;
      case 'pinChat':{const c=currentConversation();c.pinned=!c.pinned;write();dismiss();render();break;}
      case 'archiveChat':{const c=currentConversation();c.archived=!c.archived;db.currentChat=null;draftAgent='';draftText='';chat=false;write();dismiss();render();break;}
      case 'cancelChatRun':{
        const r=db.runs.find(r=>r.id===id);
        if(r?.status==='queued'){r.status='cancelled';r.events.push({type:'run.cancelled',text:'Cancelled by Patrick',at:Date.now()});for(const c of db.conversations)for(const m of c.messages)if(m.run===id)m.queued=false;write();render();}
        break;
      }
      case 'chatSettings':show('conversationSettings',id,false);break;
      case 'chooseAgent':show('recipients','',false);break;
      case 'startThread':newThread(id);break;
      case 'openThread':dismiss();db.currentChat=id;loadDraft();chat=route().page!=='chatroom';write();render();break;
      case 'expandChat':chat=false;draftAgent=currentConversation()?.agent||draftAgent||db.agents[0]?.name||'';show('chatroom','',false);break;
      case 'starter':{const field=$('#assistant textarea[name="prompt"]');field.value=id;persistDraft(id);field.focus();break;}
      case 'chat':mobileMenu=false;newThread(db.agents[0]?.name||'');break;
      case 'closeChat':chat=false;if(route().page==='chatroom'){db.currentChat=null;draftAgent='';write();render();}else paintChat();$('.chat-launcher [data-act=chat]')?.focus();break;
      case 'surface':{const cut=id.indexOf('|');show(id.slice(0,cut),id.slice(cut+1),inside);break;}
      case 'dismiss':dismiss();break;
      case 'skillTab':directoryTab=id;refresh();break;
      case 'detach':{const [skill,name]=JSON.parse(id);const a=db.agents.find(a=>a.name===name);a.skills=a.skills.filter(s=>s!==skill);write();refresh();break;}
      case 'cancel':{const r=db.runs.find(r=>r.id===id);changeRun(r,'cancel');output('run',id,'Run cancelled.',inside);break;}
      case 'copyCommand':{const command=installCommand(db.skills.find(s=>s.id===id));try{await navigator.clipboard.writeText(command);toast('Install command copied.');}catch{const field=document.createElement('textarea');field.value=command;field.readOnly=true;b.after(field);field.select();}break;}
      case 'pin':db.panels=db.panels.includes(id)?db.panels.filter(k=>k!==id):[...db.panels,id];write();refresh();toast(db.panels.includes(id)?'Panel pinned to Analytics.':'Panel unpinned.');break;
      case 'layout':case 'setLayout':layout=id|| (layout==='list'?'board':'list');issuePrefs().layout=layout;write();refresh();break;
      case 'collapseGroup':{const prefs=issuePrefs();prefs.collapsed=prefs.collapsed.includes(id)?prefs.collapsed.filter(x=>x!==id):[...prefs.collapsed,id];write();refresh();break;}
      case 'hideColumn':case 'toggleColumn':{const prefs=issuePrefs();prefs.hidden=prefs.hidden.includes(id)?prefs.hidden.filter(x=>x!==id):[...prefs.hidden,id];write();refresh();break;}
      case 'toggleCardProperty':{const prefs=issuePrefs();prefs.properties=prefs.properties.includes(id)?prefs.properties.filter(x=>x!==id):[...prefs.properties,id];write();refresh();break;}
      case 'chatBack':db.currentChat=null;draftAgent='';draftText='';write();render();break;
      case 'bookmark':db.bookmarks=db.bookmarks.includes(id)?db.bookmarks.filter(x=>x!==id):[...db.bookmarks,id];write();refresh();break;
      case 'share':{const url=new URL(location.href);url.hash=scoped('skills?id='+encodeURIComponent(id));const s=db.skills.find(x=>x.id===id);const value=url.protocol==='file:'?s.name+' · '+s.source+'\nOpen the shared Workpal.html file and select '+s.name+' in Skill Hub.':url.href;try{await navigator.clipboard.writeText(value);toast('Share text copied.');}catch{const field=document.createElement('textarea');field.value=value;field.readOnly=true;b.after(field);field.select();}break;}
      case 'exportDoc':{const r=db.reports.find(r=>r.id===id);download(r.id+'.md','# '+r.title+'\n\n'+workspace().name+' · '+date(r.at)+'\n\n'+r.body);break;}
      case 'exportNotes':download('Workpal-review.md',db.notes.map(n=>'## '+n.page+' · '+(n.author||'Reviewer')+'\n\n'+n.text).join('\n\n'));break;
    }
    }catch(err){showSaveError(err);}
  });
  document.addEventListener('dragstart',ev=>{
    const row=ev.target.closest('[draggable=true]');
    if(row)ev.dataTransfer.setData('application/workpal-issue',row.dataset.id.slice(6));
  });
  document.addEventListener('dragover',ev=>{
    if(ev.target.closest('[data-drop-state]')&&ev.dataTransfer.types.includes('application/workpal-issue'))ev.preventDefault();
  });
  document.addEventListener('drop',ev=>{
    const lane=ev.target.closest('[data-drop-state]');
    const t=db.tasks.find(t=>t.id===ev.dataTransfer.getData('application/workpal-issue'));
    if(!t||!lane||lane.dataset.dropState===t.status)return;
    ev.preventDefault();
    show('move',t.id+'|'+lane.dataset.dropState,!!lane.closest('#assistant'));
  });
  document.addEventListener('input',ev=>{
    const el=ev.target;persistFormDraft(el.form);if(el.name==='prompt')persistDraft(el.value);if(el.name==='text')quickSuggestions(el);if(!el.dataset.filter)return;
    const parent=el.closest('.resource-body,.modal-body,#page-content');const pos=el.selectionStart;
    if(el.dataset.filter==='task'){taskFilter=el.value;parent.innerHTML=tasks();}else{skillFilter=el.value;parent.innerHTML=skillsView();}
    const replacement=parent.querySelector('[data-filter]');replacement.focus();replacement.setSelectionRange(pos,pos);
  });
  document.addEventListener('change',ev=>{
    const el=ev.target;persistFormDraft(el.form);
    if(el.name==='workspaceTheme'){
      applyTheme(el.value);
      try{localStorage.setItem(themeKey,theme);}catch{toast('Theme applied. Browser storage is unavailable.');}
      return;
    }
    if(el.form?.dataset.form==='assignWork'&&el.name==='status'){
      const checkbox=el.form.elements.queueRun;
      checkbox.disabled=el.value==='backlog'||!WorkpalStudio.handlingAgent(el.form.dataset.id);
      if(checkbox.disabled)checkbox.checked=false;
      return;
    }
    if(['issue','issueProperty'].includes(el.form?.dataset.form)){syncIssueForm(el.form);persistFormDraft(el.form);return;}
    if(el.form?.dataset.form==='launch'){
      const f=el.form;
      if(el.name==='task'){
        const owner=db.tasks.find(t=>t.id===el.value)?.owner;
        if(WorkpalStudio.handlingAgent(owner))f.elements.agent.value=WorkpalStudio.handlingAgent(owner).name;
      }
      f.querySelector('.delegation-context').innerHTML=delegationContext(f.elements.task.value,f.elements.agent.value,f.elements.skill.value);
      return;
    }
    if(el.form?.dataset.form==='decision'&&el.name==='choice'){
      const f=el.form,approving=el.value==='approve';
      f.querySelector('.review-ack').hidden=!approving;
      f.elements.acknowledged.required=approving;
      f.elements.note.required=!approving;
      return;
    }
    if(el.hasAttribute('data-stage-filter'))skillStage=el.value;
    else if(el.hasAttribute('data-sort-skills'))sortSkills=el.value;
    else if(el.hasAttribute('data-issue-status'))issueStatus=el.value;
    else if(el.hasAttribute('data-issue-owner'))issueOwner=el.value;
    else return;
    refresh();
  });
  document.addEventListener('keydown',ev=>{
    if(ev.key==='Escape'){const menu=document.querySelector('.display-dropdown[open],.column-options[open]');if(menu){ev.preventDefault();menu.open=false;menu.querySelector('summary').focus();return;}}
    if(ev.key==='Escape'&&mobileMenu&&!$('#dialog').open){ev.preventDefault();mobileMenu=false;render();$('.mobile-only[data-act=menu]')?.focus();return;}
    const quickMenu=ev.target.closest('form')?.querySelector('.comment-suggestions');
    if(quickMenu&&['ArrowDown','ArrowUp','Enter','Escape'].includes(ev.key)&&!ev.isComposing){
      const buttons=[...quickMenu.querySelectorAll('button')],index=buttons.indexOf(document.activeElement);
      if(ev.key==='Escape'){ev.preventDefault();quickMenu.remove();return;}
      if(ev.key==='Enter'&&ev.target.tagName==='TEXTAREA'&&buttons.length){ev.preventDefault();buttons[0].click();return;}
      if(ev.key.startsWith('Arrow')&&buttons.length){ev.preventDefault();buttons[(index+(ev.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length].focus();return;}
    }
    if(ev.target.name==='text'&&['comment','threadReply'].includes(ev.target.form?.dataset.form)&&(ev.metaKey||ev.ctrlKey)&&ev.key==='Enter'){ev.preventDefault();ev.target.form.requestSubmit();return;}
    if((ev.metaKey||ev.ctrlKey)&&ev.key.toLowerCase()==='k'){ev.preventDefault();show('search','',false);}
    if((ev.metaKey||ev.ctrlKey)&&ev.key.toLowerCase()==='j'&&route().page!=='chatroom'){
      ev.preventDefault();
      if(ev.shiftKey)newThread(db.agents[0]?.name||'');
      else {chat=!chat;loadDraft();render();$('#assistant textarea[name="prompt"]')?.focus();}
    }
    if(ev.key==='Escape'&&!$('#dialog').open&&chat){chat=false;paintChat();}
    if(ev.target.name==='prompt'&&ev.key==='Enter'&&!ev.shiftKey&&!ev.isComposing){ev.preventDefault();ev.target.form.requestSubmit();}
  });
  $('#dialog').addEventListener('close',()=>{captureDrafts($('#dialog'));if(!$('#dialog').open)modalSurface=null;});
  window.addEventListener('pagehide',()=>captureDrafts());
  let visibleHash;
  function openSpace(id){
    dismiss();
    if(id===workspace().id){chat=false;mobileMenu=false;render();return;}
    location.hash=scoped('overview',id);
    enter();
  }
  function enter(){
    if(!location.hash){
      const last=WorkpalStudio.lastWorkspace();
      const id=WorkpalStudio.listWorkspaces().some(w=>w.id===last)?last:'tap';
      location.replace('#'+scoped(id==='tap'?'tasks':'overview',id));
    }
    if(visibleHash===location.hash)return;
    visibleHash=location.hash;
    const id=route().workspaceId;
    const changed=id!==workspace().id;
    dismiss();
    if(!WorkpalStudio.selectWorkspace(id)){
      location.replace('#overview');
      toast('Workspace unavailable in this browser.');
      return;
    }
    db=WorkpalStudio.db;db.runtimes??=[];db.inbox??={};db.quickActions??=[];db.wakeups??=[];prepareConversations();
    if(changed){
      chat=false;draftAgent='';draftText='';
      taskFilter=skillFilter=skillStage=issueStatus=issueOwner='';
      layout='list';directoryTab='all';sortSkills='rank';
    }
    layout=issuePrefs().layout;loadDraft();
    if(route().page==='chatroom')chat=false;
    mobileMenu=false;render();window.scrollTo(0,0);
  }
  setInterval(()=>{
    try{
    checkWakeups();
    const now=new Date(),day=now.toLocaleDateString('en-CA'),time=now.toTimeString().slice(0,5);
    for(const a of db.autopilots||[]){
      if(!a.enabled||a.time!==time||a.lastDay===day)continue;
      a.lastDay=day;WorkpalStudio.triggerAutopilot(a.id,'Schedule');refresh();
    }
    }catch(err){showSaveError(err);}
  },15000);
  WorkpalAnalytics.init({getDb:()=>db,workspace,teams,states,scoped,icon,esc,avatar,issueList,render,write});
  window.addEventListener('hashchange',enter);enter();
})();
