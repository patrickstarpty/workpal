import {WORKPAL_MARK} from '../../lib/workpal-assets';
import type {ComponentProps} from 'react';
export type WorkpalIconMode='static'|'think'|'intro';
export function WorkpalIcon({mode,shape,size=24,title='Workpal',...props}:Omit<ComponentProps<'svg'>,'mode'>&{mode?:WorkpalIconMode;shape?:'square'|'circle';size?:number;title?:string}){return <svg viewBox="0 0 100 100" width={size} height={size} role="img" aria-label={title} {...props}><image href={WORKPAL_MARK} width="100" height="100"/></svg>;}
