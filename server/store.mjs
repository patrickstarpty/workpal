import {seedContribution} from './contribution.mjs';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync} from 'node:fs';
import {dirname} from 'node:path';
import {fixture,originalIssues} from './fixtures.mjs';
export function openStore(path) {
  if(path!==':memory:')mkdirSync(dirname(path),{recursive:true});
  const db=new DatabaseSync(path);
  db.exec('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL,id TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(kind,id)); CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY,value TEXT);');
  let closed=false;
  const store={
    list:kind=>db.prepare('SELECT body FROM records WHERE kind=? ORDER BY rowid').all(kind).map(r=>JSON.parse(r.body)),
    get:(kind,id)=>{const r=db.prepare('SELECT body FROM records WHERE kind=? AND id=?').get(kind,id);return r?JSON.parse(r.body):null;},
    put:(kind,record)=>{db.prepare('INSERT INTO records VALUES (?,?,?) ON CONFLICT(kind,id) DO UPDATE SET body=excluded.body').run(kind,record.id,JSON.stringify(record));return record;},
    remove:(kind,id)=>db.prepare('DELETE FROM records WHERE kind=? AND id=?').run(kind,id).changes,
    close:()=>{if(!closed){db.close();closed=true;}},
  };
  if(!db.prepare("SELECT value FROM meta WHERE key='seeded'").get()) {
    db.exec('BEGIN');
    try { for(const [kind,rows] of Object.entries(fixture))for(const row of rows)store.put(kind,row);db.exec("INSERT INTO meta VALUES ('seeded','1'); COMMIT"); }
    catch(error){db.exec('ROLLBACK');db.close();throw error;}
  }
  if(!db.prepare("SELECT value FROM meta WHERE key='rich-mock-v1'").get()) {
    db.exec('BEGIN');
    try {
      for(const original of originalIssues) {
        const current=store.get('issues',original.id), enriched=fixture.issues.find(r=>r.id===original.id);
        if(current&&(!current.description||current.description===original.description))store.put('issues',{...current,description:enriched.description,created_at:current.created_at===original.created_at?enriched.created_at:current.created_at});
      }
      for(const kind of ['comments','analytics_runs'])for(const row of fixture[kind]) {
        if(store.get('issues',row.issue_id)&&(!row.project_id||store.get('projects',row.project_id))&&!store.get(kind,row.id))store.put(kind,row);
      }
      db.exec("INSERT INTO meta VALUES ('rich-mock-v1','1'); COMMIT");
    }catch(error){db.exec('ROLLBACK');db.close();throw error;}
  }
  if(!store.get('contribution_data','workspace'))store.put('contribution_data',{id:'workspace',commits:seedContribution()});
  return store;
}
