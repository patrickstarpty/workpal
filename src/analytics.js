// Analytics presentation. Historical fixtures stay separate from execution records.
globalThis.WorkpalAnalytics = (() => {
  'use strict';
  let app, resizeTimer;
  const preferences = new Map();
  const metrics = {tokens:'Tokens',cost:'Cost',seconds:'Time',runs:'Runs'};
  const errorNames = {auth:'Auth',rate_limit:'Rate limit',timeout:'Timeout',provider:'Provider',runtime:'Runtime',agent:'Agent',other:'Other'};
  const esc = value => app.esc(String(value ?? ''));
  const icon = name => app.icon(name);
  const data = () => WorkpalAnalyticsData;
  function prefs() {
    const id=app.workspace().id;
    if(!preferences.has(id))preferences.set(id,{metric:'tokens',rank:'tokens',grain:'daily',errorGrain:'daily',offenderRank:'failed',showAll:false,showOffenders:false,codes:false,refreshed:Date.now()});
    return preferences.get(id);
  }
  function selection() {
    const params=new URLSearchParams(location.hash.split('?')[1]||'');
    const db=app.getDb(),rawTeam=params.get('team'),rawProject=params.get('project');
    const team=Object.hasOwn(app.teams,rawTeam)?rawTeam:'';
    const project=db.projects.includes(rawProject)?rawProject:'';
    const days=[1,7,30,90,180].includes(Number(params.get('days')))?Number(params.get('days')):30;
    const tab=['usage','errors','teams'].includes(params.get('tab'))?params.get('tab'):team?'teams':'usage';
    return {team,project,days,tab};
  }
  function snapshot() {
    const db=app.getDb();
    if(data().ensure(db,app.workspace().id))app.write();
    return data().snapshot(db,selection());
  }
  function navigate(key,value) {
    const state=selection();state[key]=value;
    if(key==='team'&&state.tab==='teams')state.tab='teams';
    const params=new URLSearchParams();
    params.set('tab',state.tab);
    for(const k of ['days','project','team'])if(state[k]&&!(k==='days'&&state[k]===30))params.set(k,String(state[k]));
    location.hash=app.scoped('stats')+'?'+params;
  }
  function control(label,key,items,value,iconName) {
    return `<label class="analytics-filter" title="${esc(label)}">${icon(iconName)}<select aria-label="${esc(label)}" data-analytics-select="${key}">${Object.entries(items).map(([id,text])=>`<option value="${esc(id)}" ${String(value)===id?'selected':''}>${esc(text)}</option>`).join('')}</select>${icon('chevronDown')}</label>`;
  }
  function segments(label,key,items,value) {
    return `<div class="analytics-segments" role="group" aria-label="${esc(label)}">${Object.entries(items).map(([id,text])=>`<button type="button" data-analytics="${key}" data-value="${esc(id)}" aria-pressed="${id===value}">${esc(text)}</button>`).join('')}</div>`;
  }
  function grainOptions(days) {return days<=7?['daily']:days===180?['weekly']:['daily','weekly'];}
  function grain(days,key) {const allowed=grainOptions(days);return allowed.includes(prefs()[key])?prefs()[key]:allowed[0];}
  function grainControl(days,key) {const allowed=grainOptions(days);return allowed.length>1?segments('Chart interval',key,{daily:'Daily',weekly:'Weekly'},grain(days,key)):'';}
  function header() {
    const s=selection(),db=app.getDb();
    const tz=new Intl.DateTimeFormat('en',{timeZoneName:'shortOffset'}).formatToParts(new Date()).find(p=>p.type==='timeZoneName')?.value||'';
    const time=new Date(prefs().refreshed).toLocaleTimeString('en-US',{hour:'2-digit',minute:'2-digit'});
    return `<div class="analytics-heading"><button type="button" class="btn mobile-only icon-only" data-act="menu" aria-label="Workspace menu">${icon('menu')}</button><button type="button" class="btn analytics-expand icon-only" data-act="collapseNav" aria-label="Expand sidebar">${icon('panelLeft')}</button><h1>${icon('stats')}<span>Analytics</span></h1><div class="analytics-tabs" role="tablist" aria-label="Analytics views">${['usage','errors','teams'].map(tab=>`<button type="button" role="tab" id="analytics-tab-${tab}" aria-selected="${s.tab===tab}" aria-controls="analytics-panel" data-analytics="tab" data-value="${tab}">${tab[0].toUpperCase()+tab.slice(1)}</button>`).join('')}</div></div><div class="analytics-tools"><small class="analytics-freshness">${esc(tz)} · updated ${esc(time)}</small>${control('Period','days',{'1':'1d','7':'7d','30':'30d','90':'90d','180':'180d'},s.days,'calendar')}${control('Project','project',{'':'All projects',...Object.fromEntries(db.projects.map(p=>[p,p]))},s.project,'projects')}${control('Team','team',{'':'All teams',...app.teams},s.team,'team')}<button type="button" class="btn icon-only analytics-refresh" data-analytics="refresh" aria-label="Refresh analytics" title="Refresh">${icon('refresh')}</button></div>`;
  }
  const kpi = (label,value,hint='') => `<div class="analytics-kpi"><span class="analytics-label">${esc(label)}</span><strong class="analytics-value">${esc(value)}</strong><span class="analytics-hint">${esc(hint)}</span></div>`;
  const empty = (title,caption='') => `<div class="analytics-empty">${icon('stats')}<h3>${esc(title)}</h3>${caption?`<p>${esc(caption)}</p>`:''}</div>`;
  const card = (title,body,controls='',cls='') => `<section class="analytics-card ${cls}"><header class="analytics-card-header"><h2>${esc(title)}</h2><div class="analytics-card-controls">${controls}</div></header>${body}</section>`;
  function format(key,value) {return key==='cost'?data().money(value):key==='seconds'?data().duration(value):data().compact(value);}
  function axisStep(max) {
    if(max>=1&&max<=4)return 1;
    const raw=max/4,power=10**Math.floor(Math.log10(raw)),unit=raw/power;
    return (unit<=1?1:unit<=2?2:unit<=2.5?2.5:unit<=5?5:10)*power;
  }
  function chart(rows,metric,isError=false) {
    const keys=isError?Object.keys(errorNames):metric==='tokens'?['input','output','cacheRead','cacheWrite']:metric==='runs'?['completed','failed']:[metric];
    const labels=isError?errorNames:{input:'Input',output:'Output',cacheRead:'Cache read',cacheWrite:'Cache write',cost:'Cost',seconds:'Run time',completed:'Completed',failed:'Failed'};
    const fills=isError?Object.fromEntries(keys.map((key,i)=>[key,`var(--analytics-error-${i+1})`])):{input:'var(--analytics-blue-1)',output:'var(--analytics-blue-2)',cacheRead:'var(--analytics-blue-4)',cacheWrite:'var(--analytics-blue-3)',cost:'var(--analytics-blue-1)',seconds:'var(--analytics-blue-1)',completed:'var(--analytics-blue-1)',failed:'var(--analytics-error-1)'};
    const amount=(row,key)=>isError?(row.classes?.[key]||0):(row[key]||0);
    const totals=rows.map(row=>keys.reduce((sum,key)=>sum+amount(row,key),0));
    if(!totals.some(Boolean))return `<div class="analytics-chart-empty">${icon('stats')}<span>No data for this metric in the selected period.</span></div>`;
    const width=Math.max(300,Math.min(1080,innerWidth-(innerWidth>=768?424:64))),height=260,left=50,right=10,top=12,bottom=36;
    const plotWidth=width-left-right,plotHeight=height-top-bottom;
    const step=axisStep(Math.max(...totals)),max=step*4;
    const cell=plotWidth/Math.max(1,rows.length),barWidth=Math.max(2,Math.min(80,cell*.7));
    let svg='';
    for(let i=0;i<=4;i++){
      const y=top+plotHeight-i/4*plotHeight,value=i*step;
      svg+=`<line class="chart-grid" x1="${left}" y1="${y}" x2="${width-right}" y2="${y}"/><text class="chart-label" x="${left-10}" y="${y+4}" text-anchor="end">${esc(format(isError?'runs':metric,value))}</text>`;
    }
    rows.forEach((row,index)=>{
      const x=left+index*cell+cell/2;
      let y=top+plotHeight;
      const visible=keys.filter(key=>amount(row,key)>0);
      const dateLabel=new Date((row.date||row.key)+'T00:00:00').toLocaleDateString('en-US',{month:'short',day:'numeric'});
      const tooltip=[(row.days?row.label:dateLabel)+(row.partial?' · Partial week ('+row.days+'/7 days)':''),...visible.map(key=>labels[key]+': '+format(isError?'runs':metric,amount(row,key))),`Total: ${format(isError?'runs':metric,totals[index])}`].join('\n');
      svg+=`<g class="analytics-chart-point" tabindex="0" role="img" aria-label="${esc(tooltip)}" data-analytics-point data-tooltip="${esc(tooltip)}"><title>${esc(tooltip)}</title>`;
      visible.forEach((key,i)=>{
        const h=amount(row,key)/max*plotHeight;y-=h;
        svg+=`<rect x="${x-barWidth/2}" y="${y}" width="${barWidth}" height="${Math.max(.3,h)}" fill="${fills[key]}" opacity="${row.partial?.55:1}" ${i===visible.length-1?'rx="2"':''}/>`;
      });
      svg+=`<rect class="analytics-chart-hit" x="${x-cell/2}" y="${top}" width="${cell}" height="${plotHeight}" fill="transparent"/></g>`;
      const interval=Math.max(1,Math.ceil(rows.length/Math.max(2,Math.floor(plotWidth/70))));
      if(index%interval===0||rows.length===1)svg+=`<text class="chart-label" x="${x}" y="${height-10}" text-anchor="middle">${esc(dateLabel)}</text>`;
    });
    return `<div class="analytics-chart-frame"><svg class="analytics-chart" viewBox="0 0 ${width} ${height}" aria-label="${isError?'Failures':metrics[metric]} over time" role="group">${svg}</svg><div class="analytics-tooltip" role="tooltip" hidden></div></div><div class="analytics-legend">${keys.filter(key=>rows.some(row=>amount(row,key)>0)).map(key=>`<span><i class="analytics-dot" style="background:${fills[key]}"></i>${esc(labels[key])}</span>`).join('')}</div>`;
  }
  function trend(snap,s,isError=false) {
    const p=prefs(),dimension=grain(s.days,isError?'errorGrain':'grain'),metric=isError?'failed':p.metric;
    const title=(dimension==='daily'?'Daily ':'Weekly ')+(isError?'errors':metric==='seconds'?'run time':metrics[metric].toLowerCase());
    const controls=(isError?'':segments('Trend metric','metric',metrics,p.metric))+grainControl(s.days,isError?'errorGrain':'grain');
    return card(title,`<div class="analytics-card-body">${chart(snap[dimension],metric,isError)}</div>`,controls);
  }
  function agentLink(name) {
    const known=app.getDb().agents.some(a=>a.name===name);
    return known?`<button type="button" class="analytics-agent" data-act="surface" data-id="agent|${esc(name)}">${app.avatar(name)}<span>${esc(name)}</span></button>`:`<span class="analytics-agent">${icon('agents')}<span>${esc(name)}</span></span>`;
  }
  function leaderboard(snap) {
    const p=prefs(),sort=p.rank,rows=[...snap.agents].sort((a,b)=>b[sort]-a[sort]),max=Math.max(1,...rows.map(a=>a[sort]));
    const controls=segments('Rank agents by','rank',metrics,sort)+`<small>${rows.length} agents</small>`+(rows.length>10?`<button type="button" class="analytics-link" data-analytics="showAll">${p.showAll?'Show top 10':'Show all'}</button>`:'');
    const table=`<div class="analytics-table-scroll" role="region" aria-label="Agent leaderboard" tabindex="0"><table class="analytics-table"><thead><tr><th>Agent</th><th aria-label="Relative usage"></th>${Object.entries(metrics).map(([k,v])=>`<th class="number ${k===sort?'analytics-sort-active':''}">${v}</th>`).join('')}</tr></thead><tbody>${(p.showAll?rows:rows.slice(0,10)).map(a=>`<tr><td>${agentLink(a.name)}</td><td class="rank-cell"><span class="analytics-rank-track"><i style="width:${100*a[sort]/max}%"></i></span></td>${Object.keys(metrics).map(k=>`<td class="number ${k===sort?'analytics-sort-active':''}">${esc(format(k,a[k]))}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
    return card('Leaderboard',rows.length?table:empty('No agent usage in this period.'),controls,'analytics-leaderboard');
  }
  function usage(snap,s) {
    if(!snap.records.length)return empty('No usage yet','Agent usage will appear here once runs report activity.');
    const t=snap.totals,suffix=' · '+s.days+'D';
    return `<div class="analytics-kpis">${kpi('Cost'+suffix,data().money(t.cost))}${kpi('Tokens'+suffix,data().compact(t.tokens),'Input '+data().compact(t.input)+' · Output '+data().compact(t.output))}${kpi('Run time'+suffix,data().duration(t.seconds),'Across '+t.runs+' runs')}${kpi('Runs'+suffix,t.runs,t.failed+' failed')}</div>${trend(snap,s)}${leaderboard(snap)}`;
  }
  function mix(snap) {
    const p=prefs(),items=snap.classes.filter(item=>item.count),total=snap.totals.failed;
    const bar=`<div class="analytics-status-bar">${items.map(item=>`<i style="width:${100*item.count/total}%;background:var(--analytics-error-${Object.keys(errorNames).indexOf(item.key)+1})" title="${esc(item.label)}: ${item.count}"></i>`).join('')}</div>`;
    const rows=p.codes?snap.reasons:items;
    const legend=`<div class="analytics-mix-legend">${rows.map(item=>`<div class="mix-item"><i class="analytics-dot" style="background:var(--analytics-error-${Object.keys(errorNames).indexOf(p.codes?item.class:item.key)+1})"></i><span>${p.codes?'<code>'+esc(item.key)+'</code>':esc(item.label)}</span><strong>${item.count}</strong><small>${data().rate(item.count,total)}</small></div>`).join('')}</div>`;
    return card('Failure mix · '+total,`<div class="analytics-mix">${bar}${legend}</div>`,`<button type="button" class="analytics-link" data-analytics="codes" aria-expanded="${p.codes}">${p.codes?'Hide':'Show'} error codes</button>`);
  }
  function offenders(snap) {
    const p=prefs(),rows=snap.agents.filter(a=>a.failed).sort((a,b)=>p.offenderRank==='rate'?(Number(b.runs>=10)-Number(a.runs>=10)||b.failureRate-a.failureRate):b.failed-a.failed);
    const max=Math.max(1,...rows.map(a=>p.offenderRank==='rate'?a.failureRate:a.failed));
    const controls=segments('Rank offenders by','offenderRank',{failed:'Failures',rate:'Rate'},p.offenderRank)+(rows.length>8?`<button type="button" class="analytics-link" data-analytics="showOffenders">${p.showOffenders?'Show top 8':'Show all'}</button>`:'');
    const table=`<div class="analytics-table-scroll" tabindex="0" role="region" aria-label="Top offenders"><table class="analytics-table"><thead><tr><th>Agent</th><th>Failure mix</th><th class="number">Failed</th><th class="number">Runs</th><th class="number">Rate</th></tr></thead><tbody>${(p.showOffenders?rows:rows.slice(0,8)).map(a=>`<tr><td>${agentLink(a.name)}${a.runs<10?'<small class="analytics-small-sample">Fewer than 10 runs</small>':''}</td><td class="rank-cell"><span class="analytics-status-bar" style="width:${Math.max(1,100*(p.offenderRank==='rate'?a.failureRate:a.failed)/max)}%">${Object.keys(errorNames).filter(k=>a.classes[k]).map(k=>`<i style="width:${100*a.classes[k]/a.failed}%;background:var(--analytics-error-${Object.keys(errorNames).indexOf(k)+1})" title="${esc(errorNames[k])}: ${a.classes[k]}"></i>`).join('')}</span></td><td class="number">${a.failed}</td><td class="number">${a.runs}</td><td class="number">${data().rate(a.failed,a.runs)}</td></tr>`).join('')}</tbody></table></div>`;
    return card('Top offenders',table,controls);
  }
  function errors(snap,s) {
    const t=snap.totals,suffix=' · '+s.days+'D',worst=[...snap.agents].sort((a,b)=>b.failed-a.failed)[0];
    return `<div class="analytics-kpis three">${kpi('Failed runs'+suffix,t.failed,'Of '+t.runs+' runs')}${kpi('Failure rate'+suffix,data().rate(t.failed,t.runs),t.failed+' of '+t.runs+' runs failed')}${kpi('Agents affected'+suffix,t.affected,t.failed&&worst?'Most failures: '+worst.name+' · '+worst.failed:'')}</div>${t.failed?trend(snap,s,true)+mix(snap)+offenders(snap):empty('No failed runs in this window','Change the period or scope to explore another view.')}`;
  }
  function teamsPage(snap,s) {
    const db=app.getDb(),items=db.tasks.filter(t=>(!s.project||t.project===s.project)&&(!s.team||t.team===s.team));
    const active=items.filter(t=>t.status==='active').length,review=items.filter(t=>t.status==='review').length,done=items.filter(t=>t.status==='done').length;
    const kpis=`<div class="analytics-kpis">${kpi('Total issues',items.length,'Current workspace status')}${kpi('In progress',active,'Issues being worked on')}${kpi('In review',review,'Awaiting a decision')}${kpi('Completed',done,items.length?Math.round(100*done/items.length)+'% of issues':'No issues yet')}</div>`;
    const groups=Object.entries(app.teams).filter(([id])=>!s.team||id===s.team);
    const allByTeam=Object.fromEntries(groups.map(([id])=>[id,items.filter(t=>t.team===id)]));
    const table=`<div class="analytics-table-scroll" role="region" aria-label="Workload by team" tabindex="0"><table class="analytics-table analytics-team-table"><thead><tr><th>Team</th><th>Issue status</th><th class="number">Issues</th><th class="number">Runs · ${s.days}d</th><th class="number">Cost · ${s.days}d</th><th class="number">Failed</th></tr></thead><tbody>${groups.map(([id,name])=>{
      const tasks=allByTeam[id],records=snap.records.filter(r=>r.team===id),counts=Object.keys(app.states).map(k=>tasks.filter(t=>t.status===k).length);
      return `<tr><td><button type="button" class="analytics-agent" data-analytics="drillTeam" data-value="${esc(id)}">${icon('team')}<span>${esc(name)}</span>${icon('chevron')}</button></td><td><span class="analytics-status-bar">${Object.keys(app.states).map((k,i)=>`<i class="${k}" style="width:${100*counts[i]/Math.max(1,tasks.length)}%" title="${esc(app.states[k])}: ${counts[i]}"></i>`).join('')}</span></td><td class="number">${tasks.length}</td><td class="number">${records.length}</td><td class="number">${data().money(records.reduce((n,r)=>n+r.cost,0))}</td><td class="number">${records.filter(r=>r.status==='failed').length}</td></tr>`;
    }).join('')}</tbody></table></div><div class="analytics-legend analytics-team-legend">${Object.entries(app.states).map(([k,name])=>`<span><i class="analytics-dot ${k}"></i>${esc(name)}</span>`).join('')}</div>`;
    let details='';
    if(s.team)details=card(app.teams[s.team]+' issues',`<div class="analytics-team-issues">${app.issueList(items)}</div>`,`<button type="button" class="analytics-link" data-analytics="teamUsage">View usage ${icon('arrow')}</button>`);
    return kpis+card('Workload by team',table,`<small>Issue status now · Usage over ${s.days} days</small>`)+details+`<div class="analytics-footer"><button type="button" class="btn" data-act="surface" data-id="summary|${esc(s.team)}">${icon('reports')} Generate ${s.team?'team':'workspace'} summary</button>${s.team?'<button type="button" class="analytics-link" data-analytics="allTeams">All teams</button>':''}</div>`;
  }
  function pinned() {
    if(!app.getDb().panels.length)return '';
    return `<section class="analytics-card analytics-pinned"><header class="analytics-card-header"><h2>Pinned panels</h2><button type="button" class="analytics-link" data-act="surface" data-id="panel|">Build panel</button></header><div class="analytics-card-body">${app.getDb().panels.map(key=>{const [team,group]=key.split(':');return `<button type="button" class="btn" data-act="surface" data-id="panel|${esc(key)}">${icon('pin')}${esc(app.teams[team]||'Workspace')} by ${esc(group)}</button>`;}).join('')}</div></section>`;
  }
  function page() {
    const s=selection(),snap=snapshot();
    return `<div class="analytics-page" id="analytics-panel" role="tabpanel" aria-labelledby="analytics-tab-${s.tab}">${s.tab==='errors'?errors(snap,s):s.tab==='teams'?teamsPage(snap,s):usage(snap,s)}${pinned()}</div>`;
  }
  function showTooltip(target) {
    const point=target.closest?.('[data-analytics-point]');if(!point)return;
    const frame=point.closest('.analytics-chart-frame'),tooltip=frame.querySelector('.analytics-tooltip');
    tooltip.textContent=point.dataset.tooltip;tooltip.hidden=false;
    const pointBox=point.getBoundingClientRect(),frameBox=frame.getBoundingClientRect();
    tooltip.style.left=Math.max(8,Math.min(frameBox.width-tooltip.offsetWidth-8,pointBox.left-frameBox.left+pointBox.width/2-tooltip.offsetWidth/2))+'px';
    tooltip.style.top='12px';
  }
  function hideTooltips(){document.querySelectorAll('.analytics-tooltip').forEach(el=>el.hidden=true);}
  function init(context) {
    app=context;
    document.addEventListener('click',event=>{
      const button=event.target.closest('[data-analytics]');if(!button)return;
      const key=button.dataset.analytics,value=button.dataset.value;
      if(key==='tab')return navigate('tab',value);
      if(key==='drillTeam')return navigate('team',value);
      if(key==='teamUsage')return navigate('tab','usage');
      if(key==='allTeams')return navigate('team','');
      const p=prefs();
      if(key==='refresh')p.refreshed=Date.now();
      else if(['showAll','showOffenders','codes'].includes(key))p[key]=!p[key];
      else if(['metric','rank','grain','errorGrain','offenderRank'].includes(key))p[key]=value;
      app.render();
      const selector=`[data-analytics="${key}"]${value?'[data-value="'+value+'"]':''}`;
      document.querySelector(selector)?.focus({preventScroll:true});
    });
    document.addEventListener('change',event=>{const key=event.target.dataset.analyticsSelect;if(key)navigate(key,event.target.value);});
    document.addEventListener('pointerover',event=>showTooltip(event.target));
    document.addEventListener('focusin',event=>showTooltip(event.target));
    document.addEventListener('pointerout',event=>{if(event.target.closest?.('[data-analytics-point]')&&!event.relatedTarget?.closest?.('[data-analytics-point]'))hideTooltips();});
    document.addEventListener('focusout',event=>{if(event.target.closest?.('[data-analytics-point]'))hideTooltips();});
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape')hideTooltips();
      if(event.target.matches('[role=tab][data-analytics=tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
        event.preventDefault();const tabs=[...event.target.parentElement.querySelectorAll('[role=tab]')],index=tabs.indexOf(event.target);
        const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
        navigate('tab',tabs[next].dataset.value);
        requestAnimationFrame(()=>document.querySelector('#analytics-tab-'+tabs[next].dataset.value)?.focus());
      }
    });
    window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(document.querySelector('.analytics-page'))app.render();},150);});
  }
  return {init,header,page};
})();
