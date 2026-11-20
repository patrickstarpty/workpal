import {mkdir} from 'node:fs/promises';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,runPython,expect,repo})=>{
 const id=runPython(`from workpal.contracts import Actor
from workpal.work import service,issues,transitions
a=Actor(1,1)
p=service.create(a,name='Transition project')
i=issues.create(a,p['id'],'Transition issue')
i=transitions.transition(a,i['id'],'todo',i['revision'])
print(i['id'])`).trim().split('\n').at(-1);
 const page=await newPage();await signIn(page,base,'reader');
 await page.getByLabel('Workspace',{exact:true}).selectOption('1');
 await page.getByRole('button',{name:'Issues',exact:true}).click();
 await page.getByRole('button',{name:`Transition issue (#${id})`,exact:true}).click();
 await expect(page.locator('.issue-detail')).toContainText('Status: Todo');
 await page.getByRole('button',{name:'Change status',exact:true}).click({timeout:3000});
 await expect(page.getByRole('dialog')).toBeVisible();
 for(const target of ['in_progress','in_review']){
  await page.getByLabel('Target status',{exact:true}).selectOption(target);
  await page.getByRole('button',{name:'Save status',exact:true}).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.issue-detail')).toContainText(target==='in_progress'?'Status: In Progress':'Status: In Review');
  await page.getByRole('button',{name:'Change status',exact:true}).click();
 }
 await mkdir(`${repo}/outputs/workpal-web`,{recursive:true});
 await page.setViewportSize({width:1440,height:900});
 await page.screenshot({path:`${repo}/outputs/workpal-web/a54c2-transition-desktop.png`});
 await page.setViewportSize({width:390,height:844});
 await page.screenshot({path:`${repo}/outputs/workpal-web/a54c2-transition-mobile.png`});
 await page.keyboard.press('Escape');
 await expect(page.getByRole('button',{name:'Change status',exact:true})).toBeFocused();
});
