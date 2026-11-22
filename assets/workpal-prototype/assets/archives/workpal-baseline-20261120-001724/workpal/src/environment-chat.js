// Authored conversation examples and local request records. No model or environment access.
globalThis.WorkpalEnvironmentChat = (() => {
  'use strict';
  const copy = value => JSON.parse(JSON.stringify(value));
  const fixtureSource = 'environment-chat-v1';
  const profiles = [
    {id:'DEV',label:'Development',agentName:'Architecture partner',role:'Trace development failures across application code, dependencies and configuration.',starters:['Help trace a failing API request in DEV.','Compare this stack trace with the recent code change.','What evidence would distinguish a configuration issue from a code defect?']},
    {id:'UAT',label:'Acceptance',agentName:'Quality partner',role:'Investigate acceptance failures, reproduce defects and identify release-blocking gaps.',starters:['Help investigate a failed acceptance test in UAT.','Compare expected behavior with this reproduction and log excerpt.','What should we verify before retesting this release?']},
    {id:'PRD',label:'Production',agentName:'Engineering partner',role:'Triage production symptoms, assess impact and prepare evidence for an incident decision.',starters:['Help triage a production error in PRD.','Review these errors alongside the latest deployment.','What evidence is needed before choosing mitigation or rollback?']}
  ];
  const profile = id => profiles.find(item => item.id === id);
  const agent = (db,id) => db.agents.find(item => item.name === profile(id)?.agentName);
  const examples = [
    {environment:'DEV',title:'DEV · Search API rejects the new filter',turns:[
      ['user','Search fails in DEV after I added the document-type filter. The same query works when the filter is omitted.\n\nRequest: POST /api/search\nBody: {"query":"release notes","documentType":"pdf"}\nResponse: 400 INVALID_FILTER\nServer log: search.filters: unexpected field "documentType"\n\nThe frontend and search service came from different branches. Where should I start?'],
      ['assistant','The supplied response points to request validation before retrieval starts. A client/server contract mismatch is the leading hypothesis, not a confirmed root cause.\n\nCheck the schema used by the running search service and compare it with the client serializer. Also record the service commit and configuration loaded at startup; the branch in your editor may differ from the process serving the request. Keep the unfiltered request as a control.'],
      ['user','The schema in the service branch accepts filters.document_types as an array. The client serializer sends documentType at the top level. I have not yet checked the running process commit.'],
      ['assistant','That schema difference explains how the provided request could be rejected. Verify that this schema is also loaded by the running process before treating the cause as established.\n\nProposed contract check:\n1. Send the original unfiltered request.\n2. Send {"query":"release notes","filters":{"document_types":["pdf"]}} against the same service instance.\n3. Capture both responses and the service commit.\n\nIf the second request succeeds, align the serializer with the agreed contract and add coverage for omitted, single and multiple document types.'],
      ['user','Please keep the compatibility question open: another client may still use the old field. We need a small follow-up issue before changing the shared endpoint.'],
      ['assistant','The follow-up should establish which request shape each supported client uses, then decide whether to update the serializer alone or introduce a temporary compatibility adapter.\n\nAcceptance evidence to collect: running service commit, both request/response pairs, supported-client inventory and contract test results. The schema mismatch remains a hypothesis until the running instance is verified.']
    ]},
    {environment:'UAT',title:'UAT · Upload retry creates a second document',turns:[
      ['user','The interrupted-upload acceptance case fails in UAT. I uploaded a PDF, disconnected the browser near completion, reconnected and selected Retry. The document list then showed two entries with the same filename.\n\nExpected: resume the existing upload and show one document.\nRelease candidate: tap-rc.18\nBrowser: Chrome\nLog excerpt:\nPOST /uploads → upload_id=up_731\nPOST /uploads/up_731/complete → connection closed\nPOST /uploads → upload_id=up_744\n\nI cannot tell whether the first completion reached the server.'],
      ['assistant','The excerpt shows Retry starting a new upload session. It does not establish whether the first document was committed, so a lost completion response and a non-idempotent retry are both still possible.\n\nCollect the server events for up_731 and up_744, their document IDs and any idempotency key. Then compare the reconnect path with the explicit Cancel-and-upload-again path. Those two actions should have different semantics.'],
      ['user','The browser trace has no idempotency key on either create request. I can provide the client trace, but I do not have the server completion events yet. The acceptance criterion explicitly says that retries must not duplicate documents.'],
      ['assistant','This is an acceptance gap worth tracking for this release candidate. Missing idempotency keys are relevant evidence, but the trace alone does not prove where the duplicate was created.\n\nNext checks:\n• Retrieve completion and document-creation events for both upload IDs.\n• Check whether the client retains the original upload ID after reconnect.\n• Repeat interruption before completion, during completion and after server completion but before the response reaches the browser.\n\nFor each case, record document count, document ID and the visible retry state.'],
      ['user','Keep this linked to the upload-recovery acceptance case. We should retest with the same file and also with a different file that happens to have the same name.'],
      ['assistant','Agreed retest scope: retry the same upload session, deliberately start a new session, and upload different content with an identical filename. Identity should be checked using the session and content rules, not the filename alone.\n\nBefore sign-off, attach the server timeline and demonstrate one document for a retry while preserving deliberate separate uploads. The release owner still needs to review that evidence; this conversation does not mark the acceptance case as passed.']
    ]},
    {environment:'PRD',title:'PRD · Knowledge search errors after deployment',turns:[
      ['user','Support has reported intermittent failures in Knowledge Search in PRD following the latest deployment. I have two request excerpts, but no confirmed impact window yet.\n\nDeployment: tap-web-2026.11.19.2\nGateway: GET /knowledge/search → 502\nRequest ID: req_k9m2\nApplication: retrieval upstream timeout; dependency=search-index\n\nPlease help structure the investigation. Do not change production.'],
      ['assistant','Treat the deployment timing as a lead, not proof of causation. The provided request points to a timeout between the application and search-index; it does not show whether the cause is dependency health, configuration, query behavior or an application regression.\n\nFirst establish the impact window and affected tenant/request patterns. Correlate req_k9m2 across gateway, application and dependency logs, then compare failing and successful requests around the deployment. Production changes remain a human incident-owner decision.'],
      ['user','The release notes mention a new retrieval timeout setting and a changed connection-pool default. I have not yet compared the effective configuration on all instances. Support has only identified knowledge-search failures so far.'],
      ['assistant','Prioritize the effective configuration comparison, including instance revision, timeout value and pool settings. Mixed instance revisions could also explain intermittent symptoms, but that remains unconfirmed.\n\nIn parallel, collect dependency health and pool-exhaustion evidence for the same request window. Keep “only knowledge search affected” as the currently reported scope, not a verified boundary; check adjacent retrieval-dependent paths before narrowing impact.'],
      ['user','Prepare the information the incident owner needs to choose between a configuration correction and rolling back the release. We do not yet have approval for either.'],
      ['assistant','Decision brief to prepare:\n• Confirmed impact window, affected paths and supporting request IDs.\n• Effective settings and revision for each serving instance.\n• Evidence linking the failures to the timeout/pool change, or evidence against that hypothesis.\n• Compatibility of the previous release with current data and dependencies.\n• Proposed change, owner, verification steps and stop conditions.\n\nA configuration correction is a candidate if a verified setting mismatch explains the failures. Rollback is a candidate if a release regression is supported and rollback compatibility is established. Neither action is approved or executed here. Keep the investigation open until the incident owner records a decision and recovery evidence.']
    ]}
  ];

  function initialize(db,workspaceId){
    if(workspaceId !== 'tap' || db.environmentChatVersion >= 1)return false;
    if(!Array.isArray(db.conversations))throw Error('Initialize conversations before environment chats.');
    const now=Date.now();
    if(db.projects.includes('TAP'))for(const [index,example] of examples.entries()){
      const owner=agent(db,example.environment),id='environment-chat-'+example.environment.toLowerCase();
      if(!owner || db.conversations.some(c=>c.id===id || (c.fixtureSource===fixtureSource && c.environment===example.environment)))continue;
      const context={environment:example.environment,project:'TAP',agent:owner.name};
      const messages=example.turns.map(([role,text],i)=>({id:id+'-'+(i+1),role,text,...context,fixtureSource,at:now-(examples.length-index)*3600000+i*180000}));
      db.conversations.push({id,title:example.title,...context,messages,draft:'',fixtureSource});
    }
    db.environmentChatVersion=1;
    return true;
  }

  function snapshot(db,conversation){
    const environment=profile(conversation?.environment);
    if(!environment)throw Error('Choose a valid environment.');
    const project=conversation.project;
    if(!project || !db.projects.includes(project))throw Error('Choose a project in this workspace.');
    const owner=db.agents.find(item=>item.name===(conversation.agent || environment.agentName));
    if(!owner)throw Error('Choose an available agent for this environment.');
    return copy({environment:environment.id,environmentLabel:environment.label,project,
      projectSettings:db.projectSettings?.find(item=>item.project===project)||{project},agent:owner,
      conversation:{id:conversation.id||'',title:conversation.title||'New chat',fixtureSource:conversation.fixtureSource||null,messages:conversation.messages||[]},capturedAt:Date.now()});
  }

  function requireConversation(db,c){
    if(!c?.id || !db.conversations?.some(item=>item===c))throw Error('Open a conversation in this workspace.');
  }

  function queue(db,c,text){
    requireConversation(db,c);
    if(typeof text!=='string' || !text.trim())throw Error('Enter a message before sending.');
    const context=snapshot(db,c),prompt=text.trim(),at=Date.now();
    const seq=Math.max(0,...db.runs.map(run=>/^RUN-\d+$/.test(run.id)?Number(run.id.slice(4)):0))+1;
    const run={id:'RUN-'+String(seq).padStart(3,'0'),kind:'chat',mode:'offline',conversation:c.id,task:null,
      agent:context.agent.name,title:prompt.slice(0,80),status:'queued',stage:0,skill:context.agent.skills?.[0]||'',
      artifacts:[],context,events:[{type:'run.queued',text:prompt,at}]};
    const message={id:crypto.randomUUID(),role:'user',text:prompt,at,queued:true,run:run.id,
      agent:context.agent.name,environment:context.environment,project:context.project};
    // The request is part of the captured history, independent from the editable conversation.
    run.context.conversation.messages.push(copy(message));
    db.runs.unshift(run);
    if(!c.messages.length)c.title=prompt.slice(0,64);
    c.messages.push(message);c.draft='';
    return run;
  }

  function createIssue(studio,c){
    const db=studio.db;
    requireConversation(db,c);
    if(c.issueId){
      const linked=db.tasks.find(task=>task.id===c.issueId);
      if(linked)return linked;
      throw Error('The linked issue is unavailable. Restore it before creating another.');
    }
    const context=snapshot(db,c);
    if(!c.messages.some(message=>message.role==='user' && message.text?.trim()))throw Error('Add the problem to the conversation before creating an issue.');
    const history=c.messages.map(message=>'['+(message.environment||context.environment)+' · '+(message.role==='user'?'User':message.agent||context.agent.name)+']\n'+(message.text||'')).join('\n\n');
    const description=['Environment: '+context.environment+' · '+context.environmentLabel,'Project: '+context.project,'Agent: '+context.agent.name,
      'Conversation: '+c.title+' ('+c.id+')',
      '', 'Conversation history',history].join('\n');
    const {task}=studio.assignWork(context.agent.name,{title:('['+context.environment+'] '+(c.title||'Investigate environment issue')).slice(0,180),
      project:context.project,description,status:'backlog',queueRun:false,checks:['Record the reproduction or incident evidence and its source.','Distinguish confirmed findings from hypotheses.','Have the responsible owner review the outcome and next action.']});
    task.tags=[...new Set([...(task.tags||[]),context.environment,'Investigation'])];
    task.environment=context.environment;task.conversationId=c.id;task.conversationSnapshot=context;
    c.issueId=task.id;
    studio.save();
    return task;
  }
  return {profiles,initialize,profile,agent,snapshot,queue,createIssue};
})();
