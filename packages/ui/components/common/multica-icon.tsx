import type {ComponentProps} from 'react';
export type MulticaIconMode='static'|'think'|'intro';
export function MulticaIcon({mode,shape,size=24,title='Workpal',...props}:Omit<ComponentProps<'svg'>,'mode'>&{mode?:MulticaIconMode;shape?:'square'|'circle';size?:number;title?:string}){return <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={title} {...props}><image href="/workpal-mark.svg" width="100" height="100"/></svg>;}
