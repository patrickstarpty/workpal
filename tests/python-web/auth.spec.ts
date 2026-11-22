import {test,expect} from '@playwright/test';

test.use({trace:'on',screenshot:'only-on-failure'});

test('live Python auth, membership routing and session expiration',async({page,context})=>{
 const forbidden:string[]=[];let verifies=0;
 page.on('request',r=>{if(r.url().includes('/api/bootstrap'))forbidden.push(r.url());if(r.url().includes('verify-code'))verifies++;});
 await page.goto('/');
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('dev@workpal.local');
 await expect(page.getByLabel('Verification code')).toHaveCount(0);
 await expect(page.getByRole('textbox')).toHaveCount(1);
 expect(verifies).toBe(0);
 await page.getByLabel('Email',{exact:true}).fill('unsupported@example.test');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('alert')).toContainText('Unable to sign in');
 await page.getByLabel('Email',{exact:true}).fill('dev@workpal.local');
 const login=page.waitForResponse(r=>r.url().includes('verify-code')&&r.status()===200);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();await login;
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Choose a workspace'})).toBeVisible();
 const slug='acceptance-'+Date.now();
 await page.getByLabel('Name',{exact:true}).fill('Private acceptance workspace');
 await page.getByLabel('Workspace URL').fill(slug);
 await page.getByRole('button',{name:'Create workspace',exact:true}).click();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await expect(page).toHaveURL(new RegExp('#/'+slug+'/'));
 await page.goto('/#/'+slug+'/projects/deep-link');await page.reload();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await expect(page).toHaveURL(new RegExp('#/'+slug+'/'));
 await page.goto('/#/unowned-private/projects');
 await expect(page.getByText('This workspace is unavailable or you do not have access.')).toBeVisible();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toHaveCount(0);
 const cookies=await context.cookies();const csrf=cookies.find(c=>c.name==='workpal_csrf_session')||cookies.find(c=>c.name==='workpal_csrf');
 expect(csrf).toBeTruthy();
 const second=slug+'-second';
 const response=await context.request.post('/api/workspaces',{data:{name:'Second acceptance workspace',slug:second},headers:{'X-CSRF-Token':csrf!.value}});
 expect(response.status(),await response.text()).toBe(201);
 await page.goto('/#/'+slug+'/projects/old-resource');
 await page.getByRole('button', {name: 'Switch workspace', exact: true}).click();
 await page.getByRole('menuitem', {name: /Second acceptance workspace/}).click();
 await expect(page).toHaveURL(new RegExp('/'+second+'/issues$'));
 await context.clearCookies();
 await page.reload();
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toHaveCount(0);
 await expect(page.getByText('Private acceptance workspace',{exact:true})).toHaveCount(0);
 expect(forbidden).toEqual([]);
});

for(const failure of ['capability disabled','config transport failure'])test('intercepted config only: '+failure,async({page})=>{
 let submits=0;page.on('request',r=>{if(r.url().includes('verify-code'))submits++;});
 await page.route('**/api/config',route=>failure==='capability disabled'?route.fulfill({json:{development_auth:false}}):route.abort('failed'));
 await page.goto('/');
 await expect(page.getByLabel('Email',{exact:true})).toHaveValue('');
 await expect(page.getByLabel('Verification code')).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeDisabled();
 if(failure==='config transport failure')await expect(page.getByRole('button',{name:'Retry sign-in options'})).toBeVisible();
 expect(submits).toBe(0);
});

for(const action of ['logout','background401'] as const)test('live core session: '+action,async({page,context})=>{
 await page.goto('/');
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Choose a workspace'})).toBeVisible();
 const slug='session-'+action+'-'+Date.now();
 const csrf=(await context.cookies()).find(c=>c.name==='workpal_csrf_session')||(await context.cookies()).find(c=>c.name==='workpal_csrf');
 expect(csrf).toBeTruthy();
 const created=await context.request.post('/api/workspaces',{data:{name:slug,slug},headers:{'X-CSRF-Token':csrf!.value}});
 expect(created.status(),await created.text()).toBe(201);
 await page.goto('/#/'+slug+'/projects');
 await page.reload();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await expect(page).toHaveURL(new RegExp('#/'+slug+'/'));
 await expect(page.getByRole('button',{name:'Account',exact:true})).toBeVisible();
 const timeOrigin=await page.evaluate(()=>performance.timeOrigin);
 if(action==='logout'){
  await page.getByRole('button',{name:'Account',exact:true}).click();
  const loggedOut=page.waitForResponse(r=>r.url().includes('/auth/logout')&&r.request().method()==='POST');
  await page.getByRole('menuitem',{name:'Log out',exact:true}).click();
  expect((await loggedOut).status()).toBe(200);
  expect((await context.cookies()).filter(c=>c.name==='workpal_auth')).toEqual([]);
 }else{
  await context.setOffline(true);
  await expect.poll(()=>page.evaluate(()=>navigator.onLine)).toBe(false);
  await context.clearCookies();
  const unauthorized=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/workspaces'&&r.status()===401);
  await context.setOffline(false);
  await unauthorized;
 }
 await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toHaveCount(0);
 await expect(page.getByRole('button',{name:'Account',exact:true})).toHaveCount(0);
 await expect(page.getByText(slug,{exact:true})).toHaveCount(0);
 if(action==='background401')expect(await page.evaluate(()=>performance.timeOrigin)).toBe(timeOrigin);
});
