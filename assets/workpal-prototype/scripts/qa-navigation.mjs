// Workspace suites enter through the same welcome action as a user.
// The welcome suite tests the entry screen and startup routing directly.
async function enterWorkspace(page){
  await page.locator('.welcome-enter, .shell').first().waitFor({state:'visible'});
  const entry=page.locator('.welcome-enter');
  if(await entry.count()){
    await entry.click();
    await page.locator('.shell').waitFor({state:'visible'});
  }
}

export async function gotoWorkspace(page,url,options){
  const response=await page.goto(url,options);
  await enterWorkspace(page);
  return response;
}

export async function reloadWorkspace(page,options){
  const response=await page.reload(options);
  await enterWorkspace(page);
  return response;
}
