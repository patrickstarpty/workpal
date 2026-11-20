import {mkdirSync} from 'node:fs';
for(const name of ['desktop','mobile','docs','storybook'])mkdirSync(new URL('../apps/'+name+'/',import.meta.url),{recursive:true});
