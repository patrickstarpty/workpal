import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
export default defineConfig(({mode})=>({plugins:[react(),tailwind()],resolve:{dedupe:['react','react-dom','@tanstack/react-query']},build:{target:'esnext'},server:{host:'127.0.0.1',port:4174,strictPort:true,proxy:mode==='python'?Object.fromEntries(['/api','/auth','/ws','/v1','/plugin-surfaces'].map(route=>[route,{target:`http://127.0.0.1:${process.env.WORKPAL_PORT||4175}`,ws:true}])):{'/api':'http://127.0.0.1:4175'}}}));
