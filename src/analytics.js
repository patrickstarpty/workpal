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
    const db=app.getDb(),rawProject=params.get('project');
    const project=db.projects.includes(rawProject)?rawProject:'';
    const days=[1,7,30,90,180].includes(Number(params.get('days')))?Number(params.get('days')):30;
    const tab=['usage','contribution','errors'].includes(params.get('tab'))?params.get('tab'):'usage';
    return {project,days,tab};
  }
  function snapshot() {
    const db=app.getDb();
    if(data().ensure(db,app.workspace().id))app.write();
    return data().snapshot(db,selection());
  }
  function navigate(key,value) {
    const state=selection();state[key]=value;
    const params=new URLSearchParams();
    params.set('tab',state.tab);
    for(const k of ['days','project'])if(state[k]&&!(k==='days'&&state[k]===30))params.set(k,String(state[k]));
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
    return `<div class="analytics-heading"><button type="button" class="btn mobile-only icon-only" data-act="menu" aria-label="Workspace menu">${icon('menu')}</button><button type="button" class="btn analytics-expand icon-only" data-act="collapseNav" aria-label="Expand sidebar">${icon('panelLeft')}</button><h1>${icon('stats')}<span>Analytics</span></h1><div class="analytics-tabs" role="tablist" aria-label="Analytics views">${['usage','contribution','errors'].map(tab=>`<button type="button" role="tab" id="analytics-tab-${tab}" aria-selected="${s.tab===tab}" aria-controls="analytics-panel" data-analytics="tab" data-value="${tab}">${tab[0].toUpperCase()+tab.slice(1)}</button>`).join('')}</div></div><div class="analytics-tools"><small class="analytics-freshness">${esc(tz)} · updated ${esc(time)}</small>${control('Period','days',{'1':'1d','7':'7d','30':'30d','90':'90d','180':'180d'},s.days,'calendar')}${control('Project','project',{'':'All projects',...Object.fromEntries(db.projects.map(p=>[p,p]))},s.project,'projects')}<button type="button" class="btn icon-only analytics-refresh" data-analytics="refresh" aria-label="Refresh analytics" title="Refresh">${icon('refresh')}</button></div>`;
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
    const step=axisStep(Math.max(...totals)),max=Math.max(step*4,Math.ceil(Math.max(...totals)/step)*step);
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
    return `<div class="analytics-kpis">${kpi('Cost'+suffix,data().money(t.cost))}${kpi('Tokens'+suffix,data().compact(t.tokens),'Input '+data().compact(t.input)+' · Output '+data().compact(t.output))}${kpi('Run time'+suffix,data().duration(t.seconds),'Across '+t.runs+' runs')}${kpi('Runs'+suffix,t.runs,t.failed+' failed')}</div>${trend(snap,s)}<div class="viz-grid">${distribution('Token composition',[{label:'Input',value:t.input},{label:'Output',value:t.output},{label:'Cache read',value:t.cacheRead},{label:'Cache write',value:t.cacheWrite}],true)}${distribution('Runs by agent',snap.agents.map(a=>({label:a.name,value:a.runs})))}</div>${leaderboard(snap)}`;
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
    return `<div class="analytics-kpis three">${kpi('Failed runs'+suffix,t.failed,'Of '+t.runs+' runs')}${kpi('Failure rate'+suffix,data().rate(t.failed,t.runs),t.failed+' of '+t.runs+' runs failed')}${kpi('Agents affected'+suffix,t.affected,t.failed&&worst?'Most failures: '+worst.name+' · '+worst.failed:'')}</div>${lineChart('Run outcomes',snap.daily.map(r=>({...r,label:r.label})),[{key:'completed',label:'Completed'},{key:'failed',label:'Failed'}])}${t.failed?trend(snap,s,true)+mix(snap)+offenders(snap):empty('No failed runs in this window','Change the period or scope to explore another view.')}`;
  }
  function contributionPage(s) {
    const result=data().contribution(app.getDb(),s),t=result.totals;
    const guide=card('Commit attribution',`<div class="analytics-card-body contribution-guide"><p>Reference a ticket number in every commit message. Add the Workpal trailer when Workpal contributes to the change.</p><pre>TAP-027 Improve search feedback\n\nCo-authored-by: Workpal &lt;workpal@users.noreply.github.com&gt;</pre><p>Human commits only need the ticket number and a description. Workpal-assisted includes human + agent collaboration. For records without explicit contribution counts, all changes follow this commit classification.</p><details><summary>Import commit data</summary><p>Import a JSON array to replace this workspace’s saved commit data. Date and project filters apply to linked tickets.</p><pre>[{"repository":"org/repo","sha":"abc123","message":"TAP-027 Fix search","at":"2026-11-19T08:00:00Z","additions":24,"deletions":8}]</pre><label class="btn">Choose JSON file <input type="file" accept=".json,application/json" data-contribution-import></label></details><p role="status" id="contribution-status"></p></div>`);
    const tickets=data().ticketContribution(app.getDb(),result),num=n=>n.toLocaleString('en-US');
    const unique=[...new Map(result.rows.flatMap(r=>r.commits).map(c=>[c.repository+'|'+c.sha,c])).values()];
    const attributed=data().ticketContribution(app.getDb(),{rows:[{id:'summary',added:t.added,deleted:t.deleted,commits:unique}]})[0];
    const calendar=data().contributionCalendar(result,s.days),total=t.added+t.deleted,share=total?100*attributed.agentLines/total:0;
    const summary=card('Contribution summary',`<div class="analytics-card-body"><div class="contribution-compact-totals"><span><strong>${num(tickets.length)}</strong> Tickets</span><span><strong>${num(t.commits)}</strong> Commits</span><span><strong>${num(total)}</strong> Total</span></div><div class="contribution-share-value">${total?share.toFixed(1)+'%':'—'}<small>Agent contribution</small></div><div class="contribution-stacked" role="img" aria-label="Agent ${num(attributed.agentLines)}, Human ${num(attributed.humanLines)}"><i style="width:${share}%;background:${palette[0]}"></i><i style="width:${total?100-share:0}%;background:${palette[1]}"></i></div><div class="analytics-legend"><span><i class="analytics-dot" style="background:${palette[0]}"></i>Agent ${num(attributed.agentLines)}</span><span><i class="analytics-dot" style="background:${palette[1]}"></i>Human ${num(attributed.humanLines)}</span></div><p class="viz-caption">Added +${num(t.added)} · Deleted −${num(t.deleted)}</p></div>`);
    const rows=tickets.map(row=>{const pct=n=>row.totalLines?100*n/row.totalLines:0;return `<tr><td><strong>${esc(row.id)}</strong><small>${esc(row.title||row.name||'')}</small></td><td>${esc(row.team)}</td><td class="number">${num(row.totalLines)}<small>+${num(row.added)} / −${num(row.deleted)}</small></td><td class="number">${num(row.agentLines)}</td><td class="number">${num(row.humanLines)}</td><td class="squad-rate-cell"><div class="contribution-stacked" role="img" aria-label="${esc(row.id)}: Agent ${num(row.agentLines)}, Human ${num(row.humanLines)} lines"><i style="width:${pct(row.agentLines)}%;background:${palette[0]}"></i><i style="width:${pct(row.humanLines)}%;background:${palette[1]}"></i></div></td><td class="number">${row.commits.length}</td></tr>`;}).join('');
    return `<div class="contribution-top-panels">${summary}${commitHeatmap(calendar)}</div>`+card('Contribution by ticket',rows?`<div class="analytics-table-scroll" role="region" aria-label="Ticket contribution" tabindex="0"><table class="analytics-table ticket-contribution-table"><thead><tr><th>Ticket</th><th>Team / squad</th><th class="number">Total</th><th class="number">Agent</th><th class="number">Human</th><th>Contribution</th><th class="number">Commits</th></tr></thead><tbody>${rows}</tbody></table></div>`:empty('No linked tickets','Change the period or import commit data.'))+`<p class="viz-caption">Total lines = additions + deletions in the selected period. Agent + Human = Total. Explicit attribution takes priority; otherwise Workpal-tagged commit changes count toward Agent and other commit changes toward Human. Shared commits appear under each linked ticket and only once in the summary. Team follows the assigned squad or nearest parent assigned to a squad. ${result.excluded} commits without a ticket in scope are excluded.</p><details class="contribution-method"><summary>Attribution rules &amp; import</summary>${guide}<p class="viz-caption">Import agentLines and humanLines on each commit to provide line ownership. Remaining changes follow the commit attribution rule.</p></details>`;

  }

  function commitHeatmap(days){
    const offset=days[0]?.weekday||0,columns=Math.ceil((offset+days.length)/7),step=19,width=56+columns*step;
    const colors=['var(--muted)','color-mix(in srgb, var(--chart-series-1) 25%, var(--card))','color-mix(in srgb, var(--chart-series-1) 50%, var(--card))','color-mix(in srgb, var(--chart-series-1) 75%, var(--card))','var(--chart-series-1)'];
    const level=n=>n===0?0:n<=2?1:n<=5?2:n<=9?3:4;
    let previousMonth='';
    const months=days.map((d,i)=>{const month=d.date.slice(0,7),column=Math.floor((offset+i)/7);if(month===previousMonth)return '';previousMonth=month;return `<text x="${48+column*step}" y="14" class="chart-label">${new Date(d.date+'T12:00:00').toLocaleDateString('en-US',{month:'short'})}</text>`;}).join('');
    const cells=days.map((d,i)=>{const tip=`${d.date}: ${d.commits} commits · Agent ${d.agent} · Human ${d.human}`;return `<g tabindex="0" role="img" class="analytics-chart-point" data-analytics-point data-tooltip="${esc(tip)}" aria-label="${esc(tip)}"><title>${esc(tip)}</title><rect x="${48+Math.floor((offset+i)/7)*step}" y="${26+d.weekday*step}" width="15" height="15" rx="3" fill="${colors[level(d.commits)]}"/></g>`;}).join('');
    return card('Commit activity',`<div class="analytics-card-body"><div class="commit-heatmap-scroll" role="region" aria-label="Daily commit calendar" tabindex="0"><div class="analytics-chart-frame commit-heatmap-frame" style="width:${Math.max(180,width)}px"><svg class="commit-heatmap" width="${Math.max(180,width)}" height="163" role="group" aria-label="Daily commits">${months}${['Mon','Wed','Fri'].map((label,i)=>`<text x="4" y="${57+i*38}" class="chart-label">${label}</text>`).join('')}${cells}</svg><div class="analytics-tooltip" role="tooltip" hidden></div></div></div><div class="commit-heatmap-footer"><span>${days.reduce((n,d)=>n+d.commits,0).toLocaleString('en-US')} commits · ${days[0]?.date||''} — ${days.at(-1)?.date||''}</span><span class="commit-heatmap-legend">Less ${colors.map((color,i)=>`<i style="background:${color}" title="${['0','1–2','3–5','6–9','10+'][i]} commits"></i>`).join('')} More</span></div><p class="viz-caption">Hover or focus a day for details. Use left/right arrow keys to move. Each repository commit is counted once, including commits linked to multiple tickets.</p></div>`);
  }

  const palette=Array.from({length:6},(_,i)=>`var(--chart-series-${i+1})`);
  function distribution(title,entries,ring=false,percent=false){
    const total=entries.reduce((n,e)=>n+e.value,0),max=Math.max(1,...entries.map(e=>e.value));let offset=0;
    const legend=entries.map((e,i)=>`<div class="viz-row"><span><i style="background:${palette[i%palette.length]}"></i>${esc(e.label)}</span><strong>${percent?(total?(100*e.value/total).toFixed(1)+'%':'—'):esc(data().compact(e.value))}</strong>${ring?'':`<div class="viz-track"><b style="width:${100*e.value/max}%;background:${palette[i%palette.length]}"></b></div>`}</div>`).join('');
    const arcs=entries.map((e,i)=>{const length=total?100*e.value/total:0;const result=`<circle cx="90" cy="90" r="64" pathLength="100" fill="none" stroke="${palette[i%palette.length]}" stroke-width="18" stroke-dasharray="${length} ${100-length}" stroke-dashoffset="${-offset}" transform="rotate(-90 90 90)"/>`;offset+=length;return result;}).join('');
    return card(title,`<div class="analytics-card-body ${ring?'viz-ring':'viz-bars'}">${ring?`<svg viewBox="0 0 180 180" role="img" aria-label="${esc(title+': '+entries.map(e=>e.label+' '+e.value).join(', '))}"><circle cx="90" cy="90" r="64" fill="none" stroke="var(--border)" stroke-width="18"/>${arcs}<text x="90" y="87" text-anchor="middle" class="viz-total">${percent?(total?(100*entries[0].value/total).toFixed(1)+'%':'—'):esc(data().compact(total))}</text><text x="90" y="108" text-anchor="middle" class="chart-label">${percent?'Agent contribution':'Total'}</text></svg>`:''}<div class="viz-legend">${legend||'<p>No data in this scope.</p>'}</div></div>`);
  }
  function lineChart(title,rows,series){
    const width=720,height=250,left=46,top=18,bottom=36,plot=width-left-18,h=height-top-bottom;
    const max=Math.max(1,...rows.flatMap(r=>series.map(s=>r[s.key]||0))),ceiling=Math.ceil(max/4)*4;
    const x=i=>left+(rows.length<2?plot/2:i*plot/(rows.length-1)),y=v=>top+h-h*v/ceiling;
    let svg=Array.from({length:5},(_,i)=>`<line class="chart-grid" x1="${left}" x2="${width-18}" y1="${y(i*ceiling/4)}" y2="${y(i*ceiling/4)}"/><text class="chart-label" x="${left-8}" y="${y(i*ceiling/4)+4}" text-anchor="end">${data().compact(i*ceiling/4)}</text>`).join('');
    series.forEach((s,j)=>{const points=rows.map((r,i)=>`${x(i)},${y(r[s.key]||0)}`).join(' ');if(rows.length)svg+=`${j===0?`<polygon points="${x(0)},${y(0)} ${points} ${x(rows.length-1)},${y(0)}" fill="${palette[j]}" opacity=".08"/>`:''}<polyline points="${points}" fill="none" stroke="${palette[j]}" stroke-width="2" vector-effect="non-scaling-stroke"/>`;});
    rows.forEach((r,i)=>{const label=r.label||r.date,tip=[label,...series.map(s=>s.label+': '+(r[s.key]||0))].join('\n');svg+=`<g tabindex="0" role="img" class="analytics-chart-point" data-analytics-point data-tooltip="${esc(tip)}" aria-label="${esc(tip)}"><title>${esc(tip)}</title>${series.map((s,j)=>`<circle cx="${x(i)}" cy="${y(r[s.key]||0)}" r="3" fill="${palette[j]}"/>`).join('')}<rect x="${x(i)-Math.max(4,plot/Math.max(1,rows.length)/2)}" y="${top}" width="${Math.max(8,plot/Math.max(1,rows.length))}" height="${h}" fill="transparent"/></g>`;if(i===0||i===rows.length-1||i%Math.max(1,Math.ceil(rows.length/5))===0)svg+=`<text class="chart-label" x="${x(i)}" y="${height-10}" text-anchor="middle">${esc(label)}</text>`;});
    return card(title,`<div class="analytics-card-body"><div class="analytics-chart-frame"><svg class="analytics-chart" viewBox="0 0 ${width} ${height}" role="group" aria-label="${esc(title)}">${svg}</svg><div class="analytics-tooltip" role="tooltip" hidden></div></div><div class="analytics-legend">${series.map((s,i)=>`<span><i class="analytics-dot" style="background:${palette[i]}"></i>${esc(s.label)}</span>`).join('')}</div><p class="viz-caption">${rows.some(r=>series.some(s=>r[s.key]))?'Hover or focus points for details. Use arrow keys to move.':'No activity in this period.'}</p></div>`);
  }
  function skillDashboard(){
    const records=data().skillUsage(app.getDb()),items=records.map(r=>r.skill);
    const sum=key=>records.reduce((n,r)=>n+r[key],0);
    const weeks=['Week 1','Week 2','Week 3','Week 4'].map((label,i)=>({label,runs:records.reduce((n,r)=>n+r.weekly[i],0)}));
    return `<div class="skill-dashboard"><div class="skill-summary-caption">Workspace library <span>Last 4 weeks · independent of directory filters</span></div><div class="analytics-kpis">${kpi('Total skills',items.length)}${kpi('Active skills',items.length)}${kpi('Activations',sum('total'))}${kpi('Automatic activations',sum('auto'))}${kpi('Auto activation share',sum('total')?Math.round(sum('auto')/sum('total')*100)+'%':'—')}</div><div class="viz-grid skill-charts">${lineChart('Activation trend',weeks,[{key:'runs',label:'Activations'}])}${distribution('Most used skills',records.map(r=>({label:r.skill.name,value:r.total})).sort((a,b)=>b.value-a.value).slice(0,5))}${distribution('Activation methods',[{label:'Manual',value:sum('manual')},{label:'Pinned',value:sum('pinned')},{label:'Automatic',value:sum('auto')}],true)}</div></div>`;
  }
  function skillUsageDetail(id){
    const record=data().skillUsage(app.getDb()).find(r=>r.skill.id===id);
    if(!record)return '';
    return `<div class="skill-dashboard">${lineChart('Activations · last 4 weeks',record.weekly.map((runs,i)=>({label:'Week '+(i+1),runs})),[{key:'runs',label:'Activations'}])}${distribution('Activation methods',[{label:'Manual',value:record.manual},{label:'Pinned',value:record.pinned},{label:'Automatic',value:record.auto}])}</div>`;
  }

  function page() {
    const s=selection(),snap=snapshot();
    const params=new URLSearchParams(location.hash.split('?')[1]||'');
    if(params.has('team')||params.get('tab')==='teams'){
      params.delete('team');params.set('tab',s.tab);
      history.replaceState(history.state,'',location.hash.split('?')[0]+'?'+params);
    }
    return `<div class="analytics-page" data-analytics-view="${s.tab}" id="analytics-panel" role="tabpanel" aria-labelledby="analytics-tab-${s.tab}">${s.tab==='contribution'?contributionPage(s):s.tab==='errors'?errors(snap,s):usage(snap,s)}</div>`;
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
      const p=prefs();
      if(key==='refresh')p.refreshed=Date.now();
      else if(['showAll','showOffenders','codes'].includes(key))p[key]=!p[key];
      else if(['metric','rank','grain','errorGrain','offenderRank'].includes(key))p[key]=value;
      app.render();
      const selector=`[data-analytics="${key}"]${value?'[data-value="'+value+'"]':''}`;
      document.querySelector(selector)?.focus({preventScroll:true});
    });
    document.addEventListener('change',event=>{const key=event.target.dataset.analyticsSelect;if(key)navigate(key,event.target.value);});
    document.addEventListener('change',async event=>{
      if(!event.target.matches('[data-contribution-import]'))return;
      const file=event.target.files[0];if(!file)return;
      const db=app.getDb();
      try {
        if(file.size>10000000)throw new Error('Choose a JSON file smaller than 10 MB.');
        const commits=data().parseCommits(await file.text());
        db.contributionCommits=commits;app.write();app.render();
        const status=document.querySelector('#contribution-status');if(status)status.textContent=`Imported ${commits.length} commit records.`;
      } catch(error) {const status=document.querySelector('#contribution-status');if(status)status.textContent=error.message;}
    });
    document.addEventListener('pointerover',event=>showTooltip(event.target));
    document.addEventListener('focusin',event=>showTooltip(event.target));
    document.addEventListener('pointerout',event=>{if(event.target.closest?.('[data-analytics-point]')&&!event.relatedTarget?.closest?.('[data-analytics-point]'))hideTooltips();});
    document.addEventListener('focusout',event=>{if(event.target.closest?.('[data-analytics-point]'))hideTooltips();});
    document.addEventListener('keydown',event=>{
      if(event.key==='Escape')hideTooltips();
      if(event.target.matches('[data-analytics-point]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
        event.preventDefault();const points=[...event.target.closest('svg').querySelectorAll('[data-analytics-point]')],index=points.indexOf(event.target);points[event.key==='Home'?0:event.key==='End'?points.length-1:Math.max(0,Math.min(points.length-1,index+(event.key==='ArrowRight'?1:-1)))].focus();
      }
      if(event.target.matches('[role=tab][data-analytics=tab]')&&['ArrowLeft','ArrowRight','Home','End'].includes(event.key)){
        event.preventDefault();const tabs=[...event.target.parentElement.querySelectorAll('[role=tab]')],index=tabs.indexOf(event.target);
        const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowRight'?1:-1)+tabs.length)%tabs.length;
        navigate('tab',tabs[next].dataset.value);
        requestAnimationFrame(()=>document.querySelector('#analytics-tab-'+tabs[next].dataset.value)?.focus());
      }
    });
    window.addEventListener('resize',()=>{clearTimeout(resizeTimer);resizeTimer=setTimeout(()=>{if(document.querySelector('.analytics-page'))app.render();},150);});
  }
  return {init,header,page,skillDashboard,skillUsageDetail};
})();
