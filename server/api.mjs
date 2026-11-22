import {contribution,validateCommits} from './contribution.mjs';
import {dashboardRows} from './mock-content.mjs';
import {createServer as httpServer} from 'node:http';
import {randomUUID} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {openStore} from './store.mjs';
const collections=new Set(['projects','issues','agents','skills','squads','autopilots','labels']);
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2','.png':'image/png'};
function fail(status,message){throw Object.assign(new Error(message),{status});}
async function readBody(req){let text='';for await(const chunk of req){text+=chunk;if(text.length>1024*1024)fail(413,'Request too large');}try{const v=JSON.parse(text||'{}');if(!v||Array.isArray(v)||typeof v!=='object')fail(400,'Expected an object');return v;}catch(e){if(e.status)throw e;fail(400,'Invalid JSON');}}
export function createServer({dbPath='server/data/workpal.sqlite',staticDir=resolve('apps/web/dist')}={}) {
 const store=openStore(dbPath);
 const server=httpServer(async(req,res)=>{
  const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
  try {
   const url=new URL(req.url,'http://localhost'),path=url.pathname,method=req.method;
   if(!path.startsWith('/api/')){
    if(method!=='GET')fail(405,'Method not allowed');
    const file=resolve(staticDir,'.'+decodeURIComponent(path==='/'?'/index.html':path));
    if(!file.startsWith(resolve(staticDir)+sep))fail(403,'Forbidden');
    try{const data=await readFile(file);res.writeHead(200,{'Content-Type':types[extname(file)]||'application/octet-stream'});res.end(data);return;}catch{fail(404,'File not found; run pnpm build first');}
   }
   const origin=req.headers.origin;
   if(origin&&origin!==`http://${req.headers.host}`&&!['http://127.0.0.1:4174','http://localhost:4174'].includes(origin))fail(403,'Origin not allowed');
   if(method==='POST'&&path==='/api/upload-file'){
    const chunks=[];let size=0;
    for await(const chunk of req){size+=chunk.length;if(size>6*1024*1024)fail(413,'Avatar image must be smaller than 5 MB');chunks.push(chunk);}
    let form;try{form=await new Request('http://localhost/upload',{method:'POST',headers:{'content-type':req.headers['content-type']||''},body:Buffer.concat(chunks)}).formData();}catch{fail(400,'Expected an image upload');}
    const file=form.get('file');if(!file||typeof file==='string'||!file.size)fail(400,'Choose an image');
    if(file.size>5*1024*1024)fail(413,'Avatar image must be smaller than 5 MB');
    const bytes=Buffer.from(await file.arrayBuffer());
    const mime=bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))?'image/png':bytes[0]===255&&bytes[1]===216&&bytes[2]===255?'image/jpeg':bytes.subarray(0,6).toString().match(/^GIF8[79]a$/)?'image/gif':bytes.subarray(0,4).toString()==='RIFF'&&bytes.subarray(8,12).toString()==='WEBP'?'image/webp':null;
    if(!mime)fail(415,'Choose a PNG, JPEG, GIF or WebP image');
    const id=randomUUID(),url='/api/files/'+id;
    store.put('uploaded_files',{id,mime,data:bytes.toString('base64'),filename:file.name});
    return send(201,{id,url,download_url:url,filename:file.name,size:file.size,content_type:mime});
   }
   if(method==='GET'&&/^\/api\/files\/[^/]+$/.test(path)){
    const file=store.get('uploaded_files',path.split('/').at(-1));if(!file)fail(404,'Image not found');
    res.writeHead(200,{'Content-Type':file.mime,'X-Content-Type-Options':'nosniff','Cache-Control':'private, max-age=3600'});res.end(Buffer.from(file.data,'base64'));return;
   }
   const body=['POST','PUT','PATCH'].includes(method)?await readBody(req):{};
   const workspace=store.list('workspaces')[0],user=store.list('users')[0];
   if(method==='GET'&&path==='/api/bootstrap')return send(200,{workspace,user,projects:store.list('projects')});
   if(method==='GET'&&path==='/api/me')return send(200,user);
   if(method==='GET'&&path==='/api/workspaces')return send(200,store.list('workspaces'));
   if(method==='GET'&&path===`/api/workspaces/${workspace.id}`)return send(200,workspace);
   if(method==='GET'&&/^\/api\/(issues|projects)\/search$/.test(path)){
    const kind=path.split('/')[2],q=(url.searchParams.get('q')||'').toLowerCase();
    const rows=store.list(kind).filter(row=>[row.title,row.identifier,row.description].some(v=>typeof v==='string'&&v.toLowerCase().includes(q)));
    const offset=Math.max(0,Number(url.searchParams.get('offset'))||0),limit=Math.min(100,Math.max(1,Number(url.searchParams.get('limit'))||20));
    return send(200,{[kind]:rows.slice(offset,offset+limit).map(row=>({...row,match_source:'title'}))});
   }
   if(method==='GET'&&path==='/api/issues/child-progress'){
    const issues=store.list('issues');return send(200,{progress:issues.map(row=>{const children=issues.filter(c=>c.parent_issue_id===row.id);return {parent_issue_id:row.id,total:children.length,done:children.filter(c=>c.status==='done').length};}).filter(row=>row.total)});
   }
   if(method==='GET'&&/^\/api\/dashboard\/(usage\/(daily|by-agent)|agent-runtime|runtime\/daily|failures\/(daily|by-agent))$/.test(path))return send(200,dashboardRows(store,path,url.searchParams));
   if(path==='/api/dashboard/contribution'){
    if(method==='GET')return send(200,contribution(store,url.searchParams));
    if(method==='PUT'){
     let commits;try{commits=validateCommits(body.commits);}catch(error){fail(400,error.message);}
     store.put('contribution_data',{id:'workspace',commits});return send(200,{count:commits.length});
    }
   }
   if(method==='GET'&&path==='/api/issues/unread')return send(200,[]);
   const issueDetail=path.match(/^\/api\/issues\/([^/]+)\/(comments|timeline|children|labels|task-runs|wakeups|system-wakeups|duplicates|pull-requests|environments)$/);
   if(method==='GET'&&issueDetail){
    const id=decodeURIComponent(issueDetail[1]),kind=issueDetail[2],issue=store.get('issues',id);if(!issue)fail(404,'Issue not found');
    const comments=store.list('comments').filter(c=>c.issue_id===id).sort((a,b)=>a.created_at.localeCompare(b.created_at));
    if(kind==='comments')return send(200,comments);
    if(kind==='timeline')return send(200,comments.map(c=>({...c,type:'comment',comment_type:c.type,actor_type:c.author_type,actor_id:c.author_id})));
    if(kind==='children')return send(200,{issues:store.list('issues').filter(i=>i.parent_issue_id===id)});
    if(kind==='labels')return send(200,issue.labels||[]);
    if(kind==='pull-requests')return send(200,{pull_requests:[],auto_complete:null});
    if(kind==='environments')return send(200,{environments:[],configs:[],pending_starts:[],failed_starts:[]});
    if(kind==='duplicates')return send(200,{duplicate_of:null,duplicates:[]});
    return send(200,[]);
   }
   if(method==='GET'&&path==='/api/chat/pending-tasks')return send(200,{tasks:[]});
   if(method==='GET'&&path==='/api/chat/pending-tasks/has-any')return send(200,{has_pending:false});
   if(method==='GET'&&['/api/agent-task-snapshot','/api/issue-wakeup-summaries','/api/issue-wakeup-paused'].includes(path))return send(200,[]);
   if(method==='GET'&&/^\/api\/projects\/[^/]+\/resources$/.test(path))return send(200,{resources:[],total:0});
   if(method==='GET'&&/^\/api\/projects\/[^/]+\/subscription$/.test(path))return send(200,{subscribed:false});
   if(method==='GET'&&/^\/api\/projects\/[^/]+\/members$/.test(path))return send(200,{members:[],total:0,manager_id:user.id});
   if(method==='GET'&&/^\/api\/runtimes\/[^/]+$/.test(path)){const row=store.get('runtimes',decodeURIComponent(path.split('/').at(-1)));if(!row)fail(404,'Runtime not found');return send(200,row);}
   const squadMembers=path.match(/^\/api\/squads\/([^/]+)\/members(?:\/(status))?$/);
   if(method==='GET'&&squadMembers){
    const squad=store.get('squads',decodeURIComponent(squadMembers[1]));if(!squad)fail(404,'Squad not found');
    const members=(squad.member_preview||[]).filter(m=>typeof m.member_id==='string'&&['agent','member'].includes(m.member_type)).map(m=>({...m,id:squad.id+':'+m.member_type+':'+m.member_id,squad_id:squad.id,created_at:squad.created_at}));
    return send(200,squadMembers[2]?{members:members.map(m=>({member_type:m.member_type,member_id:m.member_id,status:m.member_type==='agent'?'offline':null,active_issues:[],last_active_at:null}))}:members);
   }
   if(method==='GET'&&/^\/api\/workspaces\/[^/]+\/members$/.test(path))return send(200,[{id:user.id,user_id:user.id,workspace_id:workspace.id,role:'owner',name:user.name,email:user.email,user}]);
   if(path.includes('preferences')){
    if(!['GET','PUT','PATCH'].includes(method))fail(405,'Method not allowed');
    const id=path+url.search;if(method==='GET')return send(200,store.get('preferences',id)?.value||{});
    store.put('preferences',{id,value:body});return send(200,body);
   }
   if(method==='GET'&&path==='/api/issue-statuses'){
    const categories=['unstarted','started','done','closed'];
    const statuses=['backlog','todo','in_progress','in_review','blocked','done','cancelled'].map((key,position)=>({id:key,key,name:key.replaceAll('_',' '),workspace_id:workspace.id,category:position<2?'unstarted':position<5?'started':position===5?'done':'closed',is_system:true,position,created_at:workspace.created_at,updated_at:workspace.created_at}));
    return send(200,{statuses,categories,total:statuses.length});
   }
   if(method==='GET'&&path==='/api/issue-workflows')return send(200,{workflows:[],total:0});
   if(method==='GET'&&path==='/api/labels')return send(200,{labels:store.list('labels'),total:store.list('labels').length});
   if(method==='GET'&&path==='/api/config')return send(200,{registration_enabled:false});
   if(method==='GET'&&path==='/api/runtimes')return send(200,store.list('runtimes'));
   if(method==='GET'&&path==='/api/chat/sessions')return send(200,store.list('sessions'));
   if(method==='GET'&&path==='/api/agent-run-counts')return send(200,[]);
   if(method==='GET'&&path==='/api/inbox/unread-summary')return send(200,{});
   if(method==='GET'&&(/^\/api\/(inbox|pins|issue-views|notifications|connected-apps)$/.test(path)||/\/(comments|subscribers|attachments|activity|tasks|runs|versions)$/.test(path)||path.startsWith('/api/dashboard/')))return send(200,[]);
   if(path.startsWith('/api/issues/table/')&&['GET','POST'].includes(method)){
    let rows=store.list('issues');const key=body.group_key;const query=body.query||{};
    if(query.scope?.project_id)rows=rows.filter(r=>r.project_id===query.scope.project_id);
    if(query.search)rows=rows.filter(r=>(r.title+' '+r.identifier).toLowerCase().includes(query.search.toLowerCase()));
    for(const [filter,field] of [['statuses','status'],['priorities','priority'],['project_ids','project_id']])if(query.filters?.[filter]?.length)rows=rows.filter(r=>query.filters[filter].includes(r[field]));
    if(key)rows=rows.filter(r=>[r.status,'status:'+r.status,'status/'+r.status].includes(key));
    if(body.hierarchy?.enabled)rows=rows.filter(r=>r.parent_issue_id===(body.parent_id||null));
    const common={query_fingerprint:'local',total:rows.length,next_cursor:null};
    if(path.endsWith('/rows'))return send(200,{...common,group_key:key||null,parent_id:body.parent_id||null,branch_total:rows.length,rows:rows.map(issue=>({issue,direct_child_count:issue.sub_issue_count||0}))});
    if(path.endsWith('/groups'))return send(200,{...common,groups:[...new Set(rows.map(r=>r.status))].map(status=>({key:'status:'+status,value:{kind:'status',status},count:rows.filter(r=>r.status===status).length}))});
    if(path.endsWith('/facets'))return send(200,{...common,facets:[]});
   }
   const match=path.match(/^\/api\/([^/]+)(?:\/([^/]+))?$/);
   if(match&&collections.has(match[1])){
    const kind=match[1],id=match[2]?decodeURIComponent(match[2]):null;
    if(method==='GET'){
     if(id){const row=store.get(kind,id);if(!row)fail(404,'Record not found');return send(200,row);}
     let rows=store.list(kind);
     for(const field of ['status','project_id'])if(url.searchParams.has(field))rows=rows.filter(r=>r[field]===url.searchParams.get(field));
     if(url.searchParams.has('q'))rows=rows.filter(r=>(r.title||r.name||'').toLowerCase().includes(url.searchParams.get('q').toLowerCase()));
     const total=rows.length,offset=Math.max(0,Number(url.searchParams.get('offset'))||0),limit=Math.min(10000,Math.max(1,Number(url.searchParams.get('limit'))||10000));rows=rows.slice(offset,offset+limit);
     return send(200,['projects','issues'].includes(kind)?{[kind]:rows,total}:rows);
    }
    if(method==='DELETE'&&id){if(!store.remove(kind,id))fail(404,'Record not found');return send(200,{});}
    if((method==='POST'&&!id)||(['PATCH','PUT'].includes(method)&&id)){
     const old=id?store.get(kind,id):null;if(id&&!old)fail(404,'Record not found');
     const field=['issues','projects','autopilots'].includes(kind)?'title':'name';
     if((!old||field in body)&&(typeof body[field]!=='string'||!body[field].trim()||body[field].length>500))fail(400,`${field} must contain 1–500 characters`);
     for(const field of ['description','status','priority'])if(field in body&&body[field]!==null&&typeof body[field]!=='string')fail(400,`${field} must be text`);
     const now=new Date().toISOString(),newId=id||randomUUID();
     const defaults={id:newId,workspace_id:workspace.id,created_at:now,creator_id:user.id,creator_type:'member',status:kind==='issues'?'todo':'in_progress',priority:'none',icon:null,lead_type:null,lead_id:null,start_date:null,due_date:null,description:'',labels:[],metadata:{},properties:{},position:store.list(kind).length,parent_issue_id:null,project_id:null,assignee_type:null,assignee_id:null,visibility:'workspace',issue_count:0,done_count:0,sub_issue_count:0,completed_sub_issue_count:0};
     if(kind==='issues'){defaults.number=Date.now();defaults.identifier='WP-'+defaults.number;defaults.priority='medium';}
     const row={...defaults,...old,...body,id:newId,workspace_id:workspace.id,created_at:old?.created_at||now,updated_at:now};
     return send(old?200:201,store.put(kind,row));
    }
   }
   fail(501,'This operation is unavailable in the local backend.');
  }catch(error){send(error.status||500,{error:error.status?error.message:'Internal server error'});if(!error.status)console.error(error);}
 });
 server.on('close',()=>store.close());return server;
}
