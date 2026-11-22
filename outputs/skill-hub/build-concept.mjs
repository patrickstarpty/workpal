import {readFile,writeFile} from 'node:fs/promises';
import {workpalAppearance,workpalTypeScale} from './workpal-appearance.mjs';
const sourceFiles=['anthropic','superpowers','pstack','matt-pocock','gstack'];
const parts=await Promise.all(sourceFiles.map(id=>readFile(new URL(`./sources/${id}.json`,import.meta.url),'utf8').then(JSON.parse)));
const typeLabels={research:'Research & analysis',planning:'Planning & strategy',design:'Design & media',engineering:'Engineering & architecture',quality:'Testing & review',operations:'Release & operations',documents:'Documents & data',knowledge:'Knowledge & communication',automation:'Automation & orchestration','skill-authoring':'Skill authoring',principles:'Engineering principles'};
const typeFiles=await Promise.all(['foundations','engineering','gstack'].map(name=>readFile(new URL(`./types-${name}.json`,import.meta.url),'utf8').then(JSON.parse)));
const assignments=Object.assign({},...typeFiles);
const catalog={retrievedAt:new Date().toISOString(),classificationOrigin:'Workpal editorial classification by purpose; independent of upstream source and distribution scope.',types:Object.entries(typeLabels).map(([id,label])=>({id,label})),sources:parts.map(p=>p.source),skills:parts.flatMap(p=>p.skills.map(s=>({...s,types:assignments[s.id]}))),excluded:parts.flatMap(p=>p.excluded.map(e=>({...e,sourceId:p.source.id})))};
if(new Set(catalog.skills.map(s=>s.id)).size!==catalog.skills.length)throw new Error('Duplicate catalog IDs');
for(const s of catalog.skills){
 if(!s.name||!s.description||!s.url||!s.blobSha)throw new Error('Incomplete metadata: '+s.id);
 if(!Array.isArray(s.types)||!s.types.length||s.types.length>3||new Set(s.types).size!==s.types.length||s.types.some(id=>!typeLabels[id]))throw new Error('Invalid types: '+s.id);
}
if(Object.keys(assignments).length!==catalog.skills.length)throw new Error('Classification coverage mismatch');
const roles=JSON.parse(await readFile(new URL('./role-profiles.json',import.meta.url),'utf8'));
const squadCatalog=JSON.parse(await readFile(new URL('./squads.json',import.meta.url),'utf8'));
const coreRoles=squadCatalog.squads.flatMap(s=>s.core);
const sharedRoles=squadCatalog.sharedSpecialists;
if(new Set([...coreRoles,...sharedRoles]).size!==coreRoles.length+sharedRoles.length)throw new Error('Squad role assignments overlap');
if(roles.some(r=>![...coreRoles,...sharedRoles].includes(r.id)))throw new Error('Squad role coverage incomplete');
if(new Set(squadCatalog.squads.map(s=>s.id)).size!==squadCatalog.squads.length)throw new Error('Duplicate squad IDs');
for(const s of squadCatalog.squads){
 for(const id of [...s.core,...s.specialists])if(!roles.some(r=>r.id===id))throw new Error('Unknown squad role: '+id);
 for(const id of s.specialists)if(!sharedRoles.includes(id))throw new Error('Specialist outside shared pool: '+id);
 for(const h of s.handoffs)if(!squadCatalog.squads.some(s=>s.id===h.squadId))throw new Error('Unknown squad handoff: '+h.squadId);
}
for(const role of roles){
 for(const id of role.skills)if(!catalog.skills.some(s=>s.id===id))throw new Error('Unknown role skill: '+id);
 for(const id of role.collaborators)if(!roles.some(r=>r.id===id))throw new Error('Unknown collaborator: '+id);
}
const overviewSkills=JSON.parse(await readFile(new URL('./overview-skills.json',import.meta.url),'utf8'));
const stageNames=['Plan','Design','Build','Test','Deploy','Maintain'];
if(Object.keys(overviewSkills).length!==stageNames.length)throw new Error('Overview stage coverage mismatch');
for(const name of stageNames){
 if(!Array.isArray(overviewSkills[name])||!overviewSkills[name].length)throw new Error('Missing Overview skills: '+name);
 for(const id of overviewSkills[name])if(!catalog.skills.some(s=>s.id===id))throw new Error('Unknown Overview skill: '+id);
}
await writeFile(new URL('./catalog.json',import.meta.url),JSON.stringify(catalog,null,2)+'\n');
let html=await readFile(new URL('../workpal-capability-home-concept.html',import.meta.url),'utf8');
const styles=`
.catalog-search{display:flex;gap:10px;align-items:center;margin-bottom:14px;flex-wrap:wrap}
.catalog-search input{font:inherit;font-size:13px;min-width:0;flex:1;border:1px solid var(--border);background:var(--card);color:var(--foreground);padding:11px 12px;border-radius:var(--radius)}
.catalog-search input:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
.catalog-controls{display:grid;grid-template-columns:minmax(175px,.8fr) minmax(0,1.5fr);gap:12px;margin-bottom:14px}
.catalog-controls label{font-size:11px;color:var(--muted-foreground);display:grid;gap:5px}
.catalog-controls input,.catalog-controls select{min-width:0;width:100%;font:inherit;font-size:13px;padding:10px 11px;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);color:var(--foreground)}
.catalog-controls input:focus-visible,.catalog-controls select:focus-visible{outline:2px solid var(--ring);outline-offset:2px}
.catalog-status{display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:14px}
.type-tags{display:flex;flex-wrap:wrap;gap:4px}
.type-tag{font-size:11px;background:var(--secondary);color:var(--secondary-foreground);padding:2px 6px;border-radius:var(--radius)}
.team-filters{margin-top:18px}
.team-layout{display:grid;grid-template-columns:minmax(165px,.65fr) minmax(0,1.4fr);gap:16px;align-items:start}
.team-roster{display:grid;gap:6px}
.team-roster .role-item{padding:9px 10px}
.agent-profile{display:grid;gap:17px}
.profile-pair{display:grid;grid-template-columns:1fr 1fr;gap:16px}
.profile-basis{border-top:1px solid var(--border);padding-top:12px}
.profile-basis p{margin-top:8px}
.skill-route{font-size:11px}
.squad-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:16px;margin-top:20px}
.squad-card{padding:18px;border:1px solid var(--border);border-radius:var(--radius);background:var(--card);display:flex;flex-direction:column;gap:16px;min-width:0}
.squad-card h2{font-size:20px}
.squad-card .mission{font-size:13px;color:var(--muted-foreground);margin-top:8px}
.squad-card .lineup{display:grid;gap:5px;border-left:2px solid var(--border);padding-left:10px;font-size:12px}
.squad-card .lineup strong{font-weight:500}
.squad-card .squad-output{margin-top:auto}
.squad-card .plain{align-self:flex-start}
.squad-capabilities{padding-left:17px;margin:0;display:grid;gap:5px;font-size:12px}
.shared-pool{margin-top:26px;border-top:1px solid var(--border);padding-top:20px}
.shared-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:14px}
.team-definition{margin-top:20px}
.squad-summary{display:grid;grid-template-columns:1fr 1fr;gap:20px;margin:20px 0}
.squad-summary .wide{grid-column:1/-1}
.squad-section{margin-top:22px}
.squad-section>p{margin:7px 0 12px}
.squad-members{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
.squad-lead{padding:14px;background:var(--secondary);color:var(--secondary-foreground);border-radius:var(--radius);grid-column:1/-1}
.squad-lead strong{font-size:14px;font-weight:500}
.squad-lead p{font-size:12px;margin-top:5px}
.squad-handoffs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:12px}
.team-back{margin-top:20px}
.role-page .agent-profile{margin-top:20px}
.squad-detail h1,.role-page h1{overflow-wrap:anywhere}
#squad-title:focus-visible,#agent-title:focus-visible{outline:2px solid var(--ring);outline-offset:4px}
@media(max-width:540px){.squad-grid,.shared-grid,.squad-members,.squad-summary,.squad-handoffs{grid-template-columns:1fr}.squad-summary .wide{grid-column:auto}}
.catalog-count{font-size:12px;color:var(--muted-foreground);white-space:nowrap}
.skill-card .excerpt{display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.skill-card h3{overflow-wrap:anywhere}
.catalog-footer{display:flex;justify-content:space-between;gap:16px;align-items:center;margin-top:18px}
.source-line{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-top:8px;font-size:11px;color:var(--muted-foreground)}
.source-line a,.source-link{color:var(--foreground);text-underline-offset:3px}
.full-description{font-size:13px;white-space:pre-wrap;overflow-wrap:anywhere;margin-top:12px}
.role-group{margin-top:20px}
.role-group-head{display:flex;justify-content:space-between;align-items:center;gap:10px;margin-bottom:10px}
.role-group-head span{font-size:11px;color:var(--muted-foreground)}
.role-list{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
.role-item{border:1px solid var(--border);border-radius:var(--radius);background:var(--card);padding:12px;text-align:left;min-width:0}
.role-item[aria-pressed=true]{border-color:var(--foreground)}
.role-item strong{display:block;font-size:13px;font-weight:500;overflow-wrap:anywhere}
.role-item span{display:block;font-size:11px;color:var(--muted-foreground);margin-top:4px}
.role-inspector{margin-top:18px;display:grid;grid-template-columns:1fr 1fr;gap:16px}
.role-inspector .wide{grid-column:1/-1}
.role-inspector .value{font-size:12px}
@media(max-width:540px){.role-list,.role-inspector,.catalog-controls,.team-layout,.profile-pair{grid-template-columns:1fr}.team-roster{grid-template-columns:1fr 1fr}.catalog-search input{flex-basis:100%}.catalog-footer{flex-wrap:wrap}}
`;
const chartStyles=(await Promise.all(['capability-charts.css','squad-chart.css'].map(name=>readFile(new URL('./'+name,import.meta.url),'utf8')))).join('\n');
const chartViews=(await Promise.all(['capability-charts.js','squad-chart.js'].map(name=>readFile(new URL('./'+name,import.meta.url),'utf8')))).join('\n');
html=html.replace('</style>',styles+'\n'+chartStyles+'\n</style>');
const encoded=JSON.stringify(catalog).replace(/</g,'\\u003c').replace(/\u2028/g,'\\u2028').replace(/\u2029/g,'\\u2029');
html=html.replace("let current='overview',stage=0,filter='All',selectedSkill=null,agent='researcher';",`let current='overview',stage=0,filter='All',selectedSkill=null,agent='verifier',query='',limit=24,typeFilter='All',roleMode='All';\n const catalog=${encoded};\n const roleProfiles=${JSON.stringify(roles).replace(/</g,'\\u003c')};\n const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));\n const sourceOf=s=>catalog.sources.find(p=>p.id===s.id.split(':')[0]);\n const typeLabel=id=>catalog.types.find(t=>t.id===id)?.label||id;\n const typeTags=s=>'<div class="type-tags">'+s.types.map(id=>'<span class="type-tag">'+esc(typeLabel(id))+'</span>').join('')+'</div>';`);
html=html.replace("roleMode='All';",`squad=null,roleOrigin=null,roleOriginKind='agent',squadOriginKind='squad';\n const squadCatalog=${JSON.stringify(squadCatalog).replace(/</g,'\\u003c')};`);
html=html.replace("agent='verifier'","agent=null");
html=html.replace('Meet the researcher, code simplifier and verifier.','Explore squad capabilities, core lineups and shared specialists.');
html=html.replace('Focused help inside each task.','Specialized squads. Shared expertise.');
html=html.replace('Explore agent roles →','Explore squads →');
// The Overview and Hub share catalog IDs and display the same upstream names.
let mappedStages=0;
html=html.replace(/(\{name:'([^']+)'[^\n]+skills:)\[[^\]]*\]/g,(_,prefix,name)=>{
 if(!overviewSkills[name])throw new Error('Unmapped Overview stage: '+name);
 mappedStages++;
 return prefix+JSON.stringify(overviewSkills[name]);
});
if(mappedStages!==stageNames.length)throw new Error('Overview template changed');
// Remove the base template's illustrative skill and agent records from this catalog view.
html=html.slice(0,html.indexOf(' const skills=['))+html.slice(html.indexOf(' const hero='));
html=html.replace('${chips(s.skills)}','${skillChips(s.skills)}');
html=html.replace(' function overview()',` function skillChips(ids){return '<div class="chips">'+ids.map(id=>{const skill=catalog.skills.find(s=>s.id===id);return '<button type="button" class="chip" data-open-skill="'+esc(id)+'">'+esc(skill.name)+'</button>';}).join('')+'</div>';}
 function overview()`);
html=html.replace(' function overview()',chartViews+'\n function overview()');
html=html.replace("return hero('AI-native software development'","return overviewChart()+hero('AI-native software development'");
const skillPage=`function skillResults(){
 const highlights={
  'anthropic:skills/frontend-design/SKILL.md':['Design a frontend','Create interfaces from design goals.'],
  'superpowers:skills/brainstorming/SKILL.md':['Shape an idea','Clarify intent, requirements and design.'],
  'pstack:pstack/skills/poteto-mode/SKILL.md':['Coordinate engineering work','Choose a playbook for the task.'],
  'matt-pocock:skills/productivity/grill-me/SKILL.md':['Pressure-test a plan','Work through decisions and open questions.'],
  'gstack:plan-ceo-review/SKILL.md':['Review product direction','Examine scope and the product approach.'],
  'anthropic:skills/pptx/SKILL.md':['Create a presentation','Read, edit and create slide decks.'],
  'superpowers:skills/test-driven-development/SKILL.md':['Build with regression coverage','Develop changes through tests.'],
  'pstack:pstack/skills/architect/SKILL.md':['Examine the architecture','Work through engineering design choices.'],
  'matt-pocock:skills/engineering/code-review/SKILL.md':['Review a code change','Assess the change against standards and intent.'],
  'gstack:ship/SKILL.md':['Prepare work for shipping','Follow the repository shipping workflow.'],
  'anthropic:skills/docx/SKILL.md':['Work with Word documents','Create, read and edit documents.'],
  'anthropic:skills/xlsx/SKILL.md':['Work with spreadsheets','Create and edit spreadsheet files.']
 };
 const rank=id=>{const n=Object.keys(highlights).indexOf(id);return n<0?1000:n;};
 const q=query.trim().toLowerCase();
 const matches=catalog.skills.filter(s=>(filter==='All'||sourceOf(s)?.id===filter)&&(typeFilter==='All'||s.types.includes(typeFilter))&&(!q||[s.name,s.description,...(highlights[s.id]||[]),...s.types.map(typeLabel),sourceOf(s)?.label,sourceOf(s)?.author].join(' ').toLowerCase().includes(q))).sort((a,b)=>rank(a.id)-rank(b.id)||a.name.localeCompare(b.name)||a.id.localeCompare(b.id));
 const visible=matches.slice(0,limit),chosen=catalog.skills.find(s=>s.id===selectedSkill),src=chosen?sourceOf(chosen):null;
 return '<div class="catalog-status"><span class="catalog-count" aria-live="polite">'+matches.length+' of '+catalog.skills.length+' entries</span>'+((filter!=='All'||typeFilter!=='All'||query)?'<button type="button" class="link" data-clear="true">Clear filters</button>':'')+'</div>'+
 (chosen?'<section class="panel selection" aria-labelledby="skill-detail-title" style="margin:0 0 18px"><h2 id="skill-detail-title" tabindex="-1">'+esc(chosen.name)+'</h2><button type="button" class="link" data-close-skill="true">← Back to skills</button><div class="source-line"><span>'+esc(src.label)+' · '+esc(src.author)+'</span><span>'+esc(chosen.scope)+'</span><span>'+esc(src.commitSha.slice(0,7))+'</span></div><div style="margin-top:10px">'+typeTags(chosen)+'</div><p class="full-description">'+esc(chosen.description)+'</p><div class="source-line"><a href="'+esc(chosen.url)+'" target="_blank" rel="noopener noreferrer">Read SKILL.md ↗</a><a href="'+esc(src.licenseUrl||src.repositoryUrl)+'" target="_blank" rel="noopener noreferrer">Source & license ↗</a></div></section>':'')+
 '<div class="skill-grid">'+visible.map(s=>'<button type="button" class="skill-card" data-skill="'+esc(s.id)+'" aria-pressed="'+(selectedSkill===s.id)+'"><span class="skill-name">'+esc(sourceOf(s)?.label)+' · '+esc(s.scope)+'</span><h3>'+esc(highlights[s.id]?.[0]||s.name)+'</h3><p class="excerpt">'+esc(highlights[s.id]?.[1]||s.description)+'</p>'+typeTags(s)+'<span class="link">'+esc(s.name)+' →</span></button>').join('')+'</div>'+
 (matches.length?'':'<p class="small">No skills match this search.</p>')+
 '<div class="catalog-footer"><span class="small">Source-linked catalog · entries retain their original identity</span>'+(matches.length>limit?'<button type="button" class="plain" data-more="true">Show more</button>':'')+'</div>';
 }
 function skillPage(){
 return skillCoverageChart()+hero('Skill Hub','A library of reusable expertise.','Explore skills from Anthropic, Superpowers, Lauren Tan, Matt Pocock and Garry Tan.')+
 '<span class="label">Source</span><div class="filters" role="group" aria-label="Skill sources">'+[{id:'All',label:'All sources'},...catalog.sources].map(s=>'<button type="button" data-filter="'+esc(s.id)+'" aria-pressed="'+(filter===s.id)+'">'+esc(s.label)+'</button>').join('')+'</div>'+
 '<div class="catalog-controls"><label>Type<select id="skill-type" aria-label="Skill type"><option value="All"'+(typeFilter==='All'?' selected':'')+'>All types</option>'+catalog.types.map(t=>'<option value="'+t.id+'"'+(typeFilter===t.id?' selected':'')+'>'+esc(t.label)+'</option>').join('')+'</select></label><label>Search<input id="skill-search" type="search" aria-label="Search skills" placeholder="Search skills, uses or authors" value="'+esc(query)+'"></label></div><div id="skill-results">'+skillResults()+'</div>';
 }
 function updateSkillResults(){root.querySelector('#skill-results').innerHTML=skillResults();}
 function focusSkillDetail(){
 const heading=root.querySelector('#skill-detail-title');
 heading?.focus({preventScroll:true});
 heading?.closest('section').scrollIntoView({block:'start'});
 }
 `;
html=html.slice(0,html.indexOf(' function skillPage()'))+' '+skillPage+html.slice(html.indexOf(' function teamPage()'));
const teamPage=(await readFile(new URL('./agent-team-view.js',import.meta.url),'utf8')).replace("return hero('Agent Team'","return teamChart()+hero('Agent Team'");
html=html.slice(0,html.indexOf(' function teamPage()'))+' '+teamPage+html.slice(html.indexOf(' function workspace()'));
const events=`root.addEventListener('click',event=>{
 const b=event.target.closest('button');if(!b)return;let restore=null,openDetail=false,closeDetail=false,teamFocus=null,returnToTeam=false;
 if(b.dataset.nav){current=b.dataset.nav;}
 else if(b.dataset.chartStage){stage=Number(b.dataset.chartStage);teamFocus='.stage-detail h2';}
 else if(b.dataset.chartType){typeFilter=b.dataset.chartType;filter='All';query='';limit=24;selectedSkill=null;teamFocus='#skill-type';}
 else if(b.dataset.stage){stage=Number(b.dataset.stage);restore=['stage',String(stage)];}
 else if(b.dataset.filter){filter=b.dataset.filter;selectedSkill=null;limit=24;restore=['filter',filter];}
 else if(b.dataset.skill){selectedSkill=b.dataset.skill;openDetail=true;}
 else if(b.dataset.closeSkill){restore=['skill',selectedSkill];selectedSkill=null;closeDetail=true;}
 else if(b.dataset.squad||b.dataset.chartSquad){squad=b.dataset.squad||b.dataset.chartSquad;squadOriginKind=b.dataset.chartSquad?'chartSquad':'squad';agent=null;roleOrigin=null;teamFocus='#squad-title';}
 else if(b.dataset.squadBack){restore=[squadOriginKind,squad];squad=null;agent=null;roleOrigin=null;returnToTeam=true;}
 else if(b.dataset.roleBack){restore=[roleOriginKind,roleOrigin||agent];agent=null;roleOrigin=null;returnToTeam=true;}
 else if(b.dataset.agent||b.dataset.chartAgent){agent=b.dataset.agent||b.dataset.chartAgent;roleOrigin=agent;roleOriginKind=b.dataset.chartAgent?'chartAgent':'agent';teamFocus='#agent-title';}
 else if(b.dataset.relatedAgent){agent=b.dataset.relatedAgent;teamFocus='#agent-title';}
 else if(b.dataset.openSkill){selectedSkill=b.dataset.openSkill;current='skills';filter='All';typeFilter='All';query='';limit=24;openDetail=true;}
 else if(b.dataset.clear){filter='All';typeFilter='All';query='';selectedSkill=null;limit=24;}
 else if(b.dataset.more){limit+=24;}
 else return;
 render();
 if(openDetail)focusSkillDetail();
 if(teamFocus){const target=root.querySelector(teamFocus);if(target?.matches('h1,h2'))target.tabIndex=-1;target?.focus({preventScroll:true});target?.scrollIntoView({block:'start'});}
 if(restore){
 const target=Array.from(root.querySelectorAll('button')).find(el=>el.dataset[restore[0]]===restore[1]&&el.getClientRects().length)||(closeDetail?root.querySelector('#skill-search'):returnToTeam?root.querySelector('[data-squad-back]'):null);
 target?.focus({preventScroll:true});
 if(closeDetail||returnToTeam)target?.scrollIntoView({block:'nearest'});
 }
 });
 let composingSearch=false;
 function updateSearch(input){query=input.value;limit=24;selectedSkill=null;updateSkillResults();}
 root.addEventListener('compositionstart',event=>{if(event.target.id==='skill-search')composingSearch=true;});
 root.addEventListener('compositionend',event=>{if(event.target.id!=='skill-search')return;composingSearch=false;updateSearch(event.target);});
 root.addEventListener('input',event=>{if(event.target.id!=='skill-search'||composingSearch||event.isComposing)return;updateSearch(event.target);});
 root.addEventListener('change',event=>{if(event.target.id!=='skill-type')return;typeFilter=event.target.value;limit=24;selectedSkill=null;render();root.querySelector('#skill-type')?.focus({preventScroll:true});});
`;
html=html.slice(0,html.indexOf(" root.addEventListener('click'"))+' '+events+html.slice(html.lastIndexOf(' render();'));
html=html.replaceAll('limit=24','limit=12').replaceAll('limit+=24','limit+=12');
const appearance=await workpalAppearance();
const uiStyles=(await Promise.all(['workpal-ui.css','chart-surfaces.css'].map(file=>readFile(new URL('./'+file,import.meta.url),'utf8')))).join('\n');
html=html.replace('<style>','<style id="workpal-foundation">'+appearance.css+'</style>\n<style>');
html=html.replace(/<style>([\s\S]*?)<\/style>/,(_,css)=>'<style>'+workpalTypeScale(css)+'\n'+uiStyles+'</style>');
html=html.replace('</head>','<style id="workpal-theme"></style></head>');
html=html.replace('<div id="page">','<div id="page" data-mc="page">');
html=html.replace('  <button class="primary"',`  <details class="appearance-menu"><summary>Appearance</summary><div class="appearance-panel"><label>Theme<select id="appearance-theme" aria-label="Theme">${appearance.themes.map(t=>'<option value="'+t.id+'">'+t.name+'</option>').join('')}</select></label><label>Mode<select id="appearance-mode" aria-label="Mode"><option value="system">System</option><option value="light">Light</option><option value="dark">Dark</option></select></label></div></details>\n  <button class="primary"`);
html=html.replace("enter.disabled=current==='workspace';}","enter.disabled=current==='workspace';decorateComponents();}");
html=html.replace("root.querySelector('#skill-results').innerHTML=skillResults();}","root.querySelector('#skill-results').innerHTML=skillResults();decorateComponents();}");
const appearanceRuntime=await readFile(new URL('./appearance-controls.js',import.meta.url),'utf8');
html=html.replace(" root.addEventListener('click'",' const appearanceThemes='+JSON.stringify(appearance.themes).replace(/</g,'\\u003c')+';\n'+appearanceRuntime+"\n root.addEventListener('click'");
await writeFile(new URL('../workpal-capability-hub.html',import.meta.url),html);
console.log(JSON.stringify({sources:catalog.sources.length,records:catalog.skills.length,bySource:Object.fromEntries(parts.map(p=>[p.source.id,p.skills.length])),bytes:Buffer.byteLength(html)}));
