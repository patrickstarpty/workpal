import {createServer as httpServer} from 'node:http';
import {randomUUID} from 'node:crypto';
import {readFile} from 'node:fs/promises';
import {resolve,extname,sep} from 'node:path';
import {openStore} from './store.mjs';
const collections=new Set(['projects','issues','agents','skills','squads','autopilots','labels']);
const types={'.html':'text/html','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.woff2':'font/woff2','.png':'image/png'};
function fail(status,message){throw Object.assign(new Error(message),{status});}
async function readBody(req){let text='';for await(const chunk of req){text+=chunk;if(text.length>1024*1024)fail(413,'Request too large');}try{const v=JSON.parse(text||'{}');if(!v||Array.isArray(v)||typeof v!=='object')fail(400,'Expected an object');return v;}catch(e){if(e.status)throw e;fail(400,'Invalid JSON');}}
export function createServer({dbPath='data/workpal.sqlite',staticDir=resolve('dist')}={}) {
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
   const body=['POST','PUT','PATCH'].includes(method)?await readBody(req):{};
   const workspace=store.list('workspaces')[0],user=store.list('users')[0];
   if(method==='GET'&&path==='/api/bootstrap')return send(200,{workspace,user,projects:store.list('projects')});
   if(method==='GET'&&path==='/api/me')return send(200,user);
   if(method==='GET'&&path==='/api/workspaces')return send(200,store.list('workspaces'));
   if(method==='GET'&&path===`/api/workspaces/${workspace.id}`)return send(200,workspace);
   if(method==='GET'&&path.endsWith('/members'))return send(200,[{id:user.id,user_id:user.id,workspace_id:workspace.id,role:'owner',name:user.name,email:user.email,user}]);
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
