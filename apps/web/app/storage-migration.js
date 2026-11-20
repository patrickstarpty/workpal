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
