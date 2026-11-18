// Historical usage for the offline Analytics interface. TAP starts with authored
// fixture records, not observed provider usage or actual agent execution. Keep
// these records separate from operational issues, runs and delivery evidence.
globalThis.WorkpalAnalyticsData = (() => {
  'use strict';
  const failureLabels = Object.freeze({
    auth:'Auth', rate_limit:'Rate limit', timeout:'Timeout', provider:'Provider',
    runtime:'Runtime', agent:'Agent', other:'Other',
  });
  const failureReasons = {
    auth:'agent_error.provider_auth_or_access',
    rate_limit:'agent_error.provider_rate_limit',
    timeout:'run_timeout',
    provider:'agent_error.provider_unavailable',
    runtime:'runtime_offline',
    agent:'agent_error.context_overflow',
    other:'unknown_error',
  };
  const zeroClasses = () => Object.fromEntries(Object.keys(failureLabels).map(key=>[key,0]));
  const finite = value => Number.isFinite(Number(value)) ? Math.max(0,Number(value)) : 0;
  const stamp = value => typeof value==='number' ? value : Date.parse(value);
  function localDay(value){const date=new Date(value);date.setHours(0,0,0,0);return date;}
  function addDays(value,days){const date=new Date(value);date.setDate(date.getDate()+days);return date;}
  function dateKey(value){const date=new Date(value);return `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,'0')}-${String(date.getDate()).padStart(2,'0')}`;}
  function monday(value){const date=localDay(value);date.setDate(date.getDate()-(date.getDay()+6)%7);return date;}
  const shortDate = value => new Date(value).toLocaleDateString('en-US',{month:'short',day:'numeric'});
  const numberKeys=['input','output','cacheRead','cacheWrite','tokens','cost','seconds','runs','completed','failed'];
  function bucket(value){return {key:dateKey(value),date:dateKey(value),label:shortDate(value),...Object.fromEntries(numberKeys.map(key=>[key,0])),classes:zeroClasses(),partial:false};}
  function add(target,values){
    for(const key of numberKeys)target[key]=(target[key]||0)+(values[key]||0);
    for(const key of Object.keys(failureLabels))target.classes[key]+=values.classes[key]||0;
  }

  function fixtureRecords(now){
    const roster=[
      ['Product partner','product'],['Architecture partner','engineering'],
      ['Engineering partner','engineering'],['Quality partner','quality'],
    ];
    const result=[],today=localDay(now),classes=Object.keys(failureLabels);
    for(let offset=89;offset>=0;offset--){
      const day=addDays(today,-offset),index=89-offset,weekend=[0,6].includes(day.getDay());
      const volume=weekend?2+(index%2):4+(index%4)+Math.floor(index/25);
      for(let n=0;n<volume;n++){
        const when=new Date(day);when.setHours(8+Math.floor(n*10/volume),(index*13+n*17)%60,0,0);
        if(when.getTime()>now)continue;
        const agentIndex=(index*3+n)%roster.length,[agent,team]=roster[agentIndex];
        const weight=[0.8,1.1,1.65,1][agentIndex],wave=0.8+(index%9)/10;
        const input=Math.round((12000+index*160+n*1370)*weight*wave);
        const output=Math.round(input*(0.12+agentIndex*0.025));
        const cacheRead=Math.round(input*(0.2+(index%5)*0.09));
        const cacheWrite=Math.round(input*0.045);
        const failed=(index*7+n*11)%17===0;
        const failureClass=classes[(index+n)%classes.length];
        result.push({
          id:`usage-${dateKey(day)}-${n+1}`,at:when.getTime(),agent,team,
          project:(index+n)%13===0?'':'TAP',input,output,cacheRead,cacheWrite,
          // Authored display values: no current provider prices are implied.
          cost:Math.round((0.025+agentIndex*0.026+index*0.0009+n*0.007)*wave*10000)/10000,
          seconds:Math.round((55+index*2+n*23)*weight),
          status:failed?'failed':'completed',
          ...(failed?{failureClass,reason:failureReasons[failureClass]}:{}),
        });
      }
    }
    return result;
  }

  function ensure(db,workspaceId,now=Date.now()){
    // Preserve authored, imported or previously seeded data, including an empty
    // history. Revisiting the page never moves fixture dates or refills a reset.
    if(Object.hasOwn(db,'analyticsHistory'))return false;
    const at=Number.isFinite(now)?now:Date.now();
    db.analyticsHistory={version:1,source:workspaceId==='tap'?'fixture':'workspace',asOf:at,
      records:workspaceId==='tap'?fixtureRecords(at):[]};
    return true;
  }

  function snapshot(db,{days=30,project='',team='',now=Date.now()}={}){
    const at=Number.isFinite(now)?now:Date.now();
    const range=Number.isFinite(Number(days))?Math.min(365,Math.max(1,Math.floor(Number(days)))):30;
    const today=localDay(at),start=addDays(today,1-range);
    const history=db.analyticsHistory,stored=Array.isArray(history?.records)?history.records:[];
    const records=stored.filter(record=>{
      const when=stamp(record.at);
      return Number.isFinite(when)&&when>=start.getTime()&&when<=at&&
        (!project||record.project===project)&&(!team||record.team===team)&&
        ['completed','failed'].includes(record.status);
    }).map(record=>{
      const copy={...record,at:stamp(record.at)};
      for(const key of ['input','output','cacheRead','cacheWrite','cost','seconds'])copy[key]=finite(record[key]);
      if(copy.status==='failed'){
        copy.failureClass=Object.hasOwn(failureLabels,copy.failureClass)?copy.failureClass:'other';
        copy.reason=typeof copy.reason==='string'&&copy.reason.trim()?copy.reason:'unknown_error';
      }
      return copy;
    }).sort((a,b)=>a.at-b.at);
    const dayMap=new Map(),weekMap=new Map(),agentMap=new Map(),reasonMap=new Map();
    for(let day=new Date(start);day<=today;day=addDays(day,1))dayMap.set(dateKey(day),bucket(day));
    const total=bucket(today);
    for(const record of records){
      const values={...record,tokens:record.input+record.output+record.cacheRead+record.cacheWrite,
        runs:1,completed:Number(record.status==='completed'),failed:Number(record.status==='failed'),classes:zeroClasses()};
      if(values.failed)values.classes[record.failureClass]=1;
      add(total,values);add(dayMap.get(dateKey(record.at)),values);
      const name=typeof record.agent==='string'&&record.agent?record.agent:'Unknown agent';
      if(!agentMap.has(name))agentMap.set(name,{name,team:record.team||'unassigned',cost:0,tokens:0,seconds:0,runs:0,failed:0,classes:zeroClasses()});
      const agent=agentMap.get(name);add(agent,values);
      if(agent.team!==(record.team||'unassigned'))agent.team='';
      if(values.failed){
        const key=record.failureClass+'|'+record.reason;
        if(!reasonMap.has(key))reasonMap.set(key,{key:record.reason,label:record.reason,count:0,class:record.failureClass});
        reasonMap.get(key).count++;
      }
    }
    for(const day of dayMap.values()){
      const weekStart=monday(new Date(day.date+'T00:00:00')),key=dateKey(weekStart);
      if(!weekMap.has(key)){
        const week=bucket(weekStart),last=addDays(weekStart,6);
        week.partial=addDays(weekStart,7).getTime()>at;
        week.label=shortDate(weekStart)+' – '+shortDate(last);
        week.days=Math.min(7,Math.round((localDay(at).getTime()-weekStart.getTime())/86400000)+1);
        weekMap.set(key,week);
      }
      add(weekMap.get(key),day);
    }
    const agents=[...agentMap.values()].map(agent=>({...agent,failureRate:agent.runs?100*agent.failed/agent.runs:0})).sort((a,b)=>b.tokens-a.tokens||a.name.localeCompare(b.name));
    const totals=Object.fromEntries(['cost','tokens','input','output','cacheRead','cacheWrite','seconds','runs','failed'].map(key=>[key,total[key]]));
    totals.affected=agents.filter(agent=>agent.failed>0).length;
    return {records,totals,agents,daily:[...dayMap.values()],weekly:[...weekMap.values()],
      classes:Object.entries(failureLabels).map(([key,label])=>({key,label,count:total.classes[key]})).filter(row=>row.count>0).sort((a,b)=>b.count-a.count),
      reasons:[...reasonMap.values()].sort((a,b)=>b.count-a.count||a.key.localeCompare(b.key)),
      asOf:Number.isFinite(history?.asOf)?history.asOf:at};
  }

  const compact=value=>new Intl.NumberFormat('en-US',{notation:'compact',maximumFractionDigits:1}).format(finite(value));
  const money=value=>new Intl.NumberFormat('en-US',{style:'currency',currency:'USD',minimumFractionDigits:2,maximumFractionDigits:2}).format(finite(value));
  const rate=(failed,total)=>`${total>0?(100*finite(failed)/finite(total)).toFixed(1):'0'}%`;
  function duration(value){
    const seconds=Math.round(finite(value));
    if(seconds<60)return `${seconds}s`;
    if(seconds<3600)return `${Math.floor(seconds/60)}m${seconds%60?' '+seconds%60+'s':''}`;
    const hours=Math.floor(seconds/3600),minutes=Math.floor(seconds%3600/60);
    return `${hours}h${minutes?' '+minutes+'m':''}`;
  }
  return Object.freeze({ensure,snapshot,compact,duration,rate,money,failureLabels});
})();
