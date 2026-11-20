import {test} from 'node:test';
import assert from 'node:assert/strict';
import {migrateStorage} from '../apps/web/app/storage-migration.js';
test('brand storage migration copies drafts without overwriting either version',()=>{
 const old='multi'+'ca';const values={[old+'-draft']:'review note',[old+'-theme']:'dark','workpal-theme':'light'};
 const storage={...values};Object.defineProperties(storage,{getItem:{value:k=>storage[k]??null},setItem:{value:(k,v)=>storage[k]=v}});
 migrateStorage(storage);migrateStorage(storage);
 assert.equal(storage['workpal-draft'],'review note');assert.equal(storage[old+'-draft'],'review note');assert.equal(storage['workpal-theme'],'light');
});
