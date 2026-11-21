import {readFile,writeFile,mkdir} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import sharp from 'sharp';
const root=resolve(import.meta.dirname,'../..');
const mark=await readFile(resolve(root,'apps/web/public/workpal-mark.svg'));
const word=await readFile(resolve(root,'apps/web/public/workpal-wordmark.svg'));
const uri=b=>`data:image/svg+xml;base64,${b.toString('base64')}`;
const put=async(p,data)=>{const file=resolve(root,p);await mkdir(dirname(file),{recursive:true});await writeFile(file,data);};
await put('packages/ui/lib/workpal-assets.ts',`export const WORKPAL_MARK=${JSON.stringify(uri(mark))};\nexport const WORKPAL_WORDMARK=${JSON.stringify(uri(word))};\n`);
for(const base of ['apps/web/public','apps/docs/public']){
 await put(`${base}/workpal-mark.svg`,mark);await put(`${base}/workpal-wordmark.svg`,word);
 await put(`${base}/favicon.svg`,mark);await put(`${base}/icons/icon.svg`,mark);
 for(const [name,size] of [['icon-192.png',192],['icon-512.png',512],['icon-maskable-512.png',512],['apple-touch-icon.png',180]])await put(`${base}/icons/${name}`,await sharp(mark).resize(size,size).png().toBuffer());
}
for(const shade of ['light','dark']){
 await put(`docs/assets/logo-${shade}.svg`,word);
 await put(`docs/assets/logo-${shade}.gif`,await sharp(word).resize({width:720}).gif().toBuffer());
}
const og=`<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="630"><rect width="1200" height="630" fill="#f7f7f5"/><image href="${uri(word)}" x="300" y="150" width="600" height="200"/><text x="600" y="440" text-anchor="middle" font-family="sans-serif" font-size="44" fill="#183028">Let’s work together.</text></svg>`;
await put('apps/web/app/opengraph-image.png',await sharp(Buffer.from(og)).png().toBuffer());
console.log('Generated Workpal brand assets');
