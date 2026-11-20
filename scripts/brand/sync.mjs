import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
export async function sync(root,{check=false}={}){
 const mark=await readFile(resolve(root,'apps/web/public/workpal-mark.svg'));
 const word=await readFile(resolve(root,'apps/web/public/workpal-wordmark.svg'));
 const paths=[['apps/web/public/favicon.svg',mark],['apps/web/public/icons/icon.svg',mark],['apps/docs/public/favicon.svg',mark],['docs/assets/logo-light.svg',word],['docs/assets/logo-dark.svg',word]];
 const changed=[];for(const [path,data] of paths){let current;try{current=await readFile(resolve(root,path));}catch{}if(!current?.equals(data)){changed.push(path);if(!check){await mkdir(dirname(resolve(root,path)),{recursive:true});await writeFile(resolve(root,path),data);}}}return changed;
}
if(process.argv[1]===import.meta.filename){const changed=await sync(resolve(import.meta.dirname,'../..'),{check:process.argv.includes('--check')});if(process.argv.includes('--check')&&changed.length)process.exitCode=1;console.log(changed);}
