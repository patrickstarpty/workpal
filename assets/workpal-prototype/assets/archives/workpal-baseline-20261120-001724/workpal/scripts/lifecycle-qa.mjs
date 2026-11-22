import {gotoWorkspace,reloadWorkspace} from './qa-navigation.mjs';
import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {mkdir} from 'node:fs/promises';

const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
await mkdir('test-results',{recursive:true});
const failures=[];
try {
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:900}});
    const page=await context.newPage();
    page.setDefaultTimeout(8000);
    const errors=[],remoteRequests=[];
    page.on('pageerror',error=>errors.push(error.message));
    page.on('request',request=>{if(/^https?:/.test(request.url()))remoteRequests.push(request.url());});
    const editor=page.locator('#dialog');
    async function fixture(name,{workflow=false,status='todo',running=false}={}){
      return page.evaluate(({name,workflow,status,running})=>{
        const studio=WorkpalStudio,config=studio.db.projectSettings.find(p=>p.project==='TAP');
        if(workflow){
          if(!studio.db.workflows.some(w=>w.id==='QA-LIFECYCLE'))studio.db.workflows.push({id:'QA-LIFECYCLE',name:'Lifecycle QA',steps:[
            {status:'todo',owner:'Engineering partner',instructions:'Implement requested behavior.',next:'review'},
            {status:'review',owner:'Quality partner',instructions:'Check the submitted evidence.',next:'done',rejected:'active'}
          ]});
          config.workflowId='QA-LIFECYCLE';
        }else config.workflowId='default';
        const {task}=studio.assignWork('Engineering partner',{title:name,project:'TAP',description:'Preserve progress on reconnect.',checks:['Keep the upload offset'],status,queueRun:false});
        const run=running?studio.start(task,'brainstorming'):null;
        studio.save();return {task:task.id,run:run?.id};
      },{name,workflow,status,running});
    }
    async function openIssue(id){await gotoWorkspace(page,url+'#tasks?id='+encodeURIComponent(id));}
    async function openRun(id){await gotoWorkspace(page,url+'#workflow?id='+encodeURIComponent(id));}
    async function editStatus(id,status){
      await openIssue(id);
      await page.locator('[data-id="issueProperty|'+id+'|status"]').click();
      await editor.locator('[name=status]').selectOption(status);
    }
    async function deliver(runId,summary){
      return page.evaluate(({runId,summary})=>{
        const run=WorkpalStudio.db.runs.find(r=>r.id===runId);
        WorkpalStudio.changeRun(run,'deliver',summary,{artifacts:[{title:'Reviewer supplied notes',body:'Recorded behavior and evidence, entered by the reviewer.'}],evidence:run.inputSnapshot.task.checks.map(criterion=>({criterion,evidence:'Recorded reference for '+criterion})),limitations:'No external checks performed.'});
        return WorkpalStudio.db.deliveries.find(d=>d.run===runId).id;
      },{runId,summary});
    }
    async function approveCurrent(){
      await page.locator('form[data-form=decision] [name=choice]').selectOption('approve');
      await page.locator('form[data-form=decision] [name=acknowledged]').check();
      await page.getByRole('button',{name:'Record decision',exact:true}).click();
    }
    try {
      await gotoWorkspace(page,url+'#overview');

      // A status edit with a workflow dispatches one review run, not another execution.
      const routing=await fixture('Route review '+width,{workflow:true,running:true});
      await editStatus(routing.task,'review');
      await expect(editor.locator('[name=startAgent]')).toBeChecked();
      await editor.getByRole('button',{name:'Save',exact:true}).click();
      const routed=await page.evaluate(id=>({task:WorkpalStudio.db.tasks.find(t=>t.id===id),runs:WorkpalStudio.db.runs.filter(r=>r.task===id)}),routing.task);
      expect(routed.task.status).toBe('review');
      expect(routed.task.owner).toBe('Quality partner');
      expect(routed.runs).toHaveLength(2);
      expect(routed.runs.filter(r=>r.status==='queued')).toHaveLength(1);
      expect(routed.runs.find(r=>r.status==='queued').kind).toBe('review');
      expect(routed.runs.find(r=>r.id===routing.run).status).toBe('cancelled');

      // The unchecked control suppresses workflow dispatch as well as direct dispatch.
      const backlog=await fixture('Keep assignment only '+width,{workflow:true,status:'backlog'});
      await editStatus(backlog.task,'todo');
      await editor.locator('[name=startAgent]').uncheck();
      await editor.getByRole('button',{name:'Save',exact:true}).click();
      expect(await page.evaluate(id=>WorkpalStudio.db.runs.filter(r=>r.task===id).length,backlog.task)).toBe(0);
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,backlog.task)).toBe('todo');

      // Manual Done requires a reason; late results stay candidates until explicitly selected.
      const manual=await fixture('Manual completion '+width,{running:true});
      await editStatus(manual.task,'done');
      await expect(editor.locator('[name=manualReason]')).toBeVisible();
      await editor.getByRole('button',{name:'Save',exact:true}).click();
      await expect(editor).toBeVisible();
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,manual.task)).toBe('active');
      await editor.locator('[name=manualReason]').fill('Resolved by a person before the run returned.');
      await editor.getByRole('button',{name:'Save',exact:true}).click();
      await expect(page.locator('main')).toContainText('Completed manually');
      const lateId=await deliver(manual.run,'Late delivery retained for inspection.');
      await openRun(manual.run);
      await expect(page.locator('main')).toContainText('Candidate delivery');
      await expect(page.locator('form[data-form=decision]')).toHaveCount(0);
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,manual.task)).toBe('done');
      await page.getByRole('button',{name:'Select for review',exact:true}).click();
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,manual.task)).toBe('done');
      await page.locator('form[data-form=selectDelivery] [name=reason]').fill('Reopen to inspect the late evidence.');
      await page.getByRole('button',{name:'Select for review',exact:true}).click();
      await expect(page.locator('form[data-form=decision]')).toBeVisible();
      expect(await page.evaluate(id=>WorkpalStudio.currentDelivery(id).id,manual.task)).toBe(lateId);
      await approveCurrent();
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).completion.kind,manual.task)).toBe('delivery');

      // Reverse completion order preserves the first selected delivery and exposes a candidate action.
      const parallel=await fixture('Parallel responses '+width,{running:true});
      const laterRun=await page.evaluate(id=>WorkpalStudio.start(WorkpalStudio.db.tasks.find(t=>t.id===id),'webapp-testing','Quality partner').id,parallel.task);
      const firstResult=await deliver(laterRun,'Quality response arrived first.');
      const candidate=await deliver(parallel.run,'Engineering response arrived later.');
      await openRun(parallel.run);
      await expect(page.locator('main')).toContainText('Candidate delivery');
      await expect(page.locator('form[data-form=decision]')).toHaveCount(0);
      expect(await page.evaluate(id=>WorkpalStudio.currentDelivery(id).id,parallel.task)).toBe(firstResult);
      await page.getByRole('button',{name:'Open current delivery',exact:true}).click();
      await expect(page.locator('form[data-form=decision]')).toBeVisible();
      await openRun(parallel.run);
      await page.locator('form[data-form=selectDelivery] [name=reason]').fill('Use the engineering response as the reviewed result.');
      await page.getByRole('button',{name:'Select for review',exact:true}).click();
      expect(await page.evaluate(id=>WorkpalStudio.currentDelivery(id).id,parallel.task)).toBe(candidate);
      await expect(page.locator('form[data-form=decision]')).toBeVisible();
      await page.screenshot({path:'test-results/lifecycle-selected-'+width+'.png'});
      await approveCurrent();
      await openRun(laterRun);
      await expect(page.locator('form[data-form=decision]')).toHaveCount(0);

      // Cancelling a queued retry keeps the existing delivery decision form available.
      const retry=await fixture('Cancelled retry '+width,{running:true});
      const retained=await deliver(retry.run,'Ready for review before retry.');
      const queued=await page.evaluate(id=>{
        const task=WorkpalStudio.db.tasks.find(t=>t.id===id);
        return WorkpalStudio.start(task,'webapp-testing',task.owner,true).id;
      },retry.task);
      await openRun(queued);
      await page.getByRole('button',{name:'Cancel run',exact:true}).click();
      await openRun(retry.run);
      await expect(page.locator('form[data-form=decision]')).toBeVisible();
      expect(await page.evaluate(id=>WorkpalStudio.currentDelivery(id).id,retry.task)).toBe(retained);
      await approveCurrent();
      await reloadWorkspace(page);
      expect(await page.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).status,retry.task)).toBe('done');
      expect(await page.evaluate(()=>document.documentElement.scrollWidth)).toBeLessThanOrEqual(width);
      expect(errors).toEqual([]);
      expect(remoteRequests).toEqual([]);
      console.log('PASS lifecycle '+width+'px: review routing, no-start, manual completion, late/parallel selection and cancelled retry');
    }catch(error){
      failures.push(width+'px: '+error.stack);
      await page.screenshot({path:'test-results/lifecycle-failure-'+width+'.png'});
    }finally{await context.close();}
  }
}finally{await browser.close();}
if(failures.length)throw Error(failures.join('\n\n'));
console.log('Lifecycle browser QA passed at desktop and narrow widths.');
