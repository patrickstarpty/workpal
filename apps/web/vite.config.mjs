import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import tailwind from '@tailwindcss/vite';
export default defineConfig({plugins:[react(),tailwind()],resolve:{dedupe:['react','react-dom','@tanstack/react-query']},build:{target:'esnext'},server:{host:'127.0.0.1',port:4174,strictPort:true,proxy:{'/api':'http://127.0.0.1:4175'}}});
