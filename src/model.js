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
  const storedWorkspace = read(key);
  let db = storedWorkspace || initial();
  let storageBase = JSON.parse(JSON.stringify(storedWorkspace || {}));
  let storageExists = !!storedWorkspace;
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
  const storageEqual = (left,right) => JSON.stringify(left) === JSON.stringify(right);
  const storageCopy = value => value === undefined ? undefined : JSON.parse(JSON.stringify(value));
  function storageIdentity(value, collection){
    if(value === null || typeof value !== 'object')return 'value:'+JSON.stringify(value);
    if(value.id !== undefined)return 'id:'+value.id;
    if(['agents','squads','skills'].includes(collection) && value.name !== undefined)return 'name:'+value.name;
    if(collection === 'projectSettings' && value.project !== undefined)return 'project:'+value.project;
    // Legacy notes and message records have no IDs. Their full original content is
    // the stable identity for append/remove merging; never identify notes by time alone.
    return 'entry:'+JSON.stringify(value);
  }
  function storageConflict(path){
    const error=Error('This workspace changed in another tab ('+path+'). Your edits are still open; export them or reload the latest workspace before trying again.');
    error.code='WORKSPACE_CONFLICT';return error;
  }
  function mergeStoredValue(base, local, remote, path='workspace'){
    if(storageEqual(local,remote))return local;
    if(storageEqual(local,base))return remote;
    if(storageEqual(remote,base))return local;
    if(Array.isArray(local)&&Array.isArray(remote)&&(base===undefined||Array.isArray(base))){
      const collection=path.split('.').at(-1),key=value=>storageIdentity(value,collection);
      const before=new Map((base||[]).map(value=>[key(value),value]));
      const here=new Map(local.map(value=>[key(value),value]));
      const there=new Map(remote.map(value=>[key(value),value]));
      // Duplicate identities cannot be merged without guessing which record changed.
      if(before.size!==(base||[]).length||here.size!==local.length||there.size!==remote.length)throw storageConflict(path);
      const result=[];
      for(const id of new Set([...here.keys(),...there.keys(),...before.keys()])){
        const old=before.get(id),ours=here.get(id),theirs=there.get(id);
        let chosen;
        if(storageEqual(ours,theirs))chosen=ours;
        else if(storageEqual(ours,old))chosen=theirs;
        else if(storageEqual(theirs,old))chosen=ours;
        else throw storageConflict(path+' · '+id);
        if(chosen!==undefined)result.push(chosen);
      }
      return result;
    }
    if(local&&remote&&typeof local==='object'&&typeof remote==='object'&&!Array.isArray(local)&&!Array.isArray(remote)&&(base===undefined||(base&&typeof base==='object'&&!Array.isArray(base)))){
      const merged={};
      for(const field of new Set([...Object.keys(base||{}),...Object.keys(local),...Object.keys(remote)])){
        if(path==='workspace'&&field==='_storageRevision')continue;
        const value=mergeStoredValue(base?.[field],local[field],remote[field],path+'.'+field);
        if(value!==undefined)merged[field]=value;
      }
      return merged;
    }
    throw storageConflict(path);
  }
  function applyStoredValue(current,value,path='workspace'){
    if(current===value)return current;
    if(Array.isArray(current)&&Array.isArray(value)){
      const collection=path.split('.').at(-1),existing=new Map(current.map(item=>[storageIdentity(item,collection),item]));
      const items=value.map(item=>applyStoredValue(existing.get(storageIdentity(item,collection)),item,path+'[]'));
      current.splice(0,current.length,...items);return current;
    }
    if(current&&value&&typeof current==='object'&&typeof value==='object'&&!Array.isArray(current)&&!Array.isArray(value)){
      for(const field of Object.keys(current))if(!Object.hasOwn(value,field))delete current[field];
      for(const [field,item] of Object.entries(value))current[field]=applyStoredValue(current[field],item,path+'.'+field);
      return current;
    }
    return storageCopy(value);
  }
  function save() {
    try {
      const storageKey=active.id===home.id?key:spacePrefix+active.id;
      const raw=localStorage.getItem(storageKey);
      const saved=raw?JSON.parse(raw):null;
      const remote=(active.id===home.id?saved:saved?.data)||{};
      if(storageExists&&!saved)throw storageConflict('workspace removed');
      const merged=mergeStoredValue(storageBase,db,remote);
      const candidate={...merged,_storageRevision:Math.max(Number(remote._storageRevision)||0,Number(storageBase._storageRevision)||0)+1};
      localStorage.setItem(storageKey,JSON.stringify(active.id===home.id?candidate:{name:active.name,data:candidate}));
      applyStoredValue(db,candidate);
      storageBase=storageCopy(candidate);storageExists=true;
      return true;
    } catch(error) {
      if(error?.code==='WORKSPACE_CONFLICT')throw error;
      return false;
    }
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
  // Add the second starting workspace to both fresh and existing browser sessions.
  // Reuse a user-created Symphony and leave its records untouched.
  if(!listWorkspaces().some(w=>w.name.toLowerCase()==='symphony')){
    try{createWorkspace('Symphony');}catch{ /* Keep existing workspaces usable if storage is unavailable. */ }
  }
  function selectWorkspace(id){
    if(active.id!==id){
      const item=id===home.id?{name:home.name,data:read(key)}:read(spacePrefix+id);
      if(!item?.data)return false;
      db=item.data;
      storageBase=storageCopy(item.data);storageExists=true;
      active={id,name:item.name};prepareWork();prepareDeliveries();
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
  function log(task, text) {
    task.activity.unshift({text, at:Date.now(), author:'Patrick'});
  }
  const clone = value => JSON.parse(JSON.stringify(value));
  const executionKind = run => (run.kind || 'execution') === 'execution';
  function openRun(id, agent, kind){
    return db.runs.find(r => r.task === id && (!agent || r.agent === agent) &&
      (kind ? (r.kind || 'execution') === kind : !['reply','chat'].includes(r.kind)) && ['queued','running'].includes(r.status));
  }
  function taskRequirements(task){
    return {id:task.id,title:task.title,description:task.description||'',checks:[...(task.checks||[])],project:task.project};
  }
  function captureInput(task, profile, skill, context){
    const selected=db.skills.find(item=>item.id===skill),previous=currentDelivery(task.id);
    return clone({capturedAt:Date.now(),operationRevision:task.operationRevision||0,task:taskRequirements(task),agent:profile,context,
      skill:selected?{...selected,version:selected.version||'Unversioned'}:null,workflow:workflowFor(task.project),
      previousDelivery:previous?{id:previous.id,version:previous.version,summary:previous.summary,review:previous.review}:null});
  }
  function latestDelivery(taskId){
    return (db.deliveries||[]).filter(d=>d.task===taskId).sort((a,b)=>b.version-a.version)[0];
  }
  function currentDelivery(taskId){
    const task=db.tasks.find(t=>t.id===taskId);
    return db.deliveries?.find(d=>d.id===task?.currentDeliveryId&&d.task===taskId);
  }
  function prepareDeliveries(){
    db.deliveries ??= [];
    for(const task of db.tasks){task.activity ??= [];task.operationRevision ??= 0;}
    for(const run of [...db.runs].sort((a,b)=>(a.events?.[0]?.at||0)-(b.events?.[0]?.at||0)||Number(a.id.split('-').pop())-Number(b.id.split('-').pop()))){
      run.kind ??= run.workflowStep==='review'?'review':'execution';
      run.mode ??= 'offline';
      if(!run.inputSnapshot)run.snapshotUnavailable=true;
      if(!run.delivered || !executionKind(run) || db.deliveries.some(d=>d.run===run.id))continue;
      const previous=latestDelivery(run.task);
      const delivery={id:next('DEL',db.deliveries),task:run.task,run:run.id,version:(previous?.version||0)+1,
        supersedes:previous?.id||null,summary:run.artifacts?.find(a=>a.title==='Handoff note')?.body||'Imported delivery record',
        artifacts:clone(run.artifacts||[]),evidence:[],limitations:'Original acceptance evidence was not recorded.',
        inputSnapshot:run.inputSnapshot?clone(run.inputSnapshot):null,snapshotUnavailable:!run.inputSnapshot,
        createdAt:run.events?.at(-1)?.at||Date.now(),review:run.reviewDecision?{decision:run.reviewDecision,note:'Imported decision',reviewer:'Unknown',at:null,destination:null}:null};
      db.deliveries.push(delivery);run.deliveryId=delivery.id;
    }
    for(const task of db.tasks){
      if(!Object.hasOwn(task,'currentDeliveryId'))task.currentDeliveryId=latestDelivery(task.id)?.id||null;
      for(const delivery of db.deliveries.filter(d=>d.task===task.id))
        delivery.disposition=delivery.id===task.currentDeliveryId?'current':(delivery.disposition||'history');
    }
  }
  function reviewEligibility(delivery){
    if(!delivery || !db.deliveries.includes(delivery))return 'Delivery unavailable.';
    const task=db.tasks.find(t=>t.id===delivery.task),run=db.runs.find(r=>r.id===delivery.run);
    if(!task || !run || !executionKind(run) || run.status!=='finished' || !run.delivered)return 'The source run has changed.';
    if(currentDelivery(task.id)?.id!==delivery.id)return 'This is not the current delivery. Select it for review to continue.';
    if(delivery.review || run.reviewDecision)return 'This delivery already has a review decision.';
    if(task.status!=='review')return 'The issue is no longer awaiting review. Select this delivery to resume review.';
    return '';
  }
  function approvalEligibility(delivery){
    const changed=reviewEligibility(delivery);
    if(changed)return changed;
    const task=db.tasks.find(t=>t.id===delivery.task),snapshot=delivery.inputSnapshot;
    if(!snapshot?.task || delivery.snapshotUnavailable)return 'Original requirements are unavailable. Start a new attempt before approval.';
    if(JSON.stringify(snapshot.task)!==JSON.stringify(taskRequirements(task)))return 'Requirements changed after delegation. Start a new attempt before approval.';
    if(!delivery.artifacts.some(a=>a.title?.trim()&&a.body?.trim()))return 'Attach at least one artifact with its contents or reference before approval.';
    if(!snapshot.task.checks.length)return 'Define acceptance criteria and start a new attempt before approval.';
    if(snapshot.task.checks.some((criterion,index)=>!delivery.evidence.some(e=>e.criterion===criterion&&e.index===index&&['supported','not-applicable'].includes(e.status)&&e.evidence?.trim())))
      return 'Evidence is missing for one or more acceptance criteria.';
    return '';
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
  function transitionIssue(task,status,{handoff=true,refreshReview=false,queueRun=true,internal=false,manualReason='',owner,dispatch=false}={}){
    if(!Object.hasOwn(states,status))throw Error('Choose a valid issue status.');
    const previousStatus=task.status,previousOwner=task.owner;
    if(!internal&&status==='done'&&previousStatus!=='done'&&!manualReason.trim())
      throw Error('Explain why this issue is being completed manually.');
    const step=workflowFor(task.project).steps.find(item=>item.status===status);
    const config=db.projectSettings.find(item=>item.project===task.project);
    const target=step?.owner==='Project lead'?config?.lead:step?.owner;
    const changingStep=previousStatus!==status||(status==='review'&&refreshReview);
    const nextOwner=handoff&&changingStep&&target?target:(owner??previousOwner);
    const nextAgent=handlingAgent(nextOwner);
    if(nextOwner!==previousOwner){
      const previousAgent=handlingAgent(previousOwner);
      for(const run of db.runs.filter(r=>r.task===task.id&&r.agent===previousAgent?.name&&['queued','running'].includes(r.status))){
        run.status='cancelled';
        run.events.push({type:'run.cancelled',text:'Handed off to '+nextOwner,at:Date.now()});
      }
      task.owner=nextOwner;
      log(task,'Handed off to '+nextOwner+(step?.instructions?' · '+step.instructions:''));
    }
    if(!internal&&(changingStep||nextOwner!==previousOwner))task.operationRevision=(task.operationRevision||0)+1;
    if(!internal&&status==='done'&&previousStatus!=='done'){
      task.completion={kind:'manual',reason:manualReason.trim(),at:Date.now(),reviewer:'Patrick'};
      log(task,'Completed manually · '+manualReason.trim());
    }
    task.status=status;
    if(previousStatus!==status)log(task,'Moved to '+states[status]+'.');
    if(queueRun&&(dispatch||(handoff&&target&&changingStep))&&nextAgent&&!['backlog','done'].includes(status)){
      const kind=status==='review'?'review':'execution';
      const existing=openRun(task.id,nextAgent.name,kind);
      if(!existing){
        const run=start(task,nextAgent.skills?.[0]||'',nextAgent.name,true,kind);
        if(step){
          run.origin='Workflow · '+workflowFor(task.project).name;
          run.instructions=step.instructions||'';
          run.workflowStep=status;
          run.events.push({type:'workflow.handoff',text:step.instructions||states[status],at:Date.now()});
        }
      }
    }
    save();return task;
  }
  function updateIssue(task, values, {queueRun=false,manualReason=''}={}){
    const created=!task,previousStatus=task?.status||'backlog',previousOwner=task?.owner||'Unassigned';
    const next={title:task?.title||'',description:task?.description||'',checks:task?.checks||[],project:task?.project||'',
      owner:previousOwner,status:previousStatus,priority:task?.priority||'Normal',team:task?.team||'unassigned',due:task?.due||'',tags:task?.tags||[],...values};
    next.title=String(next.title).trim();
    if(!next.title||next.title.length>180)throw Error('Enter an issue title of 1–180 characters.');
    if(next.project&&!db.projects.includes(next.project))throw Error('Choose a project in this workspace.');
    if(!Object.hasOwn(states,next.status))throw Error('Choose a valid issue status.');
    if(!Array.isArray(next.checks)||next.checks.some(c=>typeof c!=='string'))throw Error('Enter acceptance criteria as text.');
    if(!Array.isArray(next.tags))throw Error('Enter labels as text.');
    next.checks=next.checks.map(c=>c.trim()).filter(Boolean);
    const reason=String(manualReason||next.manualReason||next.completionReason||'').trim();
    if(next.status==='done'&&previousStatus!=='done'&&!reason)throw Error('Explain why this issue is being completed manually.');
    if(!task){
      task={id:nextIdForProject(next.project),stage:0,status:'backlog',owner:'Unassigned',activity:[],operationRevision:0};
      db.tasks.push(task);
    }
    const updatedFields={title:next.title,description:String(next.description||''),checks:next.checks,project:next.project,
      priority:next.priority,team:next.team,due:next.due,tags:[...next.tags]};
    const changed=created||Object.entries(updatedFields).some(([key,value])=>JSON.stringify(task[key])!==JSON.stringify(value))||next.owner!==previousOwner||next.status!==previousStatus;
    Object.assign(task,updatedFields);
    if(created&&next.parent)task.parent=next.parent;
    if(changed)task.operationRevision=(task.operationRevision||0)+1;
    if(next.status==='done'&&previousStatus!=='done'){
      task.completion={kind:'manual',reason,at:Date.now(),reviewer:'Patrick'};
      log(task,'Completed manually · '+reason);
    }
    if(changed)log(task,created?'Created issue.':'Updated issue details.');
    const dispatch=created||next.owner!==previousOwner||next.status!==previousStatus;
    transitionIssue(task,next.status,{owner:next.owner,handoff:!created||next.owner==='Unassigned',queueRun,
      dispatch,internal:true});
    const run=queueRun&&dispatch&&!['backlog','done'].includes(task.status)?openRun(task.id,handlingAgent(task.owner)?.name,task.status==='review'?'review':'execution')||null:null;
    save();return {task,run};
  }
  function nextIdForProject(project){
    return next(project==='Workpal'?'WP':project.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,5)||'ISS',db.tasks);
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
  function assignWork(target, values = {}){
    const squad=db.squads.find(item=>item.name===target);
    const agent=db.agents.find(item=>item.name===(squad?.leader||target));
    if(!squad&&!agent)throw Error('Choose an agent or squad in this workspace.');
    const title=typeof values.title==='string'?values.title.trim():'';
    if(!title||title.length>180)throw Error('Enter an issue title of 1–180 characters.');
    const project=values.project??'';
    if(typeof project!=='string'||(project&&!db.projects.includes(project)))throw Error('Choose a project in this workspace.');
    const status=values.status||'todo';
    if(!['backlog','todo'].includes(status))throw Error('New assignments must start in Backlog or To do.');
    const priority=values.priority||'Normal';
    if(!['Low','Normal','High','Urgent'].includes(priority))throw Error('Choose a valid priority.');
    if(values.checks!==undefined&&(!Array.isArray(values.checks)||values.checks.some(check=>typeof check!=='string')))
      throw Error('Enter acceptance criteria as text.');
    const queue=values.queueRun===true&&status==='todo';
    if(queue&&(!agent||(squad&&!squad.members?.includes(agent.name))))
      throw Error('Choose a squad leader who is an agent in this squad before queuing work.');
    const task={id:next(project==='Workpal'?'WP':project.toUpperCase().replace(/[^A-Z0-9]/g,'').slice(0,5)||'ISS',db.tasks),
      title,description:typeof values.description==='string'?values.description.trim():'',
      checks:(values.checks||[]).map(check=>check.trim()).filter(Boolean),project,owner:target,
      status,priority,stage:0,team:'unassigned',due:'',tags:[],activity:[],subscribed:true};
    // Explicit assignment owns this operation. Workflow routing applies to later transitions.
    db.tasks.push(task);
    log(task,'Created issue assigned to '+target+'.');
    const run=queue?start(task,agent.skills?.[0]||'',agent.name,true):null;
    save();return {task,run};
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
        title:auto.name,description:auto.prompt,owner:auto.agent,team:'unassigned',priority:'Normal',status:'todo',stage:0,activity:[],workKind:'summary',
        checks:Array.isArray(auto.checks)&&auto.checks.some(c=>typeof c==='string'&&c.trim())?auto.checks.filter(c=>typeof c==='string').map(c=>c.trim()).filter(Boolean):['Provide the requested summary with sources and open questions.']};
      db.tasks.push(task);log(task,'Created by '+auto.name+' · '+source);
      const run=start(task,agent.skills[0]||'',agent.name,true);
      run.origin=auto.name;
      Object.assign(event,{status:'Issue created',task:task.id,run:run.id});
    }
    auto.history.unshift(event);save();return event;
  }
  function start(task, skill, agent = handlingAgent(task.owner)?.name||task.owner, queued = false, kind = 'execution') {
    if (!db.agents.some(a => a.name === agent)) throw Error('Select an agent to run this issue.');
    if(!['execution','review'].includes(kind))throw Error('Choose a valid run type.');
    const existing = openRun(task.id,agent,kind);
    if(existing){
      if(kind==='execution'&&(existing.skill!==skill||!existing.inputSnapshot?.task||JSON.stringify(existing.inputSnapshot.task)!==JSON.stringify(taskRequirements(task))))
        throw Error('An existing run has different inputs. Cancel or finish it before starting a new attempt.');
      return existing;
    }
    // Opening another attempt does not revoke the current delivery or its review.
    const profile=db.agents.find(a=>a.name===agent);
    const project=db.projectSettings.find(p=>p.project===task.project);
    const squad=db.squads.find(item=>item.name===task.owner);
    const context={project:task.project,description:project?.description||'',resources:clone(project?.resources||[]),
      instructions:profile.instructions||'',skills:[...(profile.skills||[])],runtime:profile.runtimeId||'',harness:profile.runtime,model:profile.model||'Default'};
    if(squad)context.squad=clone({name:squad.name,leader:squad.leader,members:squad.members||[],roles:squad.roles||[],
      instructions:squad.instructions||'',description:squad.description||''});
    const run = {id:next('RUN',db.runs),task:task.id,agent,kind,mode:'offline',stage:queued?task.stage:2,
      status:queued?'queued':'running',skill,context,inputSnapshot:captureInput(task,profile,skill,context),
      events:[{type:queued?'run.queued':'run.started',text:agent+' · Offline record; no agent execution',at:Date.now()}],artifacts:[]};
    if(squad)run.origin='Squad · '+squad.name;
    if(kind==='review')run.reviewingDelivery=currentDelivery(task.id)?.id||null;
    db.runs.unshift(run);
    if(!queued&&kind==='execution'&&task.status!=='done'&&!(currentDelivery(task.id)&&!currentDelivery(task.id).review)){task.status='active';task.stage=2;}
    log(task,agent+(queued?' queued for ':' opened ')+run.id+' · Offline record.');
    save();return run;
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
      const current=openRun(task.id,agent.name)||openRun(task.id,agent.name,'reply');
      if(current){
        current.events.push({type:'comment.received',text,at:Date.now()});
        continue;
      }
      const run={id:next('RUN',db.runs),kind:'reply',mode:'offline',agent:agent.name,task:task.id,status:'queued',
        stage:task.stage||0,skill:agent.skills[0]||'',events:[{type:'comment.received',text,at:Date.now()},{type:'run.queued',text:agent.name,at:Date.now()}],artifacts:[]};
      db.runs.unshift(run);
      log(task,agent.name+' queued · '+run.id);
    }
    save();
  }
  function cancelReviewRuns(taskId, reason){
    for(const review of db.runs.filter(r=>r.task===taskId&&r.kind==='review'&&['queued','running'].includes(r.status))){
      review.status='cancelled';review.events.push({type:'run.cancelled',text:reason,at:Date.now()});
    }
  }
  function changeRun(run, action, note = '', payload = {}) {
    if(!run)throw Error('Run unavailable.');
    if(['approve','return'].includes(action))return decide(run.id,run.stage,action,note,payload);
    const task=db.tasks.find(t=>t.id===run.task);
    const record=(type,text)=>run.events.push({type,text,at:Date.now()});
    if(run.status==='queued'&&['claim','cancel'].includes(action)){
      run.status=action==='claim'?'running':'cancelled';
      if(task&&executionKind(run)&&action==='claim'&&['backlog','todo'].includes(task.status)&&run.inputSnapshot?.operationRevision===(task.operationRevision||0)){
        transitionIssue(task,'active',{handoff:false,internal:true});task.stage=run.stage=2;
      }
      const event=action==='claim'?'run.started':'run.cancelled';
      record(event,run.agent+' · Offline record');
      if(task)log(task,run.id+' · '+event);
      save();return run;
    }
    if(run.status!=='running'||!['finish','deliver','cancel'].includes(action))throw Error('This run has changed. Open the latest run.');
    if(action==='deliver'&&!note.trim())throw Error('Add a delivery summary before continuing.');
    if(action==='deliver'&&executionKind(run)&&!task)throw Error('Select an issue before submitting a delivery.');
    run.status=action==='cancel'?'cancelled':'finished';
    if(action==='deliver'){
      run.delivered=executionKind(run)&&!!task;
      if(run.delivered){
        const previous=latestDelivery(task.id),current=currentDelivery(task.id),checks=run.inputSnapshot?.task?.checks||[];
        const artifacts=(Array.isArray(payload.artifacts)?payload.artifacts:[]).map(a=>({title:String(a.title||''),body:String(a.body||'')}));
        const submitted=Array.isArray(payload.evidence)?payload.evidence:[];
        const evidence=checks.map((criterion,index)=>{
          const item=submitted.find((e,i)=>e.criterion===criterion&&(e.index===index||(e.index===undefined&&i===index)));
          const text=String(item?.evidence||'');
          const status=!text.trim()?'missing':(['supported','missing','unmet','not-applicable'].includes(item?.status)?item.status:'supported');
          return {criterion,index,evidence:text,status};
        });
        const delivery={id:next('DEL',db.deliveries),task:task.id,run:run.id,version:(previous?.version||0)+1,
          supersedes:run.inputSnapshot?.previousDelivery?.id||null,summary:note,artifacts,evidence,limitations:String(payload.limitations||''),
          inputSnapshot:run.inputSnapshot?clone(run.inputSnapshot):null,snapshotUnavailable:!run.inputSnapshot,createdAt:Date.now(),review:null};
        const sameOperation=run.inputSnapshot?.operationRevision===(task.operationRevision||0);
        const replacesCurrent=!current||run.inputSnapshot?.previousDelivery?.id===current.id;
        const eligible=task.status!=='done'&&sameOperation&&replacesCurrent;
        delivery.disposition=eligible?'current':'candidate';
        if(!eligible)delivery.candidateReason=task.status==='done'?'The issue was completed.':!sameOperation?'The issue changed after this run started.':'Another delivery is already selected for review.';
        db.deliveries.push(delivery);run.deliveryId=delivery.id;
        if(eligible){
          if(current)current.disposition=current.review?'history':'candidate';
          task.currentDeliveryId=delivery.id;
        }
        run.artifacts.push({stage:run.stage,title:'Delivery v'+delivery.version,body:note,at:Date.now()});
        record('delivery.recorded',delivery.id+' · v'+delivery.version+' · Manually supplied content');
      }else run.artifacts.push({stage:run.stage,title:run.kind==='review'?'Review note':'Response',body:note,at:Date.now()});
    }
    record(action==='cancel'?'run.cancelled':'run.finished',note||'Offline record closed');
    if(task){
      log(task,run.id+' · '+(note||run.status));
      if(run.delivered&&currentDelivery(task.id)?.run===run.id){
        run.deliveredFrom=task.status;
        // A delivery always needs a human decision, even if a workflow skips review.
        cancelReviewRuns(task.id,'A newer delivery is ready for review.');
        transitionIssue(task,'review',{refreshReview:true,internal:true});
      }
      if(action==='cancel'&&executionKind(run)&&task.status==='active'&&run.inputSnapshot?.operationRevision===(task.operationRevision||0)&&!openRun(task.id,undefined,'execution'))transitionIssue(task,'todo',{handoff:false,internal:true});
    }
    save();return run;
  }
  function selectDelivery(id, reason=''){
    const delivery=db.deliveries.find(d=>d.id===id),task=db.tasks.find(t=>t.id===delivery?.task);
    const run=db.runs.find(r=>r.id===delivery?.run);
    if(!delivery||!task||!run||run.status!=='finished'||!run.delivered)throw Error('Choose a recorded delivery.');
    if(delivery.review)throw Error('This delivery already has a decision. Start a new attempt to revise it.');
    if(!reason.trim())throw Error('Explain why this delivery should become current.');
    const previous=currentDelivery(task.id);
    if(previous&&previous.id!==id)previous.disposition=previous.review?'history':'candidate';
    delivery.disposition='current';delete delivery.candidateReason;
    task.currentDeliveryId=id;task.operationRevision=(task.operationRevision||0)+1;
    (delivery.selections??=[]).push({reason:reason.trim(),reviewer:'Patrick',at:Date.now(),previous:previous?.id||null});
    run.events.push({type:'delivery.selected',text:reason.trim(),at:Date.now()});
    log(task,'Selected '+id+' for review · '+reason.trim());
    cancelReviewRuns(task.id,'Current delivery changed.');
    transitionIssue(task,'review',{refreshReview:true,internal:true});
    save();return delivery;
  }
  function decide(id, expected, choice, reason='', options={}) {
    const run=db.runs.find(r=>r.id===id);
    const delivery=db.deliveries.find(d=>d.run===id);
    if(!run||run.stage!==expected)throw Error('This review has changed. Open the latest issue.');
    if(!['approve','return'].includes(choice))throw Error('Choose a valid decision.');
    const unavailable=choice==='approve'?approvalEligibility(delivery):reviewEligibility(delivery);
    if(unavailable)throw Error(unavailable);
    if(choice==='return'&&!reason.trim())throw Error('Add a review note before requesting changes.');
    if(choice==='approve'&&!options.acknowledged)throw Error('Confirm you inspected the artifacts and acceptance evidence before approval.');
    const task=db.tasks.find(t=>t.id===run.task);
    const step=workflowFor(task.project).steps.find(item=>item.status==='review');
    const destination=choice==='approve'?(step?.next||'done'):(step?.rejected||'active');
    if(!Object.hasOwn(states,destination))throw Error('Choose a valid review destination in the workflow.');
    task.operationRevision=(task.operationRevision||0)+1;
    delivery.review={decision:choice,note:reason,reviewer:'Patrick',at:Date.now(),destination};
    if(choice==='approve'&&destination==='done')task.completion={kind:'delivery',delivery:delivery.id,reason,at:delivery.review.at,reviewer:'Patrick'};
    run.reviewDecision=choice;
    run.events.push({type:choice==='approve'?'issue.approved':'changes.requested',text:delivery.id+' · '+(reason||delivery.summary)+' · Next: '+states[destination],at:Date.now()});
    cancelReviewRuns(task.id,'Human decision recorded for '+delivery.id);
    log(task,delivery.id+' · v'+delivery.version+' · '+(choice==='approve'?'Approved':'Changes requested')+(reason?' · '+reason:''));
    transitionIssue(task,destination,{internal:true});
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
    const snapshot=run?.inputSnapshot,delivery=db.deliveries.find(d=>d.run===runId);
    const lines=execution ? [snapshot?.task?snapshot.task.id+' · '+snapshot.task.title:(run.task||run.title||'Conversation run'),
      'State: '+run.status,'Run type: '+(run.kind||'execution'),'Mode: Offline record; no model or runtime was executed.',
      'Run agent: '+(snapshot?.agent?.name||run.agent||'Unassigned'),'Skill: '+(snapshot?.skill?.name||run.skill||'None')+' · '+(snapshot?.skill?.version||'Version unavailable'),
      '', '## Input snapshot',snapshot?JSON.stringify(snapshot,null,2):'Original requirements were not recorded. Current issue fields are not substituted.',
      '', '## Acceptance criteria',...(snapshot?.task?.checks||[]).map(c=>'- '+c),
      '', '## Decision trail',...run.events.map(ev=>new Date(ev.at).toISOString()+'  '+ev.type+'  '+ev.text),
      '', '## Recorded artifacts',...(run.artifacts||[]).map(a=>(stages[a.stage]||'Record')+' · '+a.title+'\n'+a.body),
      ...(delivery?['','## Delivery '+delivery.id+' · v'+delivery.version,'Source run: '+delivery.run,'Disposition: '+delivery.disposition,'Replaces: '+(delivery.supersedes||'None'),
        delivery.summary,'','### Artifacts',...delivery.artifacts.map(a=>a.title+'\n'+a.body),'','### Acceptance evidence',
        ...delivery.evidence.map(e=>e.criterion+' · '+(e.status||'missing')+'\n'+(e.evidence||'Evidence missing')),'','### Limitations',delivery.limitations||'None recorded',
        '', '### Review',delivery.review?JSON.stringify(delivery.review,null,2):'No decision recorded.',
        '', '### Selection history',...(delivery.selections?.length?delivery.selections.map(selection=>JSON.stringify(selection)):['No explicit selection recorded.']),
        '', '### Current issue audit', 'Current delivery: '+(task?.currentDeliveryId||'None'),
        'Issue status at report generation: '+(task?.status||'Unavailable'),
        'Most recent completion record: '+(task?.completion?JSON.stringify(task.completion):'None')]:[])] :
      [items.length+' tasks · '+summary.active+' active · '+summary.review+' awaiting review · '+summary.done+' completed.','','## Team workload',...Object.entries(teams).filter(([id])=>!team||id===team).map(([id,name])=>name+': '+items.filter(t=>t.team===id).length+' tasks'),'','## Review queue',...items.filter(t=>t.status==='review').map(t=>t.id+' · '+t.title+' — '+t.owner),...(summary.review?[]:['No tasks awaiting review.'])];
    const record={id:next('DOC',db.reports),title,body:lines.join('\n'),at:Date.now()};
    db.reports.unshift(record);save();return record;
  }
  prepareWork();prepareDeliveries();save();
  return {assignWork,updateIssue,currentDelivery,selectDelivery,latestDelivery,reviewEligibility,approvalEligibility,workflowFor,transitionIssue,handlingAgent,triggerAutopilot,get db(){return db;},get workspace(){return active;},listWorkspaces,createWorkspace,selectWorkspace,lastWorkspace,comment,openRun,changeRun,log,states,teams,stages,handoffs,save,count,next,start,decide,report};
})();
