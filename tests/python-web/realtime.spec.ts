import {test,expect, type WebSocket} from '@playwright/test';

test.use({trace:'on',screenshot:'on'});

test('committed workspace update reaches built-in socket and logout closes it',async({page,context},testInfo)=>{
 const frames:unknown[]=[];
 await page.addInitScript(() => {
  const Native = window.WebSocket;
  (window as any).__acceptanceSockets = [];
  window.WebSocket = class extends Native {
   constructor(url: string | URL, protocols?: string | string[]) {
    super(url, protocols);
    (window as any).__acceptanceSockets.push(this);
   }
  };
 });
 const cdp=await context.newCDPSession(page);
 await cdp.send('Network.enable');
 const socketUrls=new Map<string,string>();
 const upgraded=new Set<string>();
 cdp.on('Network.webSocketCreated',event=>socketUrls.set(event.requestId,event.url));
 cdp.on('Network.webSocketHandshakeResponseReceived',event=>{
  const url=socketUrls.get(event.requestId);
  if(url&&event.response.status===101)upgraded.add(url);
 });
 let socket:WebSocket|undefined;
 let closed=false;
 page.on('websocket',ws=>{
  if(!ws.url().includes('/ws'))return;
  socket=ws;
  ws.on('framereceived',event=>{try{frames.push(JSON.parse(event.payload.toString()));}catch{frames.push(event.payload.toString());}});
  ws.on('close',()=>{closed=true;});
 });
 await page.goto('/');
 const loginResponse=page.waitForResponse(r=>r.url().includes('verify-code')&&r.status()===200);
 await page.getByRole('button',{name:'Sign in',exact:true}).click();
 const login=await (await loginResponse).json();
 await expect(page.getByRole('button',{name:'Enter Workspace',exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Enter Workspace',exact:true}).click();
 await expect(page.getByRole('heading',{name:'Choose a workspace'})).toBeVisible();
 const slug='realtime-'+Date.now();
 await page.getByLabel('Name',{exact:true}).fill('Realtime acceptance');
 await page.getByLabel('Workspace URL').fill(slug);
 const creation=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname==='/api/workspaces');
 await page.getByRole('button',{name:'Create workspace',exact:true}).click();
 const workspace=await (await creation).json();
 await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toBeVisible();
 await expect.poll(()=>[...upgraded].some(url=>new URL(url).pathname==='/ws'&&new URL(url).searchParams.get('workspace_slug')===slug)).toBe(true);
 expect(socket?.url()).toContain('workspace_slug='+slug);
 const csrf=(await context.cookies()).find(c=>c.name==='workpal_csrf_session')||(await context.cookies()).find(c=>c.name==='workpal_csrf');
 expect(csrf).toBeTruthy();
 try{
  const response=await context.request.put('/api/workspaces/'+workspace.id,{headers:{'X-CSRF-Token':csrf!.value},data:{name:'Realtime renamed '+slug}});
  expect(response.status(),await response.text()).toBe(200);
  const updated=await response.json();
  await expect.poll(()=>frames.filter((f:any)=>f.type==='workspace:updated'),{timeout:15000}).toEqual([{type:'workspace:updated',payload:{workspace:updated},actor_id:login.user.id,actor_type:'member'}]);
  const previousSocket = socket;
  await page.evaluate(() => (window as any).__acceptanceSockets.forEach((ws: WebSocket) => ws.close()));
  await expect.poll(() => socket !== previousSocket && !!socket, {timeout:15000}).toBe(true);
  closed = false;
  const again = await context.request.put('/api/workspaces/'+workspace.id,{headers:{'X-CSRF-Token':csrf!.value},data:{name:'Reconnected '+slug}});
  expect(again.status()).toBe(200);
  const reconnected = await again.json();
  await expect.poll(()=>frames.filter((f:any)=>f.type==='workspace:updated').length,{timeout:15000}).toBe(2);
  expect((frames.filter((f:any)=>f.type==='workspace:updated')[1] as any).payload.workspace).toEqual(reconnected);
  await page.getByRole('button', {name: 'Switch workspace', exact: true}).click();
  await expect(page.getByRole('menuitem', {name: reconnected.name}).getByText(reconnected.name, {exact:true})).toBeVisible();
  await page.keyboard.press('Escape');
  await page.screenshot({path:testInfo.outputPath('realtime-updated.png')});
  await page.getByRole('button',{name:'Account',exact:true}).click();
  await page.getByRole('menuitem',{name:'Log out',exact:true}).click();
  await expect.poll(()=>closed).toBe(true);
  await expect(page.getByRole('button',{name:'Sign in',exact:true})).toBeVisible();
  await expect(page.getByRole('button', {name: 'Switch workspace', exact: true})).toHaveCount(0);
  await expect(page.getByRole('button',{name:'Account',exact:true})).toHaveCount(0);
 }finally{
  await testInfo.attach('actual-socket-frames',{body:JSON.stringify(frames,null,2),contentType:'application/json'});
 }
});
