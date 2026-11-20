import {test} from 'node:test';
import assert from 'node:assert/strict';
import {createClient} from '../src/client.js';

const json = value => new Response(JSON.stringify(value));
async function pendingRequest() {
  let release, started;
  const ready = new Promise(resolve => {started=resolve;});
  const response = new Promise(resolve => {release=resolve;});
  const lost = [];
  const client = createClient({onAccessLost:e=>lost.push(e), fetchImpl:async path => {
    if (path.endsWith('/auth/session')) return json({user:{id:1,username:'owner'},workspaces:[
      {id:1,name:'First',revision:1,role:'owner'}, {id:2,name:'Second',revision:1,role:'owner'}]});
    if (path.endsWith('/auth/csrf')) return json({csrf_token:'token'});
    started(); return response;
  }});
  await client.loadSession(); client.selectWorkspace(1);
  const checked = assert.rejects(client.perform('issue.create',{title:'Saved'},{key:'intent'}),
    error=>error.code==='context_changed' && error.outcome==='unknown');
  await ready; client.selectWorkspace(2);
  return {client,release,checked,lost};
}

test('discarding a late response cancels its unread body without parsing or reporting its permission error', async () => {
  for (const status of [200,403]) {
    const pending=await pendingRequest(); let cancelled=false;
    const response=new Response(new ReadableStream({cancel(){cancelled=true;}}),{status});
    response.json=()=>{throw Error('Stale body must not be parsed');};
    pending.release(response); await pending.checked;
    assert.equal(cancelled,true,'unread response must release its stream');
    assert.deepEqual(pending.lost,[]);
    assert.equal(pending.client.selectWorkspace(2).id,2);
  }
});

test('failed or unresolved stale-body cancellation cannot block the current context', async () => {
  for (const cleanup of [()=>Promise.reject(Error('closed stream')),()=>new Promise(()=>{})]) {
    const pending=await pendingRequest(); let called=false;
    pending.release(new Response(new ReadableStream({cancel(){called=true;return cleanup();}})));
    await pending.checked;
    assert.equal(called,true);
    assert.deepEqual(pending.lost,[]);
  }
});
