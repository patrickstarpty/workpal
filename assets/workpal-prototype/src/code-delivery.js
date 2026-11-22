globalThis.WorkpalCode = (() => {
  const copy=x=>JSON.parse(JSON.stringify(x));
  const config=(db,project)=>db.projectSettings.find(p=>p.project===project)||{};
  function context(db,project,agent){
    const p=config(db,project),runtime=(db.runtimes||[]).find(r=>r.id===agent?.runtimeId);
    return copy({resources:p.resources||[],deliveryRules:p.deliveryRules||{completion:'workflow'},codePreferences:db.codeSettings||{},machine:runtime||null,resourceMachines:(db.runtimes||[]).filter(m=>(p.resources||[]).some(r=>r.runtimeId===m.id))});
  }
  function blocker(db,task,delivery){
    const p=config(db,task.project),rule=p.deliveryRules?.completion||'workflow';
    const captured=delivery?.inputSnapshot?.context?.deliveryRules?.completion||'workflow';
    if(rule==='workflow'&&captured==='workflow')return '';
    if(delivery?.review?.decision!=='approve')return 'Approve the current delivery before completing this code issue.';
    const requirements={id:task.id,title:task.title,description:task.description||'',checks:[...(task.checks||[])],project:task.project};
    if(JSON.stringify(requirements)!==JSON.stringify(delivery.inputSnapshot?.task))return 'Requirements changed after approval. Submit and approve a new delivery.';
    const prs=(db.pullRequests||[]).filter(p=>p.task===task.id&&p.run===delivery.run);
    if(!prs.length||prs.some(p=>p.state!=='merged'))return 'Record all pull requests for the current delivery as merged first.';
    const resources=delivery.inputSnapshot?.context?.resources||[];
    const repositoryIdentity=url=>{try{return globalThis.WorkpalIntegrations?WorkpalIntegrations.repositoryKey(url):url.replace(/\.git$/, '').toLowerCase();}catch{return null;}};
    const repositoryKeys=resources.filter(r=>r.kind==='repository').map(r=>repositoryIdentity(r.url));
    if(repositoryKeys.some(key=>!key))return 'A repository captured in this run needs a valid URL. Update the project resource and submit a new delivery.';
    if(repositoryKeys.some(key=>!prs.some(p=>repositoryIdentity(p.repository)===key)))return 'Link a merged pull request for each repository captured in this run.';
    return '';
  }
  function saveResource(db,project,data){
    const p=config(db,project);if(!p.project)throw Error('Save the project settings first.');
    const list=p.resources||[];
    if(data.remove==='on'){p.resources=list.filter(r=>r.id!==data.resourceId);return;}
    const r={id:data.resourceId||'RESOURCE-'+crypto.randomUUID(),kind:data.kind,name:data.name.trim()};
    if(!r.name)throw Error('Name this resource.');
    if(r.kind==='repository'){
      let url;
      if(globalThis.WorkpalIntegrations){WorkpalIntegrations.repositoryKey(data.url);url=data.url.trim();}
      else {let parsed;try{parsed=new URL(data.url);}catch{throw Error('Enter an HTTPS repository URL.');}
        if(parsed.protocol!=='https:'||parsed.username||parsed.password)throw Error('Use an HTTPS URL without credentials.');url=parsed.href;}
      if(!data.startingRef.trim())throw Error('Set a starting ref.');
      Object.assign(r,{url:url.replace(/\/$/,''),startingRef:data.startingRef.trim()});
    }else if(r.kind==='folder'){
      if(!(db.runtimes||[]).some(m=>m.id===data.runtimeId)||!data.path.trim())throw Error('Choose the machine that owns this folder and enter its path.');
      if(!['in-place','worktree'].includes(data.mode))throw Error('Choose a folder mode.');
      Object.assign(r,{runtimeId:data.runtimeId,path:data.path.trim(),mode:data.mode});
    }else throw Error('Choose a resource type.');
    p.resources=[...list.filter(x=>x.id!==r.id),r];
  }
  function savePR(db,taskId,data){
    const task=db.tasks.find(t=>t.id===taskId),run=db.runs.find(r=>r.id===data.run&&r.task===taskId);
    if(!task||!run)throw Error('Choose a run belonging to this issue.');
    let url;try{url=new URL(data.url);}catch{throw Error('Enter a GitHub pull request URL.');}
    if(url.origin!=='https://github.com'||!/^\/[^/]+\/[^/]+\/pull\/\d+$/.test(url.pathname)||url.username||url.password)throw Error('Use https://github.com/owner/repository/pull/number.');
    if(!data.source.trim()||!data.target.trim()||!data.sha.trim())throw Error('Record source branch, target branch and commit SHA.');
    if(!/^[a-f0-9]{7,40}$/i.test(data.sha.trim()))throw Error('Enter a 7–40 character commit SHA.');
    for(const [key,values] of Object.entries({state:['open','closed','merged'],ci:['unknown','pending','passed','failed'],review:['unknown','requested','approved','changes-requested'],conflicts:['unknown','clear','conflicting']}))if(!values.includes(data[key]))throw Error('Invalid '+key+' state.');
    const repository=url.origin+url.pathname.split('/').slice(0,3).join('/');
    const prs=db.pullRequests||[],canonical=url.origin+url.pathname,old=prs.find(p=>p.task===taskId&&p.url===canonical);
    if(old&&old.run!==run.id)throw Error('This PR is linked to another attempt. Use a new PR for the new attempt.');
    const record={id:old?.id||'PR-'+crypto.randomUUID(),task:taskId,run:run.id,url:canonical,repository,source:data.source.trim(),target:data.target.trim(),sha:data.sha.trim(),state:data.state,ci:data.ci,review:data.review,conflicts:data.conflicts,provenance:'Manual record',updatedAt:Date.now()};
    record.history=[...(old?.history||[]),{at:record.updatedAt,state:record.state,sha:record.sha,ci:record.ci,review:record.review,conflicts:record.conflicts}];
    db.pullRequests=[...prs.filter(p=>p.id!==record.id),record];return record;
  }
  return {context,blocker,saveResource,savePR};
})();
