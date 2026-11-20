import type {ComponentProps} from 'react';
export function MulticaWordmark({writeDelayMs,title='Workpal',className,...props}:ComponentProps<'svg'>&{writeDelayMs?:number;title?:string}){return <svg viewBox="0 0 266 87" role="img" aria-label={title} className={className} {...props}><image href="/workpal-wordmark.svg" width="266" height="87"/></svg>;}
