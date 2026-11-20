import {createServer} from './api.mjs';
import {resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const root=fileURLToPath(new URL('../',import.meta.url));
const dev=process.argv.includes('--dev');
const server=createServer({dbPath:process.env.WORKPAL_DB||resolve(root,'server/data/workpal.sqlite'),staticDir:resolve(root,'apps/web/dist')});
server.listen(dev?4175:4174,'127.0.0.1',()=>console.log(`Workpal: http://127.0.0.1:${dev?4174:4174}`));
let vite;if(dev){const {createServer}=await import('vite');vite=await createServer({root:resolve(root,'apps/web'),configFile:resolve(root,'apps/web/vite.config.mjs')});await vite.listen();}
let stopping=false;
async function shutdown(){
  if(stopping)return;
  stopping=true;
  try{await vite?.close();}
  finally{server.close();server.closeAllConnections();}
}
for(const signal of ['SIGINT','SIGTERM'])process.on(signal,shutdown);
