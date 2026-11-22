export function entryPath(hash: string): string {
  const path = hash.replace(/^#/, '');
  if (!path || path === '/') return '/home';
  return path.startsWith('/') ? path : '/' + path;
}

/** A return destination stays inside this app and cannot lead back to sign-in. */
export function loginDestination(route: string): string {
  const base = 'https://workpal.local';
  const next = new URL(route, base).searchParams.get('next');
  if (!next || !next.startsWith('/') || next.startsWith('//') || /[\s\\]/.test(next)) return '/home';
  const destination = new URL(next, base);
  if (destination.pathname === '/login' || destination.pathname === '/') return '/home';
  return destination.pathname + destination.search + destination.hash;
}
