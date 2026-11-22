// Catalog acquisition only. Remote skill instructions are never executed.
import {mkdir, writeFile} from 'node:fs/promises';
import {parse} from 'yaml';
const repo='garrytan/gstack';
const response=await fetch(`https://api.github.com/repos/${repo}/git/trees/main?recursive=1`);
if(!response.ok)throw new Error(`Tree request: ${response.status}`);
const tree=await response.json();
if(tree.truncated)throw new Error('Incomplete repository tree');
const all=tree.tree.filter(entry=>entry.type==='blob'&&/(^|\/)SKILL\.md$/.test(entry.path));
const excluded=all.filter(e=>e.path.startsWith('test/')).map(e=>({path:e.path,reason:'Test fixture, not a distributed skill'}));
const entries=all.filter(e=>!e.path.startsWith('test/'));
const rows=[];let cursor=0;
await Promise.all(Array.from({length:6},async()=>{
 while(cursor<entries.length){
  const entry=entries[cursor++];
  const url=`https://raw.githubusercontent.com/${repo}/${tree.sha}/${entry.path}`;
  const r=await fetch(url);if(!r.ok)throw new Error(`${entry.path}: ${r.status}`);
  const text=await r.text();
  const match=text.match(/^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)/);
  const meta=match?parse(match[1]):{};
  const fallbackName=entry.path==='SKILL.md'?'gstack':entry.path.split('/').at(-2);
  const description=String(meta.description||text.replace(match?.[0]||'','').split('\n').find(line=>line.trim()&&!line.startsWith('#'))||'');
  if(!description.trim())throw new Error(`Missing description: ${entry.path}`);
  rows.push({id:`gstack:${entry.path}`,name:String(meta.name||fallbackName),description,path:entry.path,url:`https://github.com/${repo}/blob/${tree.sha}/${entry.path}`,blobSha:entry.sha,scope:/^(openclaw|capy|qm)\//.test(entry.path)?'variant':entry.path.startsWith('browser-skills/')?'browser-skill':'skill',...(meta.name&&meta.description?{}:{metadataFallback:true})});
 }
}));
rows.sort((a,b)=>a.path.localeCompare(b.path));
const result={source:{id:'gstack',label:'gstack',author:'Garry Tan',repo,commitSha:tree.sha,repositoryUrl:`https://github.com/${repo}`,retrievedAt:new Date().toISOString(),licenseUrl:`https://github.com/${repo}/blob/${tree.sha}/LICENSE`,licenseSummary:'MIT'},skills:rows,excluded};
await mkdir(new URL('./sources/',import.meta.url),{recursive:true});
await writeFile(new URL('./sources/gstack.json',import.meta.url),JSON.stringify(result,null,2)+'\n');
console.log(JSON.stringify({source:repo,commit:tree.sha,records:rows.length,variants:rows.filter(r=>r.scope==='variant').length,excluded}));
