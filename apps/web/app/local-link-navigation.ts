/** Bridge shared editor links into the active local application's hash router. */
export function installLocalLinkNavigation(target: Window) {
  const handler = (event: Event) => {
    const {path, disposition} = (event as CustomEvent<{path?:unknown;disposition?:string}>).detail ?? {};
    if (typeof path !== 'string' || !path.startsWith('/') || path.startsWith('//')) return;
    if (disposition === 'background-tab' || disposition === 'foreground-tab') {
      target.open(`${target.location.origin}/#${path}`, '_blank', 'noopener,noreferrer');
    } else {
      target.location.hash = path;
    }
  };
  target.addEventListener('workpal:navigate', handler);
  return () => target.removeEventListener('workpal:navigate', handler);
}
