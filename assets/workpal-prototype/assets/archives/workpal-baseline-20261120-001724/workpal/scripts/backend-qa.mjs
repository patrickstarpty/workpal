import {createRequire} from 'node:module';
import assert from 'node:assert/strict';
import {gotoWorkspace} from './qa-navigation.mjs';
const require=createRequire(import.meta.url);
let playwright;
for(const candidate of [process.env.WORKPAL_PLAYWRIGHT,'@playwright/test','/tmp/tap-browser-mj_qfqun/node_modules/@playwright/test','../multica/node_modules/@playwright/test'].filter(Boolean)){
  try{playwright=require(candidate);break;}catch(error){if(error.code!=='MODULE_NOT_FOUND')throw error;}
}
if(!playwright)throw Error('Set WORKPAL_PLAYWRIGHT to an installed @playwright/test.');
const browser=await playwright.chromium.launch();
try{
  const context=await browser.newContext(),page=await context.newPage(),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const url=process.env.WORKPAL_URL||'http://127.0.0.1:4188';
  await gotoWorkspace(page,url);
  const name='Backend QA '+Date.now();
  const id=await page.evaluate(name=>{
    const id=WorkpalStudio.createWorkspace(name);
    WorkpalStudio.selectWorkspace(id);
    WorkpalStudio.db.notes.push({text:'SQLite persistence <text>',at:Date.now()});
    if(!WorkpalStudio.save())throw Error('Save failed');
    return id;
  },name);
  // A new browser context has no browser storage to fall back to.
  const other=await browser.newContext({viewport:{width:390,height:844}}),second=await other.newPage();
  second.on('pageerror',e=>errors.push(e.message));
  await gotoWorkspace(second,url);
  assert.equal(await second.evaluate(id=>{
    WorkpalStudio.selectWorkspace(id);
    return WorkpalStudio.db.notes.at(-1).text;
  },id),'SQLite persistence <text>');
  const key='workpal.qa.'+Date.now();
  await page.evaluate(key=>WorkpalStorage.getItem(key),key);
  await second.evaluate(key=>{WorkpalStorage.getItem(key);WorkpalStorage.setItem(key,'first');},key);
  assert.equal(await page.evaluate(key=>{
    try{WorkpalStorage.setItem(key,'stale');return false;}catch(e){return e.code==='WORKSPACE_CONFLICT';}
  },key),true);
  assert.equal(await page.evaluate(key=>WorkpalStorage.getItem(key),key),'first');
  assert.deepEqual(errors,[]);
  console.log('PASS: UI boots, SQLite persists across browser contexts, narrow screen boots, stale writes are rejected.');
}finally{await browser.close();}
