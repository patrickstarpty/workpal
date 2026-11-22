export type CapabilityView = 'overview' | 'skills' | 'team';

/** Capability entry routes never stand in for a workspace slug. */
export function capabilityView(pathname: string): CapabilityView | null {
  if (['/', '/home'].includes(pathname)) return 'overview';
  if (pathname === '/home/skills') return 'skills';
  if (pathname === '/home/team') return 'team';
  return null;
}
export function capabilityPath(view: CapabilityView): string {
  return view === 'overview' ? '/home' : `/home/${view}`;
}
