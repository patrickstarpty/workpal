import {withBrowser, signIn} from './browser-fixture.mjs';
await withBrowser(async ({base,newPage,expect,runPython}) => {
  runPython(`from django.contrib.auth import get_user_model
from workpal.identity.models import Membership
from workpal.contracts import Actor
from workpal.work import issues,service
for n in range(22):
 u=get_user_model().objects.create_user(username='person'+str(n).zfill(2))
 Membership.objects.create(user=u,workspace_id=1,role='member')
a=Actor(1,1)
p=service.create(a,name='Assignment project')
issues.create(a,p['id'],'Assignment issue',assignee_user_id=u.id)`);
  const page=await newPage();
  await signIn(page,base,'reader');
  await page.getByLabel('Workspace',{exact:true}).selectOption('1');
  await page.getByRole('button',{name:'Issues',exact:true}).click();
  await page.getByRole('button',{name:'Assignment issue (#1)',exact:true}).click();
  await expect(page.getByRole('heading',{name:'Requirements version 1',exact:true})).toBeVisible();
  const open=()=>page.getByRole('button',{name:'Change assignee',exact:true}).click();
  await open();
  let dialog=page.getByRole('dialog');
  await dialog.getByRole('button',{name:'Save assignee',exact:true}).click();
  await expect(dialog.getByRole('alert')).toHaveText('No changes to save');
  await dialog.getByLabel('Search people',{exact:true}).fill('owner');
  await dialog.getByRole('button',{name:'owner (#1)',exact:true}).click();
  await dialog.getByRole('button',{name:'Save assignee',exact:true}).click();
  await expect(page.locator('.issue-detail')).toContainText('owner (#1)');
  await open();
  await dialog.getByRole('button',{name:'Unassigned',exact:true}).click();
  await dialog.getByRole('button',{name:'Save assignee',exact:true}).click();
  await expect(page.locator('.issue-detail')).toContainText('Unassigned');
});
