import {describe,it,expect} from 'vitest';
import {switchLocalePath} from './switch-locale';
describe('documentation locale navigation',()=>{
 it('preserves the article when switching between languages',()=>{
  expect(switchLocalePath('/zh/agents','en')).toBe('/agents');
  expect(switchLocalePath('/en/agents','zh')).toBe('/zh/agents');
  expect(switchLocalePath('/fr/developers/themes','ja')).toBe('/ja/developers/themes');
 });
 it('supports all language roots without repeated locale prefixes',()=>{
  for(const lang of ['en','zh','zh-Hant','ja','ko','fr'])expect(switchLocalePath('/zh',lang)).toBe(lang==='en'?'/':'/'+lang);
 });
});
