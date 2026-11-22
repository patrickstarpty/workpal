import {readFile} from 'node:fs/promises';
import postcss from 'postcss';
import {appearance} from '../../scripts/theme-files.mjs';

// Reuse the application's source of truth, including the theme option defaults.
export async function workpalAppearance(){
 const {BUILT_IN_THEMES}=await appearance('built-in-themes.ts');
 const {themeCss}=await appearance('theme-package.ts');
 const {themeOptionAttributes,themeOptionVariables}=await appearance('themes.ts');
 const themes=['fwd','default'].map(id=>{
  const theme=BUILT_IN_THEMES.find(t=>t.id===id);
  if(!theme)throw new Error('Missing Workpal theme: '+id);
  return {id:theme.id,name:theme.name,css:themeCss(theme),attributes:themeOptionAttributes(theme),variables:themeOptionVariables(theme)};
 });
 const tokens=postcss.parse(await readFile(new URL('../../packages/ui/styles/tokens.css',import.meta.url),'utf8'));
 tokens.walkComments(c=>c.remove());
 tokens.walkAtRules('theme',rule=>{
  if(rule.params==='inline')rule.remove();
  else rule.replaceWith(postcss.rule({selector:':root',nodes:rule.nodes}));
 });
 const font=await readFile(new URL('../../node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2',import.meta.url));
 const fontCss=`@font-face{font-family:"Workpal Inter";font-style:normal;font-weight:100 900;font-display:swap;src:url(data:font/woff2;base64,${font.toString('base64')}) format("woff2")}
 :root{--font-ui-inter:"Workpal Inter",Inter;--font-sans:var(--font-ui,var(--font-ui-inter)),ui-sans-serif,system-ui,sans-serif;--font-mono:ui-monospace,SFMono-Regular,Menlo,monospace}`;
 return {themes,css:tokens.toString()+'\n'+fontCss};
}

export function workpalTypeScale(css){
 const sizes={10:'micro',11:'micro',12:'caption',13:'label',14:'body',15:'body-lg',16:'title-sm',18:'title',19:'title-lg',20:'title-lg',21:'title-lg',23:'display-sm',24:'display-sm',30:'display',36:'display',50:'display',64:'display'};
 return css.replace(/font-size:\s*(\d+)px/g,(match,size)=>sizes[size]?'font-size:var(--text-'+sizes[size]+');line-height:var(--text-'+sizes[size]+'--line-height)':match);
}
