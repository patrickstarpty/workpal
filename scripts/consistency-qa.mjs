import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const browser=await chromium.launch();
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(8000);
const errors=[];
page.on('pageerror',error=>errors.push(error.message));
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
try{
  await page.goto(url+'#overview');
  await page.locator('.chat-launcher [data-act=chat]').click();
  const assistant=page.locator('#assistant');
  const card=assistant.locator('.resource-body').last();
  const prompt=async text=>{await assistant.locator('[name=prompt]').fill(text);await assistant.locator('[name=prompt]').press('Enter');};
  const before=await page.evaluate(()=>({tasks:WorkpalStudio.db.tasks.length,reports:WorkpalStudio.db.reports.length}));
  await prompt('Create issue titled Generate execution report');
  await expect(card.locator('[name=title]')).toHaveValue('Generate execution report');
  expect(await page.evaluate(()=>WorkpalStudio.db.reports.length)).toBe(before.reports);
  expect(await page.evaluate(()=>WorkpalStudio.db.tasks.length)).toBe(before.tasks);
  await prompt('Do not generate a report. Explain what reports contain.');
  await expect(card.getByRole('button',{name:'Organize as an issue',exact:true})).toBeVisible();
  await expect(card).toContainText('Do not generate a report.');
  expect(await page.evaluate(()=>WorkpalStudio.db.reports.length)).toBe(before.reports);
  await prompt('The document says "Generate execution report"; keep that as a quote.');
  await expect(card.getByRole('button',{name:'Choose workspace action',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>WorkpalStudio.db.reports.length)).toBe(before.reports);
  await prompt('Generate a quality team summary');
  await expect(card.locator('form[data-form=summary]')).toBeVisible();
  expect(await page.evaluate(()=>WorkpalStudio.db.reports.length)).toBe(before.reports);
  await card.getByRole('button',{name:'Generate summary',exact:true}).click();
  expect(await page.evaluate(()=>WorkpalStudio.db.reports.length)).toBe(before.reports+1);
  await prompt('Please double-check the release owner');
  await expect(card).toContainText('Please double-check the release owner');
  await expect(card.getByRole('button',{name:'Organize as an issue',exact:true})).toBeVisible();
  expect(await page.evaluate(()=>WorkpalStudio.db.runs[0].status)).toBe('finished');
  await assistant.getByRole('button',{name:'Close chat',exact:true}).click();

  await page.evaluate(()=>{
    WorkpalStudio.db.views.push({id:'VIEW-QA',name:'QA board view',status:'',owner:'',query:'',layout:'board'});
    WorkpalStudio.db.issueDisplay={layout:'list',hidden:[],collapsed:[],properties:['priority','project','assignee','due','children']};
    WorkpalStudio.save();
  });
  await page.goto(url+'#views');
  await page.getByRole('button',{name:'QA board view All statuses',exact:true}).click();
  await expect(page.getByRole('region',{name:'Issue board'}).or(page.locator('.board'))).toBeVisible();
  await page.reload();
  await expect(page.locator('.board')).toBeVisible();

  await page.evaluate(()=>{
    const task={id:'QA-INBOX',title:'Nested reply notification',project:'TAP',owner:'Patrick',status:'todo',priority:'Normal',team:'quality',stage:0,checks:[],subscribed:true,
      activity:[{id:'qa-thread',kind:'comment',text:'Original comment',author:'Patrick',at:100,replies:[{id:'qa-reply-1',text:'First nested reply',author:'Reviewer',at:200}]}]};
    WorkpalStudio.db.tasks.push(task);
    WorkpalStudio.db.inbox[task.id]={readAt:100};
    WorkpalStudio.save();
  });
  await page.goto(url+'#inbox');
  const notification=page.locator('.notification').filter({hasText:'Nested reply notification'});
  await expect(notification).toContainText('First nested reply');
  await notification.getByRole('button',{name:'Mark read',exact:true}).click();
  await expect(notification.getByRole('button',{name:'Mark unread',exact:true})).toBeVisible();
  await page.evaluate(()=>{
    WorkpalStudio.db.tasks.find(t=>t.id==='QA-INBOX').activity[0].replies.push({id:'qa-reply-2',text:'Second reply in the same millisecond',author:'Reviewer',at:200});
    WorkpalStudio.save();
  });
  await page.reload();
  await expect(notification).toContainText('Second reply in the same millisecond');
  await notification.getByRole('button',{name:'Mark read',exact:true}).click();
  await expect(notification.getByRole('button',{name:'Mark unread',exact:true})).toBeVisible();
  await notification.getByRole('button',{name:'Archive',exact:true}).click();
  await expect(notification).toHaveCount(0);
  await page.evaluate(()=>{
    WorkpalStudio.db.tasks.find(t=>t.id==='QA-INBOX').activity[0].replies.push({id:'qa-reply-3',text:'New reply after archive',author:'Reviewer',at:200});
    WorkpalStudio.save();
  });
  await page.reload();
  await expect(notification).toContainText('New reply after archive');

  const reviewId=await page.evaluate(()=>{
    const s=WorkpalStudio,db=s.db;
    db.workflows.push({id:'FLOW-QA',name:'QA review workflow',steps:[{status:'review',owner:'Quality partner',instructions:'Inspect source and gaps.',next:'done',rejected:'active'}]});
    db.projectSettings.find(p=>p.project==='TAP').workflowId='FLOW-QA';
    const issue={id:'QA-REVIEW',title:'Record review findings',description:'Check review note capture.',project:'TAP',owner:'Engineering partner',status:'todo',priority:'Normal',team:'engineering',stage:0,checks:['Attach evidence'],activity:[]};
    db.tasks.push(issue);
    const run=s.start(issue,'brainstorming');
    s.changeRun(run,'deliver','Ready for inspection',{artifacts:[{title:'Draft',body:'Reviewer reference'}],evidence:[]});
    return db.runs.find(r=>r.task===issue.id&&r.kind==='review').id;
  });
  await page.goto(url+'#workflow?id='+reviewId);
  await page.getByRole('button',{name:/Start (?:offline walkthrough|execution|run)/,exact:true}).click();
  await page.getByLabel('Review findings',{exact:true}).fill('Need a source reference for the acceptance criterion.');
  const count=await page.evaluate(()=>WorkpalStudio.db.deliveries.length);
  await page.getByRole('button',{name:'Save review note',exact:true}).click();
  await expect(page.locator('main')).toContainText('Need a source reference for the acceptance criterion.');
  expect(await page.evaluate(()=>WorkpalStudio.db.deliveries.length)).toBe(count);
  expect(await page.evaluate(()=>WorkpalStudio.db.tasks.find(t=>t.id==='QA-REVIEW').status)).toBe('review');

  await page.goto(url+'#auto');
  await page.getByRole('button',{name:'New autopilot',exact:true}).click();
  const dialog=page.locator('#dialog');
  await dialog.getByLabel('Name',{exact:true}).fill('QA summary autopilot');
  await dialog.getByLabel('Runbook',{exact:true}).fill('Summarize release decisions and unresolved questions.');
  await dialog.locator('[name=project]').selectOption('TAP');
  await dialog.locator('[name=checks]').fill('List release decisions and their sources\nList unresolved questions');
  await expect(dialog).toContainText('only while this workspace is selected');
  await dialog.getByRole('button',{name:'Save autopilot',exact:true}).click();
  await page.getByRole('button',{name:'Run now',exact:true}).click();
  const generated=await page.evaluate(()=>{
    const s=WorkpalStudio,a=s.db.autopilots.find(a=>a.name==='QA summary autopilot'),event=a.history[0];
    return {checks:s.db.tasks.find(t=>t.id===event.task).checks,snapshot:s.db.runs.find(r=>r.id===event.run).inputSnapshot.task.checks};
  });
  expect(generated.checks).toEqual(['List release decisions and their sources','List unresolved questions']);
  expect(generated.snapshot).toEqual(generated.checks);
  await expect(page.locator('main')).toContainText('Scheduled checks pause');
  expect(errors).toEqual([]);
  console.log('PASS consistency QA: safe chat parsing, explicit reports, saved board views, nested Inbox updates, review notes, Autopilot criteria and schedule boundary.');
}finally{await browser.close();}
