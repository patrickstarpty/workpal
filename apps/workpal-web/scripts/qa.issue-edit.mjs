import assert from 'node:assert/strict';
import {mkdir} from 'node:fs/promises';
import {withBrowser,signIn} from './browser-fixture.mjs';
await withBrowser(async({base,newPage,expect,runPython,repo})=>{
 runPython(`from workpal.contracts import Actor
from workpal.work import issues,service
p=service.create(Actor(1,1),name='Edit project')
issues.create(Actor(1,1),p['id'],'Original',description='Original description',criteria=[{'key':'delivery_check','text':'Delivery'},{'key':'criterion_1','text':'Other'}])`);
 async function open(){const p=await newPage();await signIn(p,base,'reader');await p.getByLabel('Workspace',{exact:true}).selectOption('1');await p.getByRole('button',{name:'Issues',exact:true}).click();await p.getByRole('button',{name:'Original (#1)',exact:true}).click();await p.getByRole('button',{name:'Edit requirements',exact:true}).click({timeout:5000});return p;}
 const a=await open(),b=await open();const da=a.getByRole('dialog'),db=b.getByRole('dialog');
 await da.getByLabel('Title',{exact:true}).fill('A <img src=x>');
 await da.getByRole('button',{name:'Save changes',exact:true}).click();await expect(da).toHaveCount(0);
 await db.getByLabel('Description',{exact:true}).fill('B description');await db.getByRole('button',{name:'Save changes',exact:true}).click();
 await expect(db.getByRole('button',{name:'Save changes',exact:true})).toBeDisabled();
 await db.getByRole('button',{name:'Reload current',exact:true}).click();await expect(db.getByLabel('Title',{exact:true})).toHaveValue('A <img src=x>');await expect(db.getByLabel('Description',{exact:true})).toHaveValue('B description');
 await db.getByRole('button',{name:'Save changes',exact:true}).click();await expect(db).toHaveCount(0);
 runPython(`from workpal.work.models import Issue,IssueRequirements
i=Issue.objects.get();assert i.revision==3 and i.current_requirements.number==3
assert i.current_requirements.title=='A <img src=x>' and i.current_requirements.description=='B description'
assert i.current_requirements.criteria==[{'key':'delivery_check','text':'Delivery'},{'key':'criterion_1','text':'Other'}]
assert IssueRequirements.objects.count()==3`);
 const edit=b.getByRole('button',{name:'Edit requirements',exact:true});await edit.click();await db.getByRole('button',{name:'Save changes',exact:true}).click();await expect(db.getByRole('alert')).toHaveText('No changes to save');
 await db.getByRole('button',{name:'Remove criterion 2',exact:true}).click();await db.getByRole('button',{name:'Add criterion',exact:true}).click();await db.getByLabel('Acceptance criterion 3',{exact:true}).fill('New');await b.keyboard.press('Escape');await expect(edit).toBeFocused();await edit.click();await expect(db.getByLabel('Acceptance criterion 3',{exact:true})).toHaveValue('New');
 await mkdir(repo+'/outputs/workpal-web',{recursive:true});for(const [name,width]of[['desktop',1440],['mobile',390]]){await b.setViewportSize({width,height:1000});assert(await b.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await b.screenshot({path:repo+`/outputs/workpal-web/a54b3-edit-${name}.png`});}
 await db.getByRole('button',{name:'Save changes',exact:true}).click();await expect(db).toHaveCount(0);
 runPython(`from workpal.work.models import Issue
i=Issue.objects.get();assert i.current_requirements.criteria==[{'key':'delivery_check','text':'Delivery'},{'key':'criterion_3','text':'New'}]`);
 await edit.click();await db.getByLabel('Description',{exact:true}).fill('');await db.getByRole('button',{name:'Remove criterion 1',exact:true}).click();await db.getByRole('button',{name:'Remove criterion 2',exact:true}).click();await db.getByRole('button',{name:'Save changes',exact:true}).click();await expect(db).toHaveCount(0);
 runPython(`from workpal.work.models import Issue
i=Issue.objects.get();assert i.current_requirements.description=='' and i.current_requirements.criteria==[]`);
});
console.log('Issue edit core and real concurrent reload passed');
