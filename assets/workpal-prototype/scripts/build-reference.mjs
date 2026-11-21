// Dev-only: render the original Multica controls without a backend or a server.
import {readFile,writeFile} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {execFileSync} from 'node:child_process';
const reference=resolve('../multica'),fixture=resolve('outputs/multica-reference');
const revision=execFileSync('git',['-C',reference,'rev-parse','HEAD'],{encoding:'utf8'}).trim();
if(!revision.startsWith('428ef30fe'))throw Error('Reference must be Multica 428ef30fe; found '+revision);
execFileSync(process.execPath,[resolve(reference,'apps/storybook/node_modules/vite/bin/vite.js'),'build','--config',resolve(fixture,'vite.config.mjs')],{stdio:'inherit'});
const root=resolve(fixture,'build');let html=await readFile(resolve(root,'index.html'),'utf8');
for(const match of [...html.matchAll(/<script[^>]+src="([^"]+)"[^>]*><\/script>/g)]){const script=(await readFile(resolve(root,match[1]),'utf8')).replaceAll('</script','<\\/script');html=html.replace(match[0],()=>'<script type="module">'+script+'</script>');}
for(const match of [...html.matchAll(/<link[^>]+href="([^"]+\.css)"[^>]*>/g)]){const path=resolve(root,match[1]);let css=await readFile(path,'utf8');for(const font of [...css.matchAll(/url\(([^)]+\.woff2)\)/g)]){const buffer=await readFile(resolve(dirname(path),font[1]));css=css.replace(font[0],'url(data:font/woff2;base64,'+buffer.toString('base64')+')');}html=html.replace(match[0],()=>'<style>'+css+'</style>');}
await writeFile(resolve(fixture,'Multica-controls.html'),html);await writeFile(resolve(fixture,'revision.json'),JSON.stringify({revision,scope:'Original PropertyPicker, Button and Dialog; translation strings supplied by the fixture. No production backend.'},null,2));
