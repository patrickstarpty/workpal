import {test} from 'node:test';
import assert from 'node:assert/strict';
import {launch} from './python-web-dev.mjs';
test('production requires a frontend build before spawning',async()=>{
 await assert.rejects(launch({mode:'production',env:{WORKPAL_DATABASE_URL:'sqlite:////tmp/unused.sqlite'},frontendDir:'/nonexistent/workpal-build'}),/build/);
});
test('requires explicit Redis configuration',async()=>{
 await assert.rejects(launch({env:{WORKPAL_DATABASE_URL:'sqlite:////tmp/unused.sqlite'}}),/REDIS_URL/);
});
test('requires explicit database configuration',async()=>{
 await assert.rejects(launch({env:{}}),/WORKPAL_DATABASE_URL/);
});
