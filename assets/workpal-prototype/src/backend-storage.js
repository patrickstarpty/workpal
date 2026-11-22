// Loaded only by the Python service; offline exports keep browser storage.
// Preserve the synchronous save contract so UI success follows a committed write.
globalThis.WorkpalStorage = (() => {
  const revisions = new Map();
  function request(method, path, body) {
    const xhr = new XMLHttpRequest();
    try {
      xhr.open(method, '/api/records' + path, false);
      xhr.setRequestHeader('X-Workpal-Token', WorkpalBackend.token);
      if (body) xhr.setRequestHeader('Content-Type', 'application/json');
      xhr.send(body ? JSON.stringify(body) : null);
    } catch { throw failure('The local service is unavailable. Keep this tab open and restart the service.'); }
    let result;
    try { result = JSON.parse(xhr.responseText); } catch { throw failure('The local service returned an invalid response.'); }
    if (xhr.status !== 200) throw failure(result.error || 'Your changes could not be saved.');
    return result;
  }
  function failure(message) {
    const error = Error(message);
    error.code = 'WORKSPACE_CONFLICT';
    return error;
  }
  return {
    get length() { return request('GET', '').keys.length; },
    key(index) { return request('GET', '').keys[index] ?? null; },
    getItem(key) {
      const result = request('GET', '/' + encodeURIComponent(key));
      revisions.set(key, result.revision);
      return result.value;
    },
    setItem(key, value) {
      // An unseen key is a create, never an unconditional overwrite.
      const result = request('PUT', '/' + encodeURIComponent(key), {value: String(value), revision: revisions.get(key) ?? 0});
      revisions.set(key, result.revision);
    }
  };
})();
