import {readFile,writeFile} from 'node:fs/promises';
const root=new URL('../',import.meta.url);
const variants={};
for(const [name,file] of [['logo','workpal-mark.svg'],['wordmark','workpal-wordmark.svg']]){
 const svg=await readFile(new URL('assets/brand/'+file,root),'utf8');
 variants[name]=svg.replace('color="#183028"','color="inherit"').replace('role="img"','aria-hidden="true"').replace(/ aria-label="[^"]*"/,'').replace('<svg ','<svg class="brand-'+name+'" focusable="false" ');
}
await writeFile(new URL('src/brand.js',root),'// Generated from assets/brand by scripts/build-brand.mjs.\nglobalThis.WorkpalBrand = Object.freeze('+JSON.stringify(variants)+');\n');
