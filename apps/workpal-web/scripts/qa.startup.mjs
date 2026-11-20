import assert from 'node:assert/strict';
import {withBrowser} from './browser-fixture.mjs';

// Real independent contexts, no authentication, retries, or synthetic responses.
await withBrowser(async ({base, newPage, expect, serverEvidence}) => {
  for (let burst = 0; burst < 6; burst++) {
    const results = await Promise.allSettled(Array.from({length:6}, async (_, index) => {
      const page = await newPage();
      const events = [];
      let active = 0, peak = 0;
      page.on('request', r => { active++; peak = Math.max(peak, active); if (r.url().includes('/app-assets/')) events.push({request:r.url()}); });
      page.on('requestfinished', () => { active--; });
      page.on('requestfailed', r => { active--; events.push({failed:r.url(),error:r.failure()}); });
      page.on('response', r => { if (r.url().includes('/app-assets/')) events.push({module:r.url(),status:r.status()}); });
      try {
        await page.goto(base);
        await expect(page.getByLabel('Username')).toBeVisible();
        assert.equal(events.filter(e => e.failed).length, 0);
        assert.ok(events.some(e => e.module?.endsWith('/features/issue-dependencies.js') && e.status === 200));
      } finally {
        console.log(JSON.stringify({burst,index,peak,events,body:await page.locator('body').innerText().catch(e => e.message)}));
        await page.context().close();
      }
    }));
    const failures = results.filter(r => r.status === 'rejected');
    assert.equal(failures.length, 0, failures.map(r => r.reason.stack).join('\n'));
    console.log('PASS startup burst', burst);
    console.log('SERVER', JSON.stringify(serverEvidence()));
  }
});
