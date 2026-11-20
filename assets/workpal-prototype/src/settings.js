// Settings follow Multica's Code and Connected apps structure.
// A local setup is never an authenticated provider connection.
globalThis.WorkpalSettings = (() => {
  function create({getDB,esc,icon,btn,tool,form,field,input,select,scoped,appearance,codeSettings}) {
    const model=WorkpalIntegrations,db=()=>getDB();
    const tab=value=>['general','code','apps'].includes(value)?value:'general';
    const names={general:'General',code:'Code',apps:'Connected apps'};
    const link=(key,label=names[key])=>'<a class="nav" href="#'+scoped('settings?tab='+key)+'">'+icon(key==='code'?'code':key==='apps'?'layers':'settings')+'<span>'+label+'</span></a>';
    function navigation(value){
      const current=tab(value);
      const item=key=>link(key).replace('class="nav"','class="nav '+(key===current?'active':'')+'"'+(key===current?' aria-current="page"':''));
      return '<nav aria-label="Settings navigation"><div class="rail-group-label"><small>Workspace</small></div>'+item('general')+'<div class="rail-group-label settings-group-label"><small>Connections</small></div>'+item('code')+item('apps')+'</nav>';
    }
    const status=()=>'<span class="integration-status">Authorization required</span>';
    const section=(title,description,body,action='')=>'<section class="settings-section"><header><div><h3>'+title+'</h3>'+(description?'<p>'+description+'</p>':'')+'</div>'+action+'</header>'+body+'</section>';
    function accountRow(a){
      const name=a.provider==='jira'?'Jira':'GitHub';
      return '<div class="integration-account"><span class="integration-icon">'+icon(a.provider==='jira'?'tasks':'code')+'</span><div class="integration-account-copy"><strong>'+name+' <span>'+esc(a.name)+'</span></strong>'+status()+'<small>'+(a.scope==='team'?'Team account':'My account')+' · Not connected</small></div><div class="integration-account-actions">'+tool('Edit setup','integrationSetup',a.id)+tool('Remove setup','integrationRemove',a.id)+'</div></div>';
    }
    function repositories(){
      const repos=model.repositories(db());
      const menu='<details class="repository-add-menu"><summary class="btn">'+icon('plus')+'Add repository'+icon('chevronDown')+'</summary><div class="repository-menu" role="group" aria-label="Add repository options">'+tool('Connect GitHub','integrationSetup','github~team')+tool('Enter a URL…','repositoryEditor')+'</div></details>';
      const rows=repos.map(r=>'<div class="repository-row"><span class="integration-icon">'+icon('code')+'</span><div class="repository-copy"><code>'+esc(r.url)+'</code>'+(r.description?'<p>'+esc(r.description)+'</p>':'')+'</div><details class="repository-actions"><summary class="btn icon-only" aria-label="Repository actions" title="Repository actions">'+icon('more')+'</summary><div class="repository-menu">'+tool('Edit','repositoryEditor',r.id)+tool('Delete repository','repositoryRemove',r.id)+'</div></details></div>').join('');
      return section('Repositories','Repositories available to this workspace.',rows||'<div class="settings-empty">'+icon('code')+'<strong>No repositories yet</strong><p>Add a repository URL to make it available in project resources.</p></div>',menu);
    }
    function code(){
      const accounts=model.setups(db()).filter(a=>a.provider==='github');
      return section('Code hosting','Connect your code host to link pull requests and track development.',
        '<div class="integration-provider"><span class="integration-icon">'+icon('code')+'</span><div class="grow"><strong>GitHub</strong><p>Not connected</p></div>'+tool('Connect GitHub','integrationSetup','github~team')+'</div>'+accounts.map(accountRow).join(''))+repositories()+
        section('Pull requests &amp; issues','Manage how pull requests appear alongside your issues.',preferences());
    }
    function preferences(){
      const c=db().codeSettings||{};
      const toggle=(name,title,description,checked)=>'<label class="settings-toggle"><span><strong>'+title+'</strong><small>'+description+'</small></span><input type="checkbox" name="'+name+'" role="switch" '+(checked?'checked':'')+'></label>';
      return form('integrationPreferences',toggle('prSidebar','Pull Request sidebar','Show linked pull requests in issue details.',c.prSidebar!==false)+
        toggle('association','Auto-link issues and PRs','Match issue identifiers in branch names and PR titles when connected.',c.association==='issue')+
        toggle('coAuthor','Co-authored-by trailer','Include Workpal attribution in agent commit preferences.',c.coAuthor!==false)+
        '<div class="settings-select-row">'+field('After PRs merge, move the issue to',select('afterMerge',{keep:"Don’t change",complete:'Done'},c.afterMerge||'keep'))+'<small>Done applies to eligible issues after all required merges are recorded.</small></div>'+field('Status reading',select('reading',{off:'Off',requested:'Read PRs, checks and reviews when connected'},c.reading||'off')),'Save preferences');
    }
    function apps(){
      return ['team','personal'].map(scope=>{
        const accounts=model.setups(db()).filter(a=>a.provider==='jira'&&a.scope===scope);
        return section(scope==='team'?'Team accounts':'My accounts',scope==='team'?'Shared app accounts for this workspace.':'App accounts for your own work.',accounts.map(accountRow).join('')||'<div class="settings-empty"><span class="integration-icon">'+icon('layers')+'</span><strong>No '+(scope==='team'?'team':'personal')+' accounts</strong><p>Connect Jira to bring your tools into Workpal.</p></div>',tool(scope==='team'?'Connect team account':'Connect my account','appCatalog',scope));
      }).join('');
    }
    function general(){
      return appearance()+section('Connections','Manage code repositories and app accounts.','<div class="settings-connections">'+link('code')+link('apps')+'</div>')+codeSettings()+section('Workspace','',
        '<dl class="properties"><dt>Workspace</dt><dd>'+esc(WorkpalStudio.workspace.name)+'</dd><dt>Owner</dt><dd>Patrick</dd><dt>Language</dt><dd>English</dd><dt>Storage</dt><dd>This browser</dd></dl><div class="actions">'+tool('Workflows','workflows')+tool('Workspace notes','notes')+'</div>');
    }
    function page(value){
      const current=tab(value);
      return '<div class="settings-content"><header class="settings-heading"><h2>'+names[current]+'</h2><p>'+({general:'Manage your workspace and preferences.',code:'Manage your code hosting, repositories and pull requests.',apps:'Connect the apps your team works with.'})[current]+'</p></header><nav class="settings-mobile-nav" aria-label="Settings sections">'+Object.keys(names).map(key=>'<a '+(key===current?'aria-current="page"':'')+' href="#'+scoped('settings?tab='+key)+'">'+names[key]+'</a>').join('')+'</nav>'+({general,code,apps})[current]()+'</div>';
    }
    function editor(type,arg=''){
      const cancel=btn('Cancel','dismiss');
      if(type==='repositoryEditor'){
        const r=model.repositories(db()).find(r=>r.id===arg)||{};
        return form(type,field('Repository URL','<input name="url" value="'+esc(r.url||'')+'" required maxlength="2048" placeholder="https://github.com/owner/repository" autocomplete="off" spellcheck="false"><small>HTTPS or SSH clone URL</small>')+field('Description (optional)','<textarea name="description" rows="3" maxlength="1000" placeholder="What is this repository for?">'+esc(r.description||'')+'</textarea>')+cancel,'Save repository',arg);
      }
      if(type==='repositoryRemove'){
        const r=model.repositories(db()).find(r=>r.id===arg);if(!r)return '<p>Repository unavailable.</p>';
        return form(type,'<p>Delete <strong>'+esc(r.url)+'</strong> from this workspace’s repository list?</p><p>Existing project resources and issue history are kept.</p>'+cancel,'Delete repository',arg);
      }
      if(type==='appCatalog')return '<label>Search apps<input name="appSearch" placeholder="Search apps…" autocomplete="off"></label><div class="app-catalog"><div class="app-catalog-row" data-app-name="jira atlassian"><span class="integration-icon">'+icon('tasks')+'</span><div class="grow"><strong>Jira</strong><p>Track issues and manage projects with Jira.</p></div>'+tool('Connect','integrationSetup','jira~'+(arg==='personal'?'personal':'team'))+'</div><p class="app-catalog-empty" hidden>No apps found.</p></div>';
      if(type==='integrationSetup'){
        const existing=model.setups(db()).find(a=>a.id===arg),[provider,scope]=arg.split('~');
        const a=existing||{provider,scope,name:''};
        if(!['jira','github'].includes(a.provider))return '<p>App unavailable.</p>';
        const github=a.provider==='github',name=github?'GitHub':'Jira';
        return form(type,'<div class="setup-intro"><span class="integration-icon">'+icon(github?'code':'tasks')+'</span><div><strong>'+name+'</strong><p>'+(github?'Connect an account or organization.':a.scope==='team'?'Set up a shared team account.':'Set up your personal account.')+'</p></div></div><p class="setup-status">Authorization required · Not connected</p>'+field(github?'Account or organization':'Account name','<input name="name" value="'+esc(a.name)+'" required maxlength="100" placeholder="'+(github?'e.g. acme':'e.g. Engineering Jira')+'" autocomplete="off">')+'<p class="settings-help">'+(github?'GitHub App authorization is required to read repository and pull request data.':'Atlassian authorization is required to access Jira issues and projects.')+'</p>'+cancel,'Save setup',arg);
      }
      if(type==='integrationRemove'){
        const a=model.setups(db()).find(a=>a.id===arg);if(!a)return '<p>Account unavailable.</p>';
        return form(type,'<p>Remove the '+esc(a.provider==='jira'?'Jira':'GitHub')+' setup for <strong>'+esc(a.name)+'</strong>?</p>'+cancel,'Remove setup',arg);
      }
      return '';
    }
    function submit(type,id,data){
      if(type==='repositoryEditor')model.saveRepository(db(),{id,url:data.url,description:data.description});
      else if(type==='repositoryRemove')model.removeRepository(db(),id);
      else if(type==='integrationSetup'){
        const old=model.setups(db()).find(a=>a.id===id),[provider,scope]=id.split('~');
        model.saveSetup(db(),{id:old?.id,provider:old?.provider||provider,scope:old?.scope||scope,name:data.name});
        return {tab:(old?.provider||provider)==='github'?'code':'apps',message:'Setup saved. Authorization is required.'};
      }else if(type==='integrationRemove'){
        const a=model.setups(db()).find(a=>a.id===id);model.removeSetup(db(),id);
        return {tab:a?.provider==='github'?'code':'apps',message:'Setup removed.'};
      }else if(type==='integrationPreferences')model.savePreferences(db(),{reading:data.reading,association:data.association==='on'?'issue':'off',afterMerge:data.afterMerge,prSidebar:data.prSidebar==='on',coAuthor:data.coAuthor==='on'});
      else return null;
      return {tab:'code',message:type==='repositoryRemove'?'Repository removed.':type==='repositoryEditor'?'Repository saved.':'Code preferences saved.'};
    }
    return {page,navigation,editor,submit,tab};
  }
  return {create};
})();
