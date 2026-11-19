// Workspace integration configuration. Authorization is completed by a future server transport.
globalThis.WorkpalIntegrations = (() => {
  const repositories = db => db.repositories || [];
  const setups = db => db.integrationSetups || [];
  const text = value => typeof value === 'string' ? value.trim() : '';

  function repositoryKey(value) {
    const raw = text(value);
    if (!raw || raw.length > 2048 || /[\s\\?#%]/.test(raw)) throw Error('Enter an HTTPS or SSH repository URL without query parameters or credentials.');
    const scp = raw.match(/^git@([^/:]+):(.+)$/);
    let url;
    try { url = new URL(scp ? 'ssh://git@' + scp[1] + '/' + scp[2] : raw); }
    catch { throw Error('Enter an HTTPS or SSH repository URL.'); }
    if (!['https:', 'ssh:'].includes(url.protocol)) throw Error('Use an HTTPS or SSH repository URL.');
    if (url.password || (url.protocol === 'https:' && url.username) || (url.protocol === 'ssh:' && url.username !== 'git')) throw Error('Repository URLs must not contain credentials. Use git as the SSH user.');
    const rawPath = scp ? scp[2] : raw.replace(/^[a-z]+:\/\/[^/]+\//i, '');
    if (rawPath.split('/').some(segment => segment === '.' || segment === '..')) throw Error('Enter a repository path without relative segments.');
    const path = url.pathname.replace(/^\//, '').replace(/\/$/, '').replace(/\.git$/i, '');
    const segments = path.split('/'), hostname = url.hostname.toLowerCase();
    if (!hostname || segments.length < 2 || segments.some(segment => !/^[A-Za-z0-9_~.-]+$/.test(segment) || /^\.+$/.test(segment))) throw Error('Include the repository owner and name in the URL.');
    if (hostname === 'github.com' && segments.length !== 2) throw Error('Use the repository URL, not a file, issue or pull request URL.');
    const port = url.port && !(url.protocol === 'ssh:' && url.port === '22') ? ':' + url.port : '';
    return hostname + port + '/' + (hostname === 'github.com' ? path.toLowerCase() : path);
  }

  function saveRepository(db, data) {
    const list = repositories(db), id = text(data.id);
    if (id && !list.some(record => record.id === id)) throw Error('This repository is no longer available.');
    const url = text(data.url), key = repositoryKey(url), description = text(data.description);
    if (description.length > 1000) throw Error('Keep the repository description under 1,000 characters.');
    if (list.some(record => record.id !== id && repositoryKey(record.url) === key)) throw Error('This repository is already in the workspace.');
    const record = {id: id || 'REPO-' + crypto.randomUUID(), url, description};
    db.repositories = id ? list.map(item => item.id === id ? record : item) : [...list, record];
    return record;
  }

  function removeRepository(db, id) {
    if (!repositories(db).some(record => record.id === id)) throw Error('This repository is no longer available.');
    db.repositories = repositories(db).filter(record => record.id !== id);
  }

  function saveSetup(db, data) {
    const list = setups(db), id = text(data.id), previous = list.find(record => record.id === id);
    if (id && !previous) throw Error('This account setup is no longer available.');
    if (!['jira', 'github'].includes(data.provider)) throw Error('Choose an available app.');
    if (!['team', 'personal'].includes(data.scope)) throw Error('Choose Team accounts or My accounts.');
    const name = text(data.name);
    if (!name || name.length > 100) throw Error('Enter an account name of up to 100 characters.');
    if (list.some(record => record.id !== id && record.provider === data.provider && record.scope === data.scope && record.name.toLowerCase() === name.toLowerCase())) throw Error('This account setup already exists.');
    const record = {id: id || 'SETUP-' + crypto.randomUUID(), provider: data.provider, scope: data.scope, name, status: 'authorization-required', createdBy: 'Patrick', createdAt: previous?.createdAt || Date.now()};
    db.integrationSetups = id ? list.map(item => item.id === id ? record : item) : [...list, record];
    return record;
  }

  function removeSetup(db, id) {
    if (!setups(db).some(record => record.id === id)) throw Error('This account setup is no longer available.');
    db.integrationSetups = setups(db).filter(record => record.id !== id);
  }

  function savePreferences(db, data) {
    const current = db.codeSettings || {}, result = {...current};
    for (const [key, choices, fallback] of [
      ['reading', ['off', 'requested'], 'off'],
      ['association', ['off', 'issue'], 'off'],
      ['afterMerge', ['keep', 'complete'], 'keep'],
    ]) {
      const value = data[key] ?? current[key] ?? fallback;
      if (!choices.includes(value)) throw Error('Choose a valid code preference for ' + key + '.');
      result[key] = value;
    }
    for (const key of ['prSidebar', 'coAuthor']) {
      const value = data[key] ?? current[key] ?? true;
      if (typeof value !== 'boolean') throw Error('Choose an on or off setting for ' + key + '.');
      result[key] = value;
    }
    db.codeSettings = result;
    return result;
  }

  return {repositories, repositoryKey, saveRepository, removeRepository, setups, saveSetup, removeSetup, savePreferences};
})();
