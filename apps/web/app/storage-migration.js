export function migrateStorage(storage) {
  const legacy = 'multi' + 'ca';
  for (const key of Object.keys(storage)) {
    if (!key.includes(legacy)) continue;
    const target = key.replaceAll(legacy, 'workpal');
    if (storage.getItem(target) === null) storage.setItem(target, storage.getItem(key));
  }
}
try { if (typeof window !== 'undefined') for (const storage of [window.localStorage, window.sessionStorage]) migrateStorage(storage); }
catch { /* Existing storage remains untouched if storage is unavailable. */ }

// Apply the agreed FWD default once to existing browser profiles as well.
// Later explicit theme choices remain persistent.
try {
  if (typeof window !== 'undefined' && !window.localStorage.getItem('workpal_fwd_default_v1')) {
    const saved = JSON.parse(window.localStorage.getItem('workpal_appearance') || '{}');
    window.localStorage.setItem('workpal_appearance', JSON.stringify({
      ...saved, state: {...saved.state, theme: 'fwd'}, version: saved.version ?? 0,
    }));
    window.localStorage.setItem('workpal_fwd_default_v1', '1');
  }
} catch { /* Storage restrictions must not prevent sign-in. */ }
