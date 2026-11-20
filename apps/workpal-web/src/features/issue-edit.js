import {el, openDialog} from '../ui.js';
import {createRequirementsForm} from './requirements-form.js';

export function createIssueRequirementsEditor({client, issue, current, onError, onSaved}) {
  const values = item => structuredClone({title:item.title, description:item.description, criteria:item.criteria});
  const equal = (left, right) => JSON.stringify(left) === JSON.stringify(right);
  const issueId = issue.id;
  let baseline = values(issue), revision = issue.revision;
  const form = createRequirementsForm(baseline);
  let intent = null, conflict = false, remote = null, generation = 0;

  return {open(returnFocus) {
    const sequence = ++generation;
    // Busy state belongs to this dialog, while the original intent survives it.
    let busy = false;
    const root = el('form', undefined, {class:'issue-composer'});
    const controls = el('fieldset'), error = el('p', '', {role:'alert'});
    const dialog = openDialog(root, {returnFocus, label:'Edit requirements'});
    dialog.classList.add('issue-create-dialog');
    const valid = () => current() && dialog.open && sequence === generation;
    dialog.addEventListener('close', () => {if (sequence === generation) generation++;});
    const button = (title, action) => {
      const node = el('button', title, {type:'button'});
      node.onclick = action;
      return node;
    };
    const save = el('button', 'Save changes', {type:'submit'}), compare = el('section');
    const reload = button('Reload current', async () => {
      if (busy || intent || !valid()) return;
      busy = true;
      sync();
      try {
        const result = await client.perform('issue.read', {issue_id:issueId});
        if (!valid()) return;
        if (result.state !== 'completed') throw Error('Reading has not been confirmed. Please retry.');
        const local = form.read(), next = values(result.data);
        for (const field of Object.keys(next)) {
          if (!equal(local[field], baseline[field])) next[field] = local[field];
        }
        baseline = values(result.data);
        revision = result.data.revision;
        remote = baseline;
        form.replace(next);
        conflict = false;
        error.textContent = 'Local changes retained. Review before saving.';
      } catch (exception) {
        fail(exception);
      } finally {
        if (valid()) {busy = false; sync();}
      }
    });
    function fail(exception) {
      if (!valid() || exception.code === 'context_changed') return;
      if ([403,404].includes(exception.status)) {
        dialog.close();
        onError(exception);
        return;
      }
      error.textContent = exception.message;
    }
    function sync() {
      controls.disabled = busy || !!intent;
      save.disabled = busy || conflict;
      save.textContent = intent ? 'Retry original request' : 'Save changes';
      reload.hidden = !conflict;
      reload.disabled = busy || !!intent;
      compare.replaceChildren();
      if (remote) {
        compare.append(el('h3', 'Current saved requirements'), el('p', remote.title), el('p', remote.description));
        for (const criterion of remote.criteria) compare.append(el('p', criterion.text));
      }
    }
    controls.append(form.element);
    root.append(el('h2', 'Edit requirements'), controls, compare, error, save, reload, button('Cancel', () => dialog.close()));
    if (intent) error.textContent = 'Saving has not been confirmed. Retry the original request.';
    else if (conflict) error.textContent = 'The issue changed. Your draft is preserved. Reload before saving again.';
    sync();

    root.onsubmit = async event => {
      event.preventDefault();
      if (busy || conflict || !valid()) return;
      if (!intent) {
        const local = form.read(), changed = {};
        for (const field of Object.keys(local)) {
          if (!equal(local[field], baseline[field])) changed[field] = local[field];
        }
        if (!Object.keys(changed).length) {error.textContent = 'No changes to save'; return;}
        if (!local.title.trim() || local.criteria.some(criterion => !criterion.text.trim())) {
          error.textContent = 'Enter a title and nonempty criteria.';
          return;
        }
        intent = {payload:{issue_id:issueId, ...changed}, revision, key:crypto.randomUUID()};
      }
      busy = true;
      sync();
      error.textContent = '';
      try {
        const result = await client.perform('issue.update', intent.payload, {revision:intent.revision, key:intent.key});
        if (!valid()) return;
        if (result.state !== 'completed') throw Error('Save outcome is unknown. Retry the original request.');
        intent = null;
        dialog.close();
        onSaved(result.data);
      } catch (exception) {
        if (!valid()) return;
        if (exception.status === 409) {intent = null; conflict = true; remote = null;}
        else if (exception.status === 400) intent = null;
        fail(exception);
      } finally {
        if (valid()) {busy = false; sync();}
      }
    };
    return dialog;
  }};
}
