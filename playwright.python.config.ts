import {defineConfig} from '@playwright/test';
import {mkdtempSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {randomBytes} from 'node:crypto';
const state=mkdtempSync(join(tmpdir(),'workpal-python-browser-'));
const port=process.env.WORKPAL_WEB_PORT||'24174';
export default defineConfig({
 testDir:'./tests/python-web', testMatch:'**/*.spec.ts', workers:1,
 use:{baseURL:`http://127.0.0.1:${port}`},
 webServer:{command:'node scripts/python-web-dev.mjs',url:`http://127.0.0.1:${port}`,reuseExistingServer:false,timeout:60000,
 gracefulShutdown:{signal:'SIGTERM',timeout:5000},
 env:{...process.env,WORKPAL_PORT:process.env.WORKPAL_PORT||'24175',WORKPAL_WEB_PORT:port,
 WORKPAL_DATABASE_URL:process.env.WORKPAL_DATABASE_URL||`sqlite:///${join(state,'test.sqlite')}`,
 WORKPAL_UPLOAD_DIR:process.env.WORKPAL_UPLOAD_DIR||join(state,'uploads'),
 REDIS_KEY_PREFIX:process.env.REDIS_KEY_PREFIX||`workpal:test:${randomBytes(12).toString('hex')}:`,
 WORKPAL_DEV_AUTH:'true',WORKPAL_ENV:'development',WORKPAL_HOST:'127.0.0.1',AUTH_SECRET:process.env.AUTH_SECRET||randomBytes(32).toString('hex')}}
});
