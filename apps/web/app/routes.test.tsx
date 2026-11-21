import {it,expect} from 'vitest';
import {resolveWorkspaceSlug} from './python-session';
import {entryPath} from './entry-route';
import {capabilityView} from './capabilities/routes';
it('keeps login distinct from the capability entry',()=>{
 expect(entryPath('#/login')).toBe('/login');
 expect(entryPath('#login')).toBe('/login');
 expect(entryPath('#/login?next=%2Fteam%2Fprojects')).toBe('/login?next=%2Fteam%2Fprojects');
 expect(entryPath('')).toBe('/home');
 expect(capabilityView('/login')).toBeNull();
 expect(capabilityView('/home')).toBe('overview');
});
it('resolves dynamic deep links and rejects malformed or inaccessible slugs',()=>{
 expect(resolveWorkspaceSlug('/acme/issues/123',['acme'])).toBe('acme');
 expect(resolveWorkspaceSlug('/review/projects',['acme'])).toBeNull();
 expect(resolveWorkspaceSlug('/%ZZ/projects',['acme'])).toBeNull();
});
