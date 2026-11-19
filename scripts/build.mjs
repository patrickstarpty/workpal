import './build-brand.mjs';
import { readFile, mkdir, writeFile } from 'node:fs/promises';
const root = new URL('../', import.meta.url);
const read = (path) => readFile(new URL(path, root), 'utf8');
let html = await read('index.html');
html=html.replace('assets/brand/workpal-favicon.svg','data:image/svg+xml;base64,'+Buffer.from(await read('assets/brand/workpal-favicon.svg')).toString('base64'));
const font = await readFile(new URL('assets/fonts/inter-latin.woff2', root));
const css = '/* '+(await read('assets/fonts/LICENSE.txt'))+' */\n' + (await read('src/studio.css'))
  .replace('../assets/fonts/inter-latin.woff2', 'data:font/woff2;base64,' + font.toString('base64'));
html = html.replace('<link rel="stylesheet" href="src/studio.css" />', `<style>${css}</style>`);
html = html.replace('<link rel="stylesheet" href="src/analytics.css" />', `<style>${await read('src/analytics.css')}</style>`);
for (const file of ['brand', 'icons', 'data', 'workspace-fixtures', 'model', 'analytics-data', 'analytics', 'studio']) {
  const script = (await read(`src/${file}.js`)).replaceAll('</script', '<\\/script');
  html = html.replace(`<script src="src/${file}.js"></script>`, () => `<script>${script}</script>`);
}
await mkdir(new URL('dist/', root), { recursive: true });
await writeFile(new URL('dist/Workpal.html', root), html);
console.log('Built dist/Workpal.html — self-contained, opens offline without installation.');
