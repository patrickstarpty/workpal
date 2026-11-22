import {defineConfig} from 'vite';
import tailwind from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import {resolve} from 'node:path';
export default defineConfig({root:import.meta.dirname,base:'./',plugins:[{name:'fixture-translations',enforce:'pre',resolveId(source,importer){if(source.endsWith('/i18n')&&importer?.includes('property-picker'))return resolve(import.meta.dirname,'i18n.ts');}},react(),tailwind()],resolve:{dedupe:['react','react-dom']},build:{outDir:'build',cssCodeSplit:false,rollupOptions:{output:{inlineDynamicImports:true}}}});
