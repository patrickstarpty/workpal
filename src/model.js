// Shared workspace records for page views, agent surfaces and report snapshots.
globalThis.WorkpalStudio = (() => {
  const source = WorkpalData;
  const key = 'workpal.studio.v2';
  const states = { backlog: 'Backlog', todo: 'To do', active: 'In progress', review: 'In review', blocked:'Blocked', done: 'Done' };
  const teams = { product: 'Product', engineering: 'Engineering', quality: 'Quality', unassigned: 'Unassigned' };
  const stages = ['Discover', 'Design', 'Build', 'Verify', 'Ship', 'Learn'];
  const handoffs = [
    ['Product partner', 'Confirm the intended user, problem and acceptance criteria.'],
    ['Architecture partner', 'Review the implementation plan and technical trade-offs.'],
    ['Engineering partner', 'Review the proposed change and its test plan.'],
    ['Quality partner', 'Check the acceptance evidence and record a decision.'],
    ['Engineering partner', 'Inspect the release scope and rollback plan.'],
    ['Product partner', 'Capture the outcome and a reusable practice.'],
  ];
  const titles = ['Trace sources in Knowledge Chat', 'Test document upload edge cases', 'Define acceptance criteria for test design', 'Clarify knowledge search states', 'Review conversational context boundaries', 'Define Skill Hub admission criteria', 'Record human intervention events', 'Prioritize the next release backlog'];
  const descriptions = ['Link each answer citation to the original document passage.', 'Cover empty files, duplicate uploads and failed parses.', 'Specify the inputs, outputs and human checks for generated tests.', 'Distinguish loading, empty and failed search results.', 'Compare context retention strategies for follow-up questions.', 'Record source, authorship and validation for shared skills.', 'Capture when and why a person intervenes in a run.', 'Order the next release by customer impact and dependency.'];
  const acceptance = [
    ['Open the cited passage', 'Explain when the source is missing', 'Check keyboard navigation'],
    ['Reject empty files', 'Handle duplicate uploads', 'Allow retry after a failed parse'],
    ['List representative scenarios', 'Define the quality rubric'],
    ['Use consistent state labels', 'Support keyboard navigation'],
    ['Document trade-offs', 'Specify retention boundaries'],
    ['Credit the author', 'State the skill’s scope and validation status'],
    ['Separate review from takeover', 'Exclude sensitive content'],
    ['Identify release dependencies', 'Confirm the priority order'],
  ];
  const skillDescriptions = ['Clarify constraints and acceptance criteria before implementation.', 'Break an approved design into small, verifiable engineering tasks.', 'Drive implementation from a failing test to a verified behavior.', 'Check browser workflows with repeatable tests and screenshots.', 'Design a distinctive interface around a specific product context.', 'Review interaction quality and accessibility in a web interface.', 'Collect fresh evidence before marking a task complete.', 'Turn a repeated practice into a skill with a test case.'];
  const agents = source.agents.map((a,i) => ({name:handoffs[i][0], role:['Product definition','System design','Implementation','Verification'][i],runtime:a.runtime,skills:a.skills}));
  const builtInSkills = () => source.skills.map((s,i) => ({id:s.id,name:s.name,author:s.author,source:s.source,stage:s.stage,description:skillDescriptions[i]}));
  function read(key) { try { return JSON.parse(localStorage.getItem(key)); } catch { return null; } }
  const old = read('workpal.prototype.v1') || {};
  function initial(oldState = old) {
    const tasks = (Array.isArray(oldState.tasks) ? oldState.tasks : source.tasks.filter(t=>t.project==='TAP')).map(t => {
      const i = source.tasks.findIndex(seed => seed.id === t.id);
      const seed = source.tasks[i];
      const ownerIndex = source.agents.findIndex(a => a.name === t.owner);
      return {id:t.id,title:t.title === seed?.title ? titles[i] : t.title, description:t.description === seed?.description ? descriptions[i] : t.description,
        checks: JSON.stringify(t.checks) === JSON.stringify(seed?.checks) ? acceptance[i] : t.checks, team:source.taskTeam(t),project:t.project,
        owner:ownerIndex >= 0 ? agents[ownerIndex].name : t.owner === '研究者' ? 'Patrick' : t.owner,status:t.status==='todo'?'backlog':t.status,priority:t.priority === '高' ? 'High' : 'Normal',stage:t.stage};
    });
    const now = Date.now();
    const sampleTask = tasks.find(t => t.id === 'TAP-028' && t.status === 'review');
    const runs = sampleTask ? [{id:'RUN-014',task:sampleTask.id,stage:3,status:'waiting',events:stages.slice(0,4).map((s,i)=>({type:i===3?'review.requested':'stage.completed',text:s,at:now-(4-i)*60000})),skill:'webapp-testing'}] : [];
    return {tasks,projects:[...new Set(['TAP',...tasks.map(t=>t.project)])],agents,skills:builtInSkills(),runs,bookmarks:oldState.bookmarks || ['brainstorming'],notes:oldState.notes || [],reports:[],messages:[]};
  }
  const spacePrefix = 'workpal.space.';
  const home = {id:'tap',name:'TAP'};
  let active = home;
  let db = read(key) || initial();
  if (!db.issueSchema) {
    if (read(key)) {
      for (const t of db.tasks) {
        if (t.status === 'todo') t.status = 'backlog';
        if (t.owner === 'Researcher') t.owner = 'Patrick';
        if (t.id === 'WP-014') {
          if (t.title === 'Pair tasks for the pilot study') t.title = titles[7];
          if (t.description === 'Match tasks by domain, difficulty and expected change size.') t.description = descriptions[7];
          if (t.checks.join('|') === 'Define task strata|Record likely confounders') t.checks = acceptance[7];
        }
      }
    }
    db.issueSchema = 1;
  }
  // Refile untouched starter issues from the former two-project seed. Keep authored work in place.
  if (!db.tapProjectMigration) {
    const legacyTitles = ['Define Skill Hub admission criteria','Record human intervention events','Prioritize the next release backlog'];
    let refiled=false;
    for(const t of db.tasks) {
      const i = ['WP-012','WP-013','WP-014'].indexOf(t.id);
      if(i<0 || t.project!=='Workpal' || t.title!==legacyTitles[i] || t.activity?.length)continue;
      refiled=true;
      t.project='TAP';
      if(i===0 && t.description===descriptions[5]){
        t.title='Define admission criteria for TAP design skills';
        t.description='Document the source and validation needed for reusable skills used in TAP development.';
      }
    }
    if(refiled&&!db.tasks.some(t=>t.project==='Workpal'))db.projects=db.projects.filter(p=>p!=='Workpal');
    db.tapProjectMigration = true;
  }
  const directoryPicks = [
    ['find-skills','Find Skills','vercel-labs/skills',0,'Discover skills by the task you want an agent to complete.',1],
    ['agent-browser','Agent Browser','vercel-labs/agent-browser',3,'Drive browser interactions from an agent workflow.',3],
    ['vercel-react-best-practices','React Best Practices','vercel-labs/agent-skills',2,'Review React and Next.js performance patterns during implementation.',57],
    ['impeccable','Impeccable','pbakaus/impeccable',1,'Refine interface typography, layout and interaction design.',214]
  ];
  function populateDirectory(items) {
    for(const s of items){
      const upstream=source.skills.find(item=>item.id===s.id);
      if(upstream)s.repo=upstream.repo;
    }
    for(const [id,name,repo,stage,description,rank] of directoryPicks){
      if(!items.some(s=>s.id===id)) items.push({id,name,repo,author:repo.split('/')[0],stage,description,
        source:'https://skills.sh/'+repo+'/'+id,rank});
    }
    const knownRanks={'frontend-design':15,'web-design-guidelines':62,'skill-creator':199,brainstorming:202};
    for(const s of items) if(Object.hasOwn(knownRanks,s.id))s.rank=knownRanks[s.id];
    return items;
  }
  populateDirectory(db.skills);
  db.panels ??= [];
  for (const t of db.tasks) t.activity ??= [];
  for (const r of db.runs) r.agent ??= db.tasks.find(t=>t.id===r.task)?.owner;
  function save() {
    try {
      if(active.id===home.id)localStorage.setItem(key,JSON.stringify(db));
      else localStorage.setItem(spacePrefix+active.id,JSON.stringify({name:active.name,data:db}));
      return true;
    } catch {return false;}
  }
  function listWorkspaces(){
    const result=[home];
    try {
      for(let i=0;i<localStorage.length;i++){
        const k=localStorage.key(i);
        if(!k?.startsWith(spacePrefix))continue;
        const item=read(k);
        if(item?.data)result.push({id:k.slice(spacePrefix.length),name:item.name});
      }
    } catch { /* The default workspace remains usable without storage. */ }
    return result;
  }
  function createWorkspace(value){
    const name=value.trim();
    if(!name||name.length>60)throw Error('Enter a workspace name of 1–60 characters.');
    if(listWorkspaces().some(w=>w.name.toLowerCase()===name.toLowerCase()))throw Error('A workspace with this name already exists.');
    const id=crypto.randomUUID();
    const data={projects:[],tasks:[],agents:[],skills:populateDirectory(builtInSkills()),runs:[],
      bookmarks:[],notes:[],reports:[],messages:[],panels:[],issueSchema:1};
    try{localStorage.setItem(spacePrefix+id,JSON.stringify({name,data}));}
    catch{throw Error('Workspace could not be saved in this browser.');}
    return id;
  }
  function selectWorkspace(id){
    if(active.id!==id){
      const item=id===home.id?{name:home.name,data:read(key)}:read(spacePrefix+id);
      if(!item?.data)return false;
      db=item.data;
      active={id,name:item.name};prepareWork();
    }
    try{localStorage.setItem('workpal.lastSpace',JSON.stringify(id));}catch{}
    return true;
  }
  const lastWorkspace=()=>read('workpal.lastSpace')||home.id;
  function count(items) { return Object.fromEntries(Object.keys(states).map(s=>[s,items.filter(t=>t.status===s).length])); }
  function next(prefix, records) {
    const seq = Math.max(0,...records.filter(r=>r.id.startsWith(prefix+'-')).map(r=>Number(r.id.split('-').pop())||0))+1;
    return prefix+'-'+String(seq).padStart(3,'0');
  }
  function artifact(task,stage,skill) {
    const criteria=task.checks.join(' / ');
    const outputs=[
      ['Acceptance brief',task.description+'\nAcceptance: '+criteria],
      ['Handoff plan','Owner: '+task.owner+' · Project: '+task.project+'\nPlan a small change for '+task.title+' and attach evidence for each criterion.'],
      ['Implementation checklist',task.checks.map((c,i)=>(i+1)+'. Implement and verify: '+c).join('\n')],
      ['Verification worksheet',task.checks.map(c=>'[ ] '+c+' — reviewer evidence required').join('\n')],
      ['Release review','Scope: '+task.title+'\nConfirm acceptance, record a rollback owner and review the change before release.'],
      ['Learning record','Review the decision trail for '+task.id+'. Document the intervention and retest '+(skill||'the method')+' on a matched task.'],
    ];
    return {stage,title:outputs[stage][0],body:outputs[stage][1],at:Date.now()};
  }
  for(const run of db.runs){
    const task=db.tasks.find(t=>t.id===run.task);
    if(task && !run.artifacts)run.artifacts=stages.slice(0,run.stage+1).map((_,i)=>artifact(task,i,run.skill));
  }
  function log(task, text) {
    task.activity.unshift({text, at:Date.now(), author:'Patrick'});
  }
  function openRun(id, agent){
    return db.runs.find(r => r.task === id && (agent ? r.agent === agent : r.kind !== 'reply') && ['queued','running'].includes(r.status));
  }
  function prepareWorkflows(){
    db.workflows ??= [];
    for(const config of db.projectSettings || []){
      if(!config.reviewer || config.workflowId)continue;
      const workflow={id:next('FLOW',db.workflows),name:config.project+' review',steps:[
        {status:'active',owner:'',instructions:'Implement and verify the issue.',next:'review',rejected:''},
        {status:'review',owner:config.reviewer,instructions:'Review the result against the acceptance criteria.',next:'done',rejected:'active'}
      ]};
      db.workflows.push(workflow);config.workflowId=workflow.id;
    }
    for(const run of db.runs){
      run.events ??= [];run.artifacts ??= [];
      if(!['waiting','returned'].includes(run.status))continue;
      if(run.status==='returned')run.reviewDecision='return';
      run.status='finished';run.delivered=true;
    }
  }
  function workflowFor(project){
    const id=db.projectSettings.find(config=>config.project===project)?.workflowId;
    return db.workflows.find(flow=>flow.id===id)||{id:'default',name:'Default',steps:[]};
  }
  function transitionIssue(task,status,{handoff=true}={}){
    if(!Object.hasOwn(states,status))throw Error('Choose a valid issue status.');
    const previousStatus=task.status;
    const previousOwner=task.owner;
    const step=workflowFor(task.project).steps.find(item=>item.status===status);
    const config=db.projectSettings.find(item=>item.project===task.project);
    const target=step?.owner==='Project lead'?config?.lead:step?.owner;
    const nextOwner=handoff&&previousStatus!==status&&target?target:previousOwner;
    const nextAgent=handlingAgent(nextOwner);
    if(nextOwner!==previousOwner){
      const previousAgent=handlingAgent(previousOwner);
      for(const run of db.runs.filter(r=>r.task===task.id&&r.agent===previousAgent?.name&&['queued','running'].includes(r.status))){
        run.status='cancelled';
        run.events.push({type:'run.cancelled',text:'Handed off to '+nextOwner,at:Date.now()});
      }
      task.owner=nextOwner;
      log(task,'Handed off to '+nextOwner+(step.instructions?' · '+step.instructions:''));
    }
    task.status=status;
    if(previousStatus!==status)log(task,'Moved to '+states[status]+'.');
    if(handoff&&previousStatus!==status&&target&&nextAgent&&status!=='backlog'){
      const run=start(task,nextAgent.skills[0]||'',nextAgent.name,true);
      run.origin='Workflow · '+workflowFor(task.project).name;
      run.instructions=step.instructions||'';
      run.workflowStep=status;
      run.events.push({type:'workflow.handoff',text:step.instructions||states[status],at:Date.now()});
    }
    save();return task;
  }
  function prepareWork(){
    prepareWorkflows();
    if(db.workReady)return;
    db.squads=[];db.autopilots=[];db.views=[];db.projectSettings=[];
    if(active.id==='tap'&&db.projects.includes('TAP')){
      const lead=db.agents.find(a=>a.name==='Engineering partner');
      if(lead){
        db.squads.push({name:'TAP delivery',leader:lead.name,members:[...db.agents.map(a=>a.name),'Patrick'],description:'Coordinate TAP delivery and the release decision.',instructions:'Delegate implementation and verification separately. Patrick decides release readiness.'});
        db.autopilots.push({id:'AUTO-001',name:'Daily delivery brief',agent:lead.name,project:'TAP',prompt:'Summarize blocked work and issues awaiting a release decision.',mode:'issue',time:'09:00',enabled:false,history:[]});
      }
      db.projectSettings.push({project:'TAP',lead:'Patrick',description:'Build the knowledge and test-design workspace. Each release must preserve citation traceability and recover from failed uploads.',reviewer:'',due:''});
      db.views.push({id:'VIEW-001',name:'Needs review',status:'review',owner:'',query:'',layout:'list'});
      // Keep the existing project and issue IDs usable when a saved workspace upgrades.
      const parent={id:next('TAP',db.tasks),title:'Review the Knowledge Chat rollout',project:'TAP',stage:2,status:'active',team:'product',priority:'High',
        owner:lead?'TAP delivery':'Patrick',description:'Decide whether to expand Knowledge Chat access. Check citations, confirm recovery from failed uploads and obtain release approval.',
        checks:['Verify citations against the source','Confirm retry behavior','Record the release decision'],tags:['Release'],activity:[],subscribed:true};
      db.tasks.push(parent);
      const risk={id:next('TAP',db.tasks),title:'Confirm recovery after interrupted upload',project:'TAP',parent:parent.id,stage:3,status:'blocked',team:'engineering',priority:'High',
        owner:lead?.name||'Patrick',description:'Wait for the second upload attempt before opening the release to more teams.',checks:['Retain upload progress on reconnect'],tags:['Release risk'],activity:[],subscribed:true};
      db.tasks.push(risk);
      const signoff={id:next('TAP',db.tasks),title:'Approve the next rollout cohort',project:'TAP',parent:parent.id,stage:3,status:'todo',team:'product',priority:'High',
        owner:'Patrick',description:'Review the upload and citation evidence before expanding access.',checks:[],tags:['Release'],activity:[]};
      db.tasks.push(signoff);
      parent.activity.push({id:'release-note',kind:'comment',author:'Patrick',text:'Hold the current rollout until the upload follow-up is closed.',at:Date.now()-86400000,
        replies:[{author:'Patrick',text:'Keep the approval on the sign-off issue so the decision is easy to find.',at:Date.now()-82000000}]});
      if(lead){
        db.runs.push({id:next('RUN',db.runs),task:risk.id,agent:lead.name,stage:3,status:'failed',skill:'webapp-testing',events:[
          {type:'run.started',text:'Check upload recovery',at:Date.now()-7200000},{type:'run.failed',text:'Upload verification timed out waiting for a second response.',at:Date.now()-7190000}],artifacts:[]});
      }

    }
    db.workReady=true;prepareWorkflows();
  }
  function handlingAgent(owner){
    const squad=db.squads?.find(s=>s.name===owner);
    return db.agents.find(a=>a.name===(squad?.leader||owner));
  }
  function triggerAutopilot(id,source='Manual'){
    const auto=db.autopilots.find(a=>a.id===id);
    if(!auto)throw Error('Autopilot not found.');
    const at=Date.now(),agent=handlingAgent(auto.agent);
    const event={at,source,status:'Skipped',task:'',run:'',note:''};
    if(!agent)event.note='The assignee is unavailable.';
    else if(auto.mode==='run')event.note='Runtime offline. Run-only triggers require an online runtime.';
    else {
      const task={id:next(auto.project.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,5)||'ISS',db.tasks),project:auto.project,
        title:auto.name,description:auto.prompt,owner:auto.agent,team:'unassigned',priority:'Normal',status:'todo',stage:0,activity:[],checks:[]};
      db.tasks.push(task);log(task,'Created by '+auto.name+' · '+source);
      const run=start(task,agent.skills[0]||'',agent.name,true);
      run.origin=auto.name;
      Object.assign(event,{status:'Issue created',task:task.id,run:run.id});
    }
    auto.history.unshift(event);save();return event;
  }
  function start(task, skill, agent = handlingAgent(task.owner)?.name||task.owner, queued = false) {
    if (!db.agents.some(a => a.name === agent)) throw Error('Select an agent to run this issue.');
    const existing = openRun(task.id,agent);
    if (existing) return existing;
    const run = {id:next('RUN',db.runs), task:task.id, agent, stage:queued?task.stage:2, status:queued?'queued':'running', skill,
      events:[{type:queued?'run.queued':'run.started', text:agent, at:Date.now()}], artifacts:[]};
    const profile=db.agents.find(a=>a.name===agent);
    const project=db.projectSettings.find(p=>p.project===task.project);
    run.context={project:task.project,description:project?.description||'',instructions:profile.instructions||'',skills:[...profile.skills],runtime:profile.runtimeId||'',harness:profile.runtime,model:profile.model||'Default'};
    db.runs.unshift(run);
    if(!queued){task.status='active';task.stage=2;}
    log(task, agent+(queued?' queued for ':' started ')+run.id+'.');
    save();
    return run;
  }
  function comment(task, text, {replyTo} = {}) {
    if(replyTo){
      const thread=task.activity.find(entry=>entry.id===replyTo&&entry.kind==='comment');
      if(!thread)throw Error('Discussion unavailable.');
      (thread.replies??=[]).push({id:crypto.randomUUID(),text,author:'Patrick',at:Date.now()});
      thread.resolved=false;
    }else{
      log(task,text);task.activity[0].kind='comment';task.activity[0].id=crypto.randomUUID();
    }
    task.subscribed=true;
    const mentioned=name=>{
      const escaped=name.replace(/[.*+?^${}()|[\]\\]/g,'\\$&');
      return new RegExp('@'+escaped+'(?![\\p{L}\\p{N}_-])','iu').test(text);
    };
    const targets=[...db.agents,...db.squads].filter(item=>mentioned(item.name));
    const recipients=new Map();
    for(const target of targets){
      const agent=handlingAgent(target.name);
      if(agent)recipients.set(agent.name,agent);
    }
    if(!targets.length&&!mentioned('Patrick')&&!mentioned('all')){
      const owner=handlingAgent(task.owner);
      if(owner)recipients.set(owner.name,owner);
    }
    for (const agent of recipients.values()) {
      const current=openRun(task.id,agent.name);
      if(current){
        current.events.push({type:'comment.received',text,at:Date.now()});
        continue;
      }
      const run={id:next('RUN',db.runs),kind:'reply',agent:agent.name,task:task.id,status:'queued',
        stage:task.stage||0,skill:agent.skills[0]||'',events:[{type:'comment.received',text,at:Date.now()},{type:'run.queued',text:agent.name,at:Date.now()}],artifacts:[]};
      db.runs.unshift(run);
      log(task,agent.name+' queued · '+run.id);
    }
    save();
  }
  function changeRun(run, action, note = '') {
    if(!run)throw Error('Run unavailable.');
    if(['approve','return'].includes(action))return decide(run.id,run.stage,action,note);
    const task = db.tasks.find(t => t.id === run.task);
    const record=(type,text)=>run.events.push({type,text,at:Date.now()});
    if(run.status==='queued'&&['claim','cancel'].includes(action)){
      run.status=action==='claim'?'running':'cancelled';
      if(task&&run.kind!=='reply'&&action==='claim'&&['backlog','todo'].includes(task.status)){
        transitionIssue(task,'active',{handoff:false});task.stage=run.stage=2;
      }
      const event=action==='claim'?'run.started':'run.cancelled';
      record(event,run.agent);
      if(task)log(task,run.id+' · '+event);
      save();return run;
    }
    if(run.status!=='running'||!['finish','deliver','cancel'].includes(action))throw Error('This run has changed. Open the latest run.');
    if(action==='deliver'&&!note.trim())throw Error('Add a handoff note before continuing.');
    run.status=action==='cancel'?'cancelled':'finished';
    if(action==='deliver'){
      run.delivered=run.kind!=='reply'&&!!task;
      run.artifacts.push({stage:run.stage,title:run.kind==='reply'?'Response':'Handoff note',body:note,at:Date.now()});
    }
    record(action==='cancel'?'run.cancelled':'run.finished',note||'Execution ended');
    if(task){
      log(task,run.id+' · '+(note||run.status));
      if(run.delivered){
        const step=workflowFor(task.project).steps.find(item=>item.status===task.status);
        run.deliveredFrom=task.status;
        transitionIssue(task,step?.next||'review');
      }
      if(action==='cancel'&&run.kind!=='reply'&&task.status==='active'&&!openRun(task.id))transitionIssue(task,'todo',{handoff:false});
    }
    save();return run;
  }
  function decide(id, expected, choice, reason='') {
    const run=db.runs.find(r=>r.id===id);
    const task=db.tasks.find(t=>t.id===run?.task);
    if(!run||run.stage!==expected||run.status!=='finished'||!run.delivered||run.reviewDecision||task?.status!=='review')throw Error('This review has changed. Open the latest issue.');
    if(!['approve','return'].includes(choice))throw Error('Choose a valid decision.');
    if(choice==='return'&&!reason.trim())throw Error('Add a review note before requesting changes.');
    const step=workflowFor(task.project).steps.find(item=>item.status==='review');
    run.reviewDecision=choice;
    run.events.push({type:choice==='approve'?'issue.approved':'changes.requested',text:reason||task.title,at:Date.now()});
    log(task,run.id+' · '+(choice==='approve'?'Approved':'Changes requested')+(reason?' · '+reason:''));
    transitionIssue(task,choice==='approve'?'done':step?.rejected||'active');
    save();return run;
  }
  function report(kind, team, runId) {
    const run=db.runs.find(r=>r.id===runId);
    const items=db.tasks.filter(t=>!team || t.team===team);
    const execution=kind==='execution';
    if(execution&&!run) throw Error('Select a run first.');
    const title=execution?'Execution report · '+run.id:(team?teams[team]:'Workspace')+' summary';
    const task=db.tasks.find(t=>t.id===run?.task);
    const summary=count(items);
    const lines=execution ? [task?task.id+' · '+task.title:(run.title||'Conversation run'),'State: '+run.status,'Run agent: '+(run.agent||task?.owner||'Unassigned'),'Skill: '+(run.skill||'None'),'','## Decision trail',...run.events.map(ev=>new Date(ev.at).toISOString()+'  '+ev.type+'  '+ev.text),'','## Stage artifacts',...(run.artifacts||[]).map(a=>stages[a.stage]+' · '+a.title+'\n'+a.body),'','## Acceptance criteria',...(task?.checks||[]).map(c=>'- '+c)] :
      [items.length+' tasks · '+summary.active+' active · '+summary.review+' awaiting review · '+summary.done+' completed.','','## Team workload',...Object.entries(teams).filter(([id])=>!team||id===team).map(([id,name])=>name+': '+items.filter(t=>t.team===id).length+' tasks'),'','## Review queue',...items.filter(t=>t.status==='review').map(t=>t.id+' · '+t.title+' — '+t.owner),...(summary.review?[]:['No tasks awaiting review.'])];
    const record={id:next('DOC',db.reports),title,body:lines.join('\n'),at:Date.now()};
    db.reports.unshift(record);save();return record;
  }
  prepareWork();save();
  return {workflowFor,transitionIssue,handlingAgent,triggerAutopilot,get db(){return db;},get workspace(){return active;},listWorkspaces,createWorkspace,selectWorkspace,lastWorkspace,comment,openRun,changeRun,log,states,teams,stages,handoffs,save,count,next,start,decide,report};
})();
