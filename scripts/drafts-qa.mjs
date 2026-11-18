import {createRequire} from 'node:module';
import {pathToFileURL} from 'node:url';
import {resolve} from 'node:path';
import {mkdir,readFile} from 'node:fs/promises';
const require=createRequire(import.meta.url);
const {chromium,expect}=require(process.env.WORKPAL_PLAYWRIGHT||'@playwright/test');
const url=pathToFileURL(resolve('dist/Workpal.html')).href;
const browser=await chromium.launch();
await mkdir('test-results',{recursive:true});
const failures=[];
async function visit(page,hash){await page.goto(url+'#'+hash);}
async function notes(page){await page.getByRole('button',{name:'Workspace notes',exact:true}).click();return page.locator('#dialog');}
try {
  for(const width of [1440,390]){
    const context=await browser.newContext({viewport:{width,height:900},acceptDownloads:true});
    const page=await context.newPage();page.setDefaultTimeout(7000);
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    try{
      await visit(page,'settings');
      const fixture=await page.evaluate(()=>{
        const studio=WorkpalStudio;
        function task(title){return studio.assignWork('Engineering partner',{title,project:'TAP',description:'Draft persistence fixture',checks:['Retain the entered text'],status:'todo',priority:'Normal',queueRun:false}).task;}
        const a=task('Draft A'),b=task('Draft B'),c=task('Review draft');
        const first=studio.start(a,'brainstorming'),second=studio.start(b,'brainstorming'),review=studio.start(c,'brainstorming');
        studio.changeRun(review,'deliver','Review fixture',{artifacts:[{title:'Draft reference',body:'An authored reference for review.'}],evidence:c.checks.map(criterion=>({criterion,evidence:'Reviewer reference',status:'supported'})),limitations:'Manual QA fixture'});
        return {first:first.id,second:second.id,review:review.id,task:a.id};
      });
      await visit(page,'workflow?id='+fixture.first);
      const summary=page.locator('main form[data-form=deliver] [name=note]');
      const artifact=page.locator('main [name=artifactBody]');
      await summary.fill('Keep this summary '+width);
      await artifact.fill('Keep the important artifact '+width);
      if(width>767){
        await page.getByRole('button',{name:'Collapse sidebar',exact:true}).click();
        await expect(summary).toHaveValue('Keep this summary '+width);
        await expect(artifact).toHaveValue('Keep the important artifact '+width);
      }
      await page.locator('.chat-launcher [data-act=chat]').click();
      await page.getByRole('button',{name:'Close chat',exact:true}).click();
      await expect(summary).toHaveValue('Keep this summary '+width);
      await expect(artifact).toHaveValue('Keep the important artifact '+width);
      await visit(page,'workflow?id='+fixture.second);
      await expect(page.locator('main form[data-form=deliver] [name=note]')).toHaveValue('');
      await page.locator('main form[data-form=deliver] [name=note]').fill('Separate second run '+width);
      await visit(page,'workflow?id='+fixture.first);
      await expect(summary).toHaveValue('Keep this summary '+width);
      await expect(artifact).toHaveValue('Keep the important artifact '+width);
      await page.reload();
      await expect(summary).toHaveValue('Keep this summary '+width);
      await expect(artifact).toHaveValue('Keep the important artifact '+width);
      await visit(page,'workflow?id='+fixture.review);
      await page.locator('main form[data-form=decision] [name=choice]').selectOption('return');
      await page.locator('main form[data-form=decision] [name=note]').fill('Keep this review reasoning '+width);
      await page.reload();
      await expect(page.locator('main form[data-form=decision] [name=choice]')).toHaveValue('return');
      await expect(page.locator('main form[data-form=decision] [name=note]')).toHaveValue('Keep this review reasoning '+width);
      await visit(page,'tasks?id='+fixture.task);
      await page.locator('main form[data-form=comment] [name=text]').fill('Keep this comment '+width);
      await page.reload();
      await expect(page.locator('main form[data-form=comment] [name=text]')).toHaveValue('Keep this comment '+width);
      await page.getByRole('button',{name:'Post comment',exact:true}).click();
      await page.reload();
      await expect(page.locator('main form[data-form=comment] [name=text]')).toHaveValue('');
      await page.screenshot({path:'test-results/drafts-'+width+'.png'});
      expect(errors).toEqual([]);
      console.log('PASS drafts '+width+'px: layout, chat, navigation, reload, per-run, review and comment');
    }catch(error){failures.push('Drafts '+width+'px: '+error.stack);await page.screenshot({path:'test-results/drafts-failure-'+width+'.png'});}
    finally{await context.close();}
  }
  const context=await browser.newContext({viewport:{width:1440,height:900},acceptDownloads:true});
  const first=await context.newPage(),second=await context.newPage();
  first.setDefaultTimeout(7000);second.setDefaultTimeout(7000);
  try{
    await visit(first,'settings');await visit(second,'settings');
    let dialog=await notes(first);
    await dialog.locator('[name=text]').fill('Reviewer note from first tab');
    await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();
    dialog=await notes(second);
    await dialog.locator('[name=text]').fill('Reviewer note from second tab');
    await dialog.getByRole('button',{name:'Save feedback',exact:true}).click();
    const savedNotes=await second.evaluate(()=>JSON.parse(localStorage.getItem('workpal.studio.v2')).notes.map(n=>n.text));
    expect(savedNotes).toContain('Reviewer note from first tab');
    expect(savedNotes).toContain('Reviewer note from second tab');
    const id=await first.evaluate(()=>WorkpalStudio.db.tasks.find(t=>t.id==='TAP-030').id);
    await visit(first,'tasks?id='+id);await visit(second,'tasks?id='+id);
    await first.getByRole('button',{name:'Edit issue',exact:true}).click();
    await second.getByRole('button',{name:'Edit issue',exact:true}).click();
    await first.locator('#dialog [name=description]').fill('Saved description from first tab');
    await first.locator('#dialog').getByRole('button',{name:'Save changes',exact:true}).click();
    await second.locator('#dialog [name=description]').fill('Keep unsaved description from second tab');
    await second.locator('#dialog').getByRole('button',{name:'Save changes',exact:true}).click();
    await expect(second.locator('#storage-conflict')).toBeVisible();
    await expect(second.locator('#dialog [name=description]')).toHaveValue('Keep unsaved description from second tab');
    expect(await second.evaluate(id=>JSON.parse(localStorage.getItem('workpal.studio.v2')).tasks.find(t=>t.id===id).description,id)).toBe('Saved description from first tab');
    const download=second.waitForEvent('download',{timeout:10000}).catch(error=>error);
    await second.getByRole('button',{name:'Export unsaved work',exact:true}).click();
    const exported=await download;if(exported instanceof Error)throw exported;
    expect(exported.suggestedFilename()).toBe('Workpal-unsaved.json');
    const backup=JSON.parse(await readFile(await exported.path(),'utf8'));
    expect(backup.data.tasks.find(t=>t.id===id).description).toBe('Keep unsaved description from second tab');
    await second.screenshot({path:'test-results/storage-conflict.png'});
    await second.getByRole('button',{name:'Keep recovery copy and reload',exact:true}).click();
    await expect(second.locator('#storage-conflict')).toHaveCount(0);
    await second.getByRole('button',{name:'Edit issue',exact:true}).click();
    await expect(second.locator('#dialog [name=description]')).toHaveValue('Keep unsaved description from second tab');
    expect(await second.evaluate(()=>Object.keys(localStorage).some(key=>key.startsWith('workpal.recovery.')))).toBe(true);
    expect(await second.evaluate(id=>WorkpalStudio.db.tasks.find(t=>t.id===id).description,id)).toBe('Saved description from first tab');
    console.log('PASS cross-tab notes merge and conflicting edit export');
  }catch(error){failures.push('Cross-tab: '+error.stack);await second.screenshot({path:'test-results/storage-conflict-failure.png'});}
  finally{await context.close();}

  const isolated=await browser.newContext({viewport:{width:1440,height:900}});
  const page=await isolated.newPage();page.setDefaultTimeout(7000);
  try{
    await visit(page,'settings');let dialog=await notes(page);
    await dialog.locator('[name=text]').fill('Home workspace unsaved note');
    await page.keyboard.press('Escape');
    const other=await page.evaluate(()=>WorkpalStudio.createWorkspace('Draft isolation'));
    await visit(page,'w/'+other+'/settings');dialog=await notes(page);
    await expect(dialog.locator('[name=text]')).toHaveValue('');
    await dialog.locator('[name=text]').fill('Other workspace unsaved note');
    await visit(page,'settings');dialog=await notes(page);
    await expect(dialog.locator('[name=text]')).toHaveValue('Home workspace unsaved note');
    await visit(page,'w/'+other+'/settings');dialog=await notes(page);
    await expect(dialog.locator('[name=text]')).toHaveValue('Other workspace unsaved note');
    console.log('PASS workspace draft isolation');
  }catch(error){failures.push('Workspace isolation: '+error.stack);await page.screenshot({path:'test-results/draft-workspace-failure.png'});}
  finally{await isolated.close();}
}finally{await browser.close();}
if(failures.length)throw Error(failures.join('\n\n'));
console.log('Draft and persistence browser QA passed.');
