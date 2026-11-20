import {test} from 'node:test';
import assert from 'node:assert/strict';
import {resolve} from 'node:path';
import {sync} from './sync.mjs';
test('Workpal SVG copies match the canonical assets',async()=>assert.deepEqual(await sync(resolve(import.meta.dirname,'../..'),{check:true}),[]));
