// Authored, linked review data. No execution, repository access or measured usage.
globalThis.WorkpalWorkspaceFixtures = (db, now=Date.now()) => {
  if(!db.workpalSkillLibraryVersion){
    const catalog=[
      ['citation-audit','Citation Audit',3,'Check quoted passages, document permissions and deep-link anchors.'],
      ['upload-recovery','Upload Recovery',2,'Implement resumable uploads with deduplication and safe cancellation.'],
      ['retrieval-tuning','Retrieval Tuning',2,'Tune title boosts and access filters using representative query cases.'],
      ['conversation-state','Conversation State',2,'Preserve drafts, pagination and navigation state across conversations.'],
      ['repository-onboarding','Repository Onboarding',1,'Map branches, packages and webhook permissions before connecting a repository.'],
      ['pipeline-triage','Pipeline Triage',3,'Separate flaky tests, runner failures and reproducible build errors.'],
      ['access-review','Access Review',3,'Review permission changes, credential expiry and least-privilege boundaries.'],
      ['release-readiness','Release Readiness',4,'Assemble rollback steps, dependency gates and the approved commit scope.'],
      ['skill-discovery','Skill Discovery',0,'Find reusable skills by task intent and assess their source and scope.'],
      ['skill-versioning','Skill Versioning',2,'Compare releases, pin versions and prepare rollback-compatible updates.'],
      ['skill-review','Skill Review',3,'Review skill instructions, attribution and installation commands before publication.'],
      ['collection-governance','Collection Governance',1,'Define collection ownership, visibility and team access rules.'],
      ['ticket-refinement','Ticket Refinement',0,'Turn a product request into scoped tickets and observable acceptance criteria.'],
      ['dependency-mapping','Dependency Mapping',1,'Identify release blockers and record cross-ticket dependencies.'],
      ['commit-attribution','Commit Attribution',2,'Link commits to tickets and record Workpal co-authorship consistently.'],
      ['review-handoff','Review Handoff',3,'Package change references, acceptance evidence and unresolved questions.'],
      ['rollback-planning','Rollback Planning',4,'Define rollback triggers, data compatibility and recovery checkpoints.'],
      ['incident-learning','Incident Learning',5,'Extract reusable practices from failures and human interventions.']
    ];
    for(const [name,label,stage,description] of catalog){const id='workpal-'+name;if(!db.skills.some(s=>s.id===id))db.skills.push({id,name:label,author:'Workpal',stage,description,version:'1.0.0',local:true,source:'',fixtureSource:'workpal-library'});}
    for(const agent of db.agents){const stages=agent.name.includes('Product')?[0,5]:agent.name.includes('Architecture')?[1]:agent.name.includes('Quality')?[3]:[2,4];for(const skill of db.skills.filter(s=>s.local&&stages.includes(s.stage)))if(!agent.skills.includes(skill.id))agent.skills.push(skill.id);}
    db.workpalSkillLibraryVersion=1;
  }
  const linkSkills=()=>{
    const ids=['citation-audit','upload-recovery','retrieval-tuning','conversation-state','repository-onboarding','pipeline-triage','access-review','release-readiness','skill-discovery','skill-versioning','skill-review','collection-governance'];
    const parents=db.tasks.filter(t=>t.id.startsWith('INIT-'));
    for(const run of db.runs.filter(r=>r.fixtureSource==='linked-v2'&&!r.skillLibraryLinked)){
      const task=db.tasks.find(t=>t.id===run.task),index=parents.findIndex(p=>p.id===task?.parent);if(index<0)continue;
      const skill=db.skills.find(s=>s.id==='workpal-'+ids[index%ids.length]);if(!skill)continue;
      run.skill=skill.id;run.skillLibraryLinked=true;
      const agent=db.agents.find(a=>a.name===run.agent);if(agent&&!agent.skills.includes(skill.id))agent.skills.push(skill.id);
      if(run.inputSnapshot)run.inputSnapshot.skill=JSON.parse(JSON.stringify(skill));
      const delivery=db.deliveries.find(d=>d.run===run.id);if(delivery?.inputSnapshot)delivery.inputSnapshot.skill=JSON.parse(JSON.stringify(skill));
    }
  };
  if(db.linkedFixtureVersion===2){linkSkills();return false;}
  // Upgrade untouched v1 chains; preserve any chain with local edits or replies.
  if(db.linkedFixtureVersion===1){
    const removable=new Set(db.tasks.filter(t=>t.fixtureSource==='linked-v1'&&t.operationRevision===0&&t.activity.length===2&&t.activity.every(e=>!e.replies?.length)&&!db.runs.some(r=>r.task===t.id&&(!r.fixtureSource||r.events.length>2))&&!db.deliveries.some(d=>d.task===t.id&&(d.selections?.length||d.review?.note&&d.review.note!=='Scope accepted for the release checklist.'))).map(t=>t.id));
    const parents=new Set(db.tasks.filter(t=>t.id.startsWith('INIT-')&&db.tasks.some(c=>c.parent===t.id)&&db.tasks.filter(c=>c.parent===t.id).every(c=>removable.has(c.id))).map(t=>t.id));
    db.tasks=db.tasks.filter(t=>!removable.has(t.id)&&!parents.has(t.id));
    db.runs=db.runs.filter(r=>!removable.has(r.task));db.deliveries=db.deliveries.filter(d=>!removable.has(d.task));
    db.reports=db.reports.filter(r=>r.fixtureSource!=='linked-v1');
    if(db.contributionCommits?.every(c=>c.fixtureSource==='linked-v1')){db.contributionCommits=db.contributionCommits.filter(c=>!removable.has(c.task));db.mergeFixtureCommits=true;}
  }
  const copy=value=>JSON.parse(JSON.stringify(value));
  const day=86400000, commits=[], usage=[];
  const add=(prefix,rows)=>prefix+'-'+String(Math.max(999,...rows.map(r=>Number(r.id?.split('-').pop())||0))+1).padStart(4,'0');
  const projects=[['TAP','Knowledge workspace',['Citation navigation','Document ingestion','Search relevance','Conversation history']],['Developer Platform','Developer experience',['Repository onboarding','Build pipelines','Environment access','Release controls']],['Skill Hub','Reusable skills',['Skill discovery','Version management','Quality review','Team collections']]];
  let randomState=719231;
  const random=()=>{randomState=(Math.imul(randomState,1664525)+1013904223)>>>0;return randomState/4294967296;};
  const pick=items=>items[Math.floor(random()*items.length)];
  const hex=()=>Array.from({length:40},()=>Math.floor(random()*16).toString(16)).join('');
  const scenarios=[
    ['Keep page anchors stable after PDF re-indexing','Scroll to the quoted paragraph from a citation','Show deleted-source warnings in older answers','Restore focus after closing the source drawer','Fix citation numbers after streaming reconnect','Support two sources for the same claim','Retain source access checks when sharing a conversation'],
    ['Resume multipart uploads after a network drop','Skip duplicate files using content hashes','Move scanned PDFs to the OCR queue','Clean up abandoned upload sessions','Retry parsing without creating a second document','Show actionable errors for password-protected PDFs','Preserve filenames containing emoji','Limit concurrent uploads per workspace','Cancel queued OCR jobs when a document is deleted'],
    ['Boost exact document-title matches','Exclude archived documents from retrieval','Fix stale permission filters in cached results','Tune score thresholds for short queries','Keep selected filters after opening a result','Measure query coverage for mixed-language documents'],
    ['Restore drafts after switching conversations','Paginate long conversation histories','Rename threads without losing selection','Remove deleted threads from browser history','Export answers with their source references'],
    ['Detect the default branch during repository setup','Reject repositories outside the approved organization','Recover from an expired installation token','Index monorepo package boundaries','Avoid duplicate webhook subscriptions','Show repository permission changes'],
    ['Cancel superseded branch builds','Reuse dependency caches across pull requests','Surface the first failing test in build summaries','Retry interrupted artifact uploads','Separate flaky tests from deterministic failures','Keep build logs after a runner disconnect','Limit parallel jobs per repository','Link build artifacts to the originating commit'],
    ['Expire temporary environment access after review','Require an owner for production credentials','Remove stale runtime registrations','Audit changes to environment permissions','Block deployments when approval has expired','Rotate the shared staging credential'],
    ['Generate release notes from merged tickets','Require rollback instructions before approval','Stop promotion when a dependency is blocked','Keep release approvals attached to the reviewed SHA','Show partial rollout progress','Recover a cancelled release draft','Link hotfixes to the previous release'],
    ['Match skill search against descriptions','Keep filters when returning from a skill detail','Rank exact skill names above keyword matches','Show the source repository on result cards','Handle an unavailable upstream skill','Deduplicate skills published from repository forks'],
    ['Pin installed skills to a version','Show breaking changes before updating','Retain the previous version for rollback','Detect removed files in an upstream release','Prevent concurrent updates to the same skill','Record who approved a version change','Compare permissions between skill versions','Migrate legacy unversioned installations'],
    ['Require an example input for skill submissions','Return submissions with missing source attribution','Keep reviewer comments across revisions','Flag installation commands for manual inspection','Block publishing until review is resolved'],
    ['Share a collection with a team','Keep private skills out of public collections','Reorder skills with keyboard controls','Transfer collection ownership','Explain why a shared skill is unavailable','Restore accidentally removed collection items','Remove access after a member leaves']
  ];
  for(const [project,description,areas] of projects){
    if(!db.projects.includes(project))db.projects.push(project);
    if(!db.projectSettings.some(p=>p.project===project))db.projectSettings.push({project,lead:'Patrick',description,reviewer:'Patrick',due:''});
    const squad=project+' delivery';
    if(!db.squads.some(s=>s.name===squad))db.squads.push({name:squad,leader:'Engineering partner',members:[...db.agents.map(a=>a.name),'Patrick'],description:'Coordinate '+description.toLowerCase()+'.',instructions:'Review dependencies, implementation and acceptance evidence before release.'});
    for(const [areaIndex,area] of areas.entries()){
      const parent={id:add('INIT',db.tasks),project,title:area+' release',description:'Coordinate '+area.toLowerCase()+' across definition, implementation and review.',checks:['Review linked issues before release'],status:'active',team:'product',owner:squad,priority:'High',stage:2,tags:['Release'],activity:[],subscribed:true};
      db.tasks.push(parent);
      for(const [index,title] of scenarios[projects.findIndex(p=>p[0]===project)*4+areaIndex].entries()){
        const serial=projects.findIndex(p=>p[0]===project)*36+areaIndex*9+index;
        const status=pick(project==='TAP'?['done','done','done','review','active','active','blocked','todo']:project==='Skill Hub'?['done','review','active','todo','backlog','backlog']:['done','done','review','active','blocked','todo']);
        const human=random()<0.27;
        const agent=db.agents.find(a=>a.name===(index===1?'Architecture partner':index===4?'Quality partner':'Engineering partner'))||db.agents[0];
        const at=now-(status==='done'?3+Math.floor(random()*39):1+Math.floor(random()*8))*day-Math.floor(random()*7)*3600000;
        const task={id:add(project==='TAP'?'TAP':project==='Skill Hub'?'SKILL':'DEV',db.tasks),project,parent:parent.id,title,description:title+'. This is part of the '+area.toLowerCase()+' rollout. '+pick(['Existing sessions must retain their state during the change.','Apply the same access rules to direct links and list views.','Keep the previous behavior available until the rollout is approved.','Handle interrupted requests without duplicating records.']),checks:[title+' for an existing workspace',pick(['Retry after a network interruption without creating duplicates','Reject access after the user loses team membership','Preserve the selection when navigating back','Show a useful empty state for a new workspace'])],status,team:index===0||index===8?'product':index===4?'quality':'engineering',owner:human?'Patrick':agent.name,priority:index===5?'Urgent':index%3===0?'High':'Normal',stage:status==='done'?5:status==='review'?3:2,tags:[area,index===5?'Dependency':'Release'],due:new Date(now+(index-3)*day).toISOString().slice(0,10),subscribed:index%3===0,operationRevision:0,activity:[],fixtureSource:'linked-v2'};
        db.tasks.push(task);
        task.activity.push({id:'discussion-'+task.id,kind:'comment',author:'Patrick',text:status==='blocked'?pick(['The staging credential has expired; implementation is ready but verification is blocked.','Waiting for the upstream permission schema to settle before wiring this in.','The regression case still reproduces after reconnect. Keep the release gate closed.']):pick(['Please split the migration from the UI change so we can roll back independently.','The happy path looks covered. Include a case with an existing workspace before review.','Keep the current API shape for this release; the client update will follow.','The scope is smaller than the original estimate. Leave bulk operations for the next release.']),at:at+600000,replies:[],resolved:status==='done'});
        let run;
        if(!human&&status!=='backlog'){
          const context={project,description,resources:[],instructions:'Keep changes scoped to the linked issue.',skills:agent.skills||[],runtime:agent.runtimeId||'',harness:agent.runtime,model:agent.model||'Default'};
          run={id:add('RUN',db.runs),task:task.id,agent:agent.name,kind:'execution',mode:'offline',stage:task.stage,status:['done','review'].includes(status)?'finished':status==='todo'?'queued':'running',skill:agent.skills?.[0]||'',context,inputSnapshot:{capturedAt:at,operationRevision:0,task:{id:task.id,title:task.title,description:task.description,checks:copy(task.checks),project},agent:copy(agent),context:copy(context),skill:copy(db.skills.find(s=>s.id===agent.skills?.[0])||null),previousDelivery:null},events:[{type:'run.started',text:task.title,at}],artifacts:[],fixtureSource:'linked-v2'};
          db.runs.unshift(run);
        }
        const linked=[];
        if(!['backlog','todo','blocked'].includes(status))for(let c=0;c<(human?1+serial%3:1+serial%8);c++){
          const assisted=!human&&c!==0;
          const commit={repository:'workpal/'+project.toLowerCase().replaceAll(' ','-'),sha:hex(),message:task.id+' '+(c===0?title:pick(['fix: preserve existing records during retry','test: cover missing permissions','fix: address review feedback on state handling','refactor: extract shared validation','test: add regression coverage for reconnect','fix: avoid duplicate updates after navigation','chore: remove obsolete fallback']))+(assisted?'\n\nCo-authored-by: Workpal <workpal@users.noreply.github.com>':''),at:at+(c+1)* (31+serial%67)*60000,additions:Math.floor(2+random()**3*640),deletions:Math.floor(random()**2*210),task:task.id,run:assisted?run?.id:null,fixtureSource:'linked-v2'};
          commits.push(commit);linked.push(commit);
        }
        if(run&&run.status==='finished'){
          const summary=title+'. '+pick(['Includes the recovery path and a migration note.','The compatibility fallback remains enabled for this release.','Ready for review; rollout remains gated on the parent release.']);
          const artifacts=[{title:'Change manifest',body:linked.map(c=>c.repository+' · '+c.sha.slice(0,12)+' · '+c.message.split('\n')[0]).join('\n'),stage:3,at:at+14*3600000}];
          const delivery={id:add('DEL',db.deliveries),task:task.id,run:run.id,version:1,supersedes:null,summary,artifacts,evidence:task.checks.map((criterion,index)=>({criterion,index,status:'supported',evidence:'Review scope: '+criterion+'. Change references: '+linked.map(c=>c.sha.slice(0,12)).join(', ')})),limitations:'Repository checks and release approval must be verified before shipping.',inputSnapshot:copy(run.inputSnapshot),createdAt:at+15*3600000,disposition:'current',review:status==='done'?{decision:'approve',reviewer:'Patrick',note:'Scope accepted for the release checklist.',destination:'done',at:at+16*3600000}:null,fixtureSource:'linked-v2'};
          db.deliveries.push(delivery);task.currentDeliveryId=delivery.id;run.delivered=true;run.deliveryId=delivery.id;run.artifacts=copy(artifacts);run.events.push({type:'delivery.recorded',text:delivery.id+' · '+summary,at:delivery.createdAt});
          if(delivery.review){run.reviewDecision='approve';task.completion={kind:'delivery',delivery:delivery.id,reason:delivery.review.note,at:delivery.review.at,reviewer:'Patrick'};}
          usage.push({id:'usage-'+run.id,run:run.id,task:task.id,at:delivery.createdAt,agent:run.agent,team:task.team,project,input:Math.floor(4000+random()**2*95000),output:Math.floor(700+random()*12000),cacheRead:Math.floor(random()*42000),cacheWrite:Math.floor(random()*9000),cost:Number((0.03+random()**2*1.8).toFixed(4)),seconds:Math.floor(80+random()**2*2600),status:'completed',fixtureSource:'linked-v2'});
        }else if(status==='done')task.completion={kind:'manual',reason:'Requirements accepted for '+parent.id,at:at+16*3600000,reviewer:'Patrick'};
        task.activity.unshift({author:'Patrick',text:task.id+' · '+status+(run?' · '+run.id:'')+(task.currentDeliveryId?' · '+task.currentDeliveryId:''),at:at+16*3600000});
      }
      const children=db.tasks.filter(t=>t.parent===parent.id);
      db.reports.push({id:add('DOC',db.reports),title:area+' delivery brief',at:now-3600000,body:project+' / '+parent.id+'\n\n'+children.map(t=>t.id+' · '+t.title+' · '+t.status+(t.currentDeliveryId?' · '+t.currentDeliveryId:'')).join('\n')+'\n\nRelease dependency: '+(children.filter(t=>t.status==='blocked').map(t=>t.id+' — '+t.activity.find(e=>e.kind==='comment').text).join('\n')||'No open blocking dependency recorded.'),fixtureSource:'linked-v2'});
    }
  }
  const generated=db.tasks.filter(t=>t.fixtureSource==='linked-v2');
  for(const task of generated.filter(t=>t.status==='blocked')){
    const dependency=generated.find(t=>t.project===task.project&&['active','review'].includes(t.status)&&t.id!==task.id);
    if(dependency){task.dependsOn=[dependency.id];task.description+=' Blocked by '+dependency.id+': '+dependency.title+'.';task.activity.unshift({author:'Patrick',text:'Dependency: '+dependency.id+' must clear review before this can proceed.',at:now-2*3600000});}
  }
  // Returned first attempts keep their own manifests and requirements; the current
  // attempt remains actionable through the normal delivery review flow.
  for(const [index,delivery] of db.deliveries.filter(d=>d.fixtureSource==='linked-v2').entries()){
    if(index%4!==1)continue;
    const run=db.runs.find(r=>r.id===delivery.run),task=db.tasks.find(t=>t.id===delivery.task);
    const previousRun=copy(run);previousRun.id=add('RUN',db.runs);previousRun.events=previousRun.events.map(e=>({...e,at:e.at-2*day}));
    const previous=copy(delivery);previous.id=add('DEL',db.deliveries);previous.run=previousRun.id;previous.disposition='history';previous.createdAt-=2*day;
    previous.artifacts=[{title:'Initial review scope',body:task.title+' — recovery behavior still needs revision.',stage:3,at:previous.createdAt}];
    previous.evidence=previous.evidence.map((e,i)=>({...e,status:i===0?'supported':'unmet',evidence:i===0?'Initial implementation included in review scope.':'Recovery leaves stale state after reconnect.'}));
    previous.review={decision:'return',reviewer:'Patrick',note:'The reconnect path leaves stale state. Add a regression case before resubmitting.',destination:'active',at:previous.createdAt+3600000};
    previousRun.deliveryId=previous.id;previousRun.reviewDecision='return';previousRun.artifacts=copy(previous.artifacts);previousRun.events=[{type:'run.started',text:task.title,at:previous.createdAt-3600000},{type:'changes.requested',text:previous.review.note,at:previous.review.at}];
    previousRun.inputSnapshot.capturedAt=previous.createdAt-3600000;previous.inputSnapshot=copy(previousRun.inputSnapshot);
    db.runs.push(previousRun);db.deliveries.push(previous);
    delivery.version=2;delivery.supersedes=previous.id;run.inputSnapshot.previousDelivery={id:previous.id,version:1,summary:previous.summary,review:copy(previous.review)};delivery.inputSnapshot=copy(run.inputSnapshot);
    task.activity.push({id:'revision-'+task.id,kind:'comment',author:'Patrick',text:previous.review.note,at:previous.review.at,resolved:true,replies:[{id:'revision-reply-'+task.id,author:'Patrick',text:'Updated in '+delivery.id+'. Please check the reconnect regression case again.',at:delivery.createdAt}]});
    const record=usage.find(u=>u.run===run.id);if(record)usage.push({...record,id:'usage-'+previousRun.id,run:previousRun.id,at:previous.createdAt,input:Math.round(record.input*.63),output:Math.round(record.output*.72),seconds:Math.round(record.seconds*.8),cost:Number((record.cost*.7).toFixed(4))});
  }
  // Do not replace imports or local review notes. Only replace legacy authored usage.
  if(db.mergeFixtureCommits){db.contributionCommits.push(...commits);delete db.mergeFixtureCommits;}else if(!Object.hasOwn(db,'contributionCommits'))db.contributionCommits=commits;
  if(!db.analyticsHistory||db.analyticsHistory.source==='fixture')db.analyticsHistory={version:1,source:'fixture',asOf:now,records:[...(db.analyticsHistory?.records||[]).filter(r=>r.fixtureSource==='linked-v1'&&db.runs.some(run=>run.id===r.run)),...usage]};
  db.linkedFixtureVersion=2;linkSkills();
  return true;
};
