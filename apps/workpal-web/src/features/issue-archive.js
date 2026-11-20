import {el, openDialog} from '../ui.js';

export function createIssueArchiveControl({client, issue, current, onError, onChanged}) {
  const id = issue.id, target = !issue.archived;
  const action = target ? 'issue.archive' : 'issue.restore';
  const label = target ? 'Archive issue' : 'Restore issue';
  let revision = issue.revision, title = issue.title, archived = issue.archived;
  let intent = null, conflict = false, reached = false, generation = 0;
  return {open(returnFocus) {
    const sequence = ++generation;
    let busy = false;
    const root = el('form', undefined, {class:'issue-composer'});
    const dialog = openDialog(root, {returnFocus, label});
    dialog.classList.add('issue-create-dialog');
    const valid = () => current() && dialog.open && generation === sequence;
    dialog.addEventListener('close', () => {if (generation === sequence) generation++;});
    const heading = el('p', title), fact = el('p', archived ? 'Archived' : 'Active'), error = el('p', '', {role:'alert'});
    const submit = el('button', label, {type:'submit'});
    const button = (name, fn) => {const b = el('button', name, {type:'button'}); b.onclick = fn; return b;};
    const refresh = button('Refresh issue', () => {if (!valid() || busy) return; dialog.close(); onChanged();});
    const reload = button('Reload current', async () => {
      if (!valid() || busy || intent) return;
      busy = true; sync();
      try {
        const result = await client.perform('issue.read', {issue_id:id});
        if (!valid()) return;
        if (result.state !== 'completed') throw Error('Reading has not been confirmed. Please retry.');
        revision = result.data.revision; title = result.data.title; archived = result.data.archived;
        reached = archived === target; conflict = false;
        heading.textContent = title;
        fact.textContent = archived ? 'Archived' : 'Active';
        error.textContent = reached ? (target ? 'Already archived' : 'Already active') : 'Review the current issue before submitting.';
      } catch (exception) {fail(exception);} finally {if (valid()) {busy = false; sync();}}
    });
    function fail(exception) {
      if (!valid() || exception.code === 'context_changed') return;
      if ([403,404].includes(exception.status)) {dialog.close(); onError(exception); return;}
      error.textContent = exception.message;
    }
    function sync() {
      submit.disabled = busy || conflict || reached;
      submit.hidden = reached;
      submit.textContent = intent ? 'Retry original request' : label;
      reload.hidden = !conflict; reload.disabled = busy;
      refresh.hidden = !reached; refresh.disabled = busy;
    }
    root.append(el('h2', label), heading, el('p', target ? 'Archiving hides this issue from active lists. Its status and requirements stay unchanged.' : 'Restoring shows this issue in active lists. Its status and requirements stay unchanged.'), fact, error, submit, reload, refresh, button('Cancel', () => dialog.close()));
    if (intent) error.textContent = 'Outcome is unknown. Retry the original request.';
    else if (conflict) error.textContent = 'The issue changed. Reload before submitting.';
    else if (reached) error.textContent = target ? 'Already archived' : 'Already active';
    sync();
    root.onsubmit = async event => {
      event.preventDefault();
      if (!valid() || busy || conflict || reached) return;
      intent ??= {payload:{issue_id:id}, revision, key:crypto.randomUUID()};
      busy = true; sync(); error.textContent = '';
      try {
        const result = await client.perform(action, intent.payload, {revision:intent.revision,key:intent.key});
        if (!valid()) return;
        if (result.state !== 'completed') throw Error('Outcome is unknown. Retry the original request.');
        intent = null; dialog.close(); onChanged();
      } catch (exception) {
        if (!valid()) return;
        if (exception.status === 409) {intent = null; conflict = true;}
        else if (exception.status === 400) intent = null;
        fail(exception);
      } finally {if (valid()) {busy = false; sync();}}
    };
    return dialog;
  }};
}
