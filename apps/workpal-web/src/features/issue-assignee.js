import {createPersonLabel, createPersonPicker} from './people.js';
import {el, openDialog} from '../ui.js';

export function createIssueAssigneeEditor({client, issue, current, onError, onChanged}) {
  const id = issue.id; let target = issue.assignee_user_id;
  const action = 'issue.update';
  const label = 'Change assignee';
  let revision = issue.revision, title = issue.title, assignee = issue.assignee_user_id;
  let intent = null, conflict = false, reached = false, generation = 0;
  return {open(returnFocus) {
    const sequence = ++generation;
    let busy = false;
    const root = el('form', undefined, {class:'issue-composer'});
    const dialog = openDialog(root, {returnFocus, label});
    dialog.classList.add('issue-create-dialog');
    const valid = () => current() && dialog.open && generation === sequence;
    dialog.addEventListener('close', () => {if (generation === sequence) generation++;});
    const heading = el('p', title), fact = el('div'), error = el('p', '', {role:'alert'});
    const controls = el('fieldset');
    const paint = () => fact.replaceChildren(el('p','Current assignee'), createPersonLabel({client,userId:assignee,current:valid,onError}));
    paint();
    controls.append(createPersonPicker({client,value:target,current:valid,onError,onChange:value=>{target=value; reached=false; sync();}}));
    const submit = el('button', 'Save assignee', {type:'submit'});
    const button = (name, fn) => {const b = el('button', name, {type:'button'}); b.onclick = fn; return b;};
    const refresh = button('Refresh issue', () => {if (!valid() || busy) return; dialog.close(); onChanged();});
    const reload = button('Reload current', async () => {
      if (!valid() || busy || intent) return;
      busy = true; sync();
      try {
        const result = await client.perform('issue.read', {issue_id:id});
        if (!valid()) return;
        if (result.state !== 'completed') throw Error('Reading has not been confirmed. Please retry.');
        revision = result.data.revision; title = result.data.title; assignee = result.data.assignee_user_id;
        reached = assignee === target; conflict = false;
        heading.textContent = title;
        paint();
        error.textContent = reached ? 'No changes to save' : 'Review the current issue before submitting.';
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
      submit.textContent = intent ? 'Retry original request' : 'Save assignee';
      controls.disabled = busy || !!intent;
      reload.hidden = !conflict; reload.disabled = busy;
      refresh.hidden = !reached; refresh.disabled = busy;
    }
    root.append(el('h2', label), heading, controls, fact, error, submit, reload, refresh, button('Cancel', () => dialog.close()));
    if (intent) error.textContent = 'Outcome is unknown. Retry the original request.';
    else if (conflict) error.textContent = 'The issue changed. Reload before submitting.';
    else if (reached) error.textContent = 'No changes to save';
    sync();
    root.onsubmit = async event => {
      event.preventDefault();
      if (!valid() || busy || conflict || reached) return;
      if (!intent && target === assignee) {error.textContent='No changes to save'; return;}
      intent ??= {payload:{issue_id:id,assignee_user_id:target}, revision, key:crypto.randomUUID()};
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
