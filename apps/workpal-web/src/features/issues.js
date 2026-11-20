import {createIssueHierarchy} from './issue-hierarchy.js';
import {createIssueDependencies} from './issue-dependencies.js';
import {createIssueTransitionEditor} from './issue-transition.js';
import {createIssueTransitionHistory} from './issue-status-history.js';
import {createPersonLabel} from './people.js';
import {createIssueAssigneeEditor} from './issue-assignee.js';
import {createIssueArchiveControl} from './issue-archive.js';
import {createIssueRequirementsEditor} from './issue-edit.js';
import {createIssueComposer} from './issue-create.js';
import {el} from '../ui.js';

export async function showIssues({client, content, current, onError}) {
  content.replaceChildren(el('p', 'Loading issues…', {role:'status'}));
  let canEdit = false, actions = [];
  let listSequence = 0, detailSequence = 0, historySequence = 0, cursor = 0;
  const query = el('input', undefined, {type:'search', maxlength:'300', 'aria-label':'Search issues', placeholder:'Search issues'});
  const archived = el('input', undefined, {type:'checkbox'});
  const label = el('label', 'Include archived');
  label.prepend(archived);
  const rows = el('div'), detail = el('section', undefined, {class:'issue-detail'});
  const status = el('p', undefined, {role:'status'});
  const more = button('Load more', () => load(true));
  const toolbar = el('div', undefined, {class:'project-toolbar'});
  toolbar.append(query, label, button('Refresh issues', () => load()));
  content.replaceChildren(el('h1', 'Issues'), toolbar, status, rows, more, detail);
  query.oninput = () => load();
  archived.onchange = () => load();

  function button(title, action) {
    const node = el('button', title, {type:'button'});
    node.onclick = action;
    return node;
  }
  async function call(action, payload, isCurrent = current) {
    const result = await client.perform(action, payload, {current:isCurrent});
    if (result.state !== 'completed') throw Error('Reading has not been confirmed. Please retry.');
    return result.data;
  }
  function failure(target, error, retry) {
    if (error.code === 'context_changed') return;
    if (error.status === 403 || error.status === 404) {
      ++listSequence; ++detailSequence; ++historySequence;
      rows.replaceChildren(); detail.replaceChildren();
      onError(error);
      return;
    }
    target.replaceChildren(el('p', error.message, {role:'alert'}), button('Retry', retry));
  }
  function fields(target, fact) {
    target.append(el('h3', fact.title), el('p', fact.description));
    const criteria = el('ul');
    for (const criterion of fact.criteria) criteria.append(el('li', `${criterion.key}: ${criterion.text}`));
    target.append(criteria);
  }
  async function load(append = false) {
    const sequence = ++listSequence;
    ++detailSequence; ++historySequence;
    detail.replaceChildren();
    if (!append) { cursor = 0; rows.replaceChildren(); }
    more.hidden = true;
    status.replaceChildren(el('span', 'Loading issues…'));
    try {
      const data = await call('issue.list', {query:query.value, include_archived:archived.checked, cursor, limit:20});
      if (!current() || sequence !== listSequence) return;
      for (const issue of data.items) {
        const row = el('div', undefined, {class:'project-row'});
        const category = issue.status_category.replaceAll('_', ' ');
        const categoryLabel = category.charAt(0).toUpperCase() + category.slice(1);
        row.append(button(`${issue.title} (#${issue.id})`, () => read(issue.id)),
          el('span', `${categoryLabel} · Requirements version ${issue.requirements_revision} · ${issue.archived ? 'Archived' : 'Active'}`));
        rows.append(row);
      }
      cursor = data.next_cursor;
      more.hidden = !cursor;
      status.textContent = rows.childElementCount ? '' : 'No issues found.';
    } catch (error) {
      if (current() && sequence === listSequence) failure(status, error, () => load(append));
    }
  }
  async function read(id) {
    const sequence = ++detailSequence;
    ++historySequence;
    detail.replaceChildren(el('p', 'Loading issue…', {role:'status'}));
    try {
      const issue = await call('issue.read', {issue_id:id}, () => current() && sequence === detailSequence);
      if (!current() || sequence !== detailSequence) return;
      const project = await call('project.read', {project_id:issue.project_id}, () => current() && sequence === detailSequence);
      if (!current() || sequence !== detailSequence) return;
      const state = issue.workflow_snapshot.definition.states.find(item => item.key === issue.status_key);
      detail.replaceChildren(el('h2', `Issue #${issue.id}`));
      fields(detail, issue);
      const assignee = el('p','Assignee: ');
      assignee.append(createPersonLabel({client,userId:issue.assignee_user_id,current:()=>current()&&sequence===detailSequence,onError}));
      detail.append(assignee);
      if(actions.includes('issue.transition')){
        const editor=createIssueTransitionEditor({client,issue,current:()=>current()&&sequence===detailSequence,onError:error=>failure(detail,error,()=>read(id)),onChanged:async()=>{
          if(!current()||sequence!==detailSequence)return;
          const pending=load(), token=detailSequence;await pending;
          if(current()&&token===detailSequence)await read(id);
        }});
        const change=button('Change status',()=>editor.open(change));detail.append(change);
      }
      if(canEdit){
        const editor=createIssueAssigneeEditor({client,issue,current:()=>current()&&sequence===detailSequence,onError,onChanged:async()=>{
          if(!current()||sequence!==detailSequence)return;
          const pending=load(), token=detailSequence; await pending;
          if(current()&&token===detailSequence)await read(id);
        }});
        const change=button('Change assignee',()=>editor.open(change));detail.append(change);
      }
      if (actions.includes(issue.archived ? 'issue.restore' : 'issue.archive')) {
        const control = createIssueArchiveControl({client, issue,
          current:() => current() && sequence === detailSequence,
          onError:error => failure(detail, error, () => read(id)),
          onChanged:async () => {
            if (!current() || sequence !== detailSequence) return;
            const include = archived.checked;
            const pending = load(), token = detailSequence;
            await pending;
            if (!current() || token !== detailSequence) return;
            if (include || issue.archived) await read(id);
            if (document.activeElement === document.body) toolbar.querySelectorAll('button')[0]?.focus();
          }});
        const archive = button(issue.archived ? 'Restore issue' : 'Archive issue', () => control.open(archive));
        detail.append(archive);
      }
      if (canEdit) {
        const editor = createIssueRequirementsEditor({
          client, issue, current:() => current() && sequence === detailSequence, onError,
          onSaved:async () => {
            const pending = load(), token = detailSequence;
            await pending;
            if (current() && token === detailSequence) await read(id);
          }
        });
        const edit = button('Edit requirements', () => editor.open(edit));
        detail.append(edit);
      }
      detail.append(el('p', `Project: ${project.name}`), el('p', issue.archived ? 'Archived' : 'Active'),
        el('p', `Status: ${state?.label ?? issue.status_key}`),
        el('p', `Current requirements version: ${issue.requirements_revision}`));
      if (issue.status_category === 'blocked') {
        detail.append(el('p', `Blocking reason: ${issue.blocked_reason}`));
        const owner=el('p','Blocked owner: ');
        owner.append(createPersonLabel({client,userId:issue.blocked_owner_user_id,current:()=>current()&&sequence===detailSequence,onError:error=>failure(detail,error,()=>read(id))}));
        detail.append(owner);
      }
      if(actions.includes('issue.transitions.list')) detail.append(createIssueTransitionHistory({client,issue,current:()=>current()&&sequence===detailSequence,onError:error=>failure(detail,error,()=>read(id))}));
      if(actions.includes('issue.dependency.list')) detail.append(createIssueDependencies({client,issue,actions,current:()=>current()&&sequence===detailSequence,onError:error=>failure(detail,error,()=>read(id)),onChanged:async()=>{if(!current()||sequence!==detailSequence)return;const pending=load(),token=detailSequence;await pending;if(current()&&token===detailSequence)await read(id);}}));
      if(actions.includes('issue.children.list')) detail.append(createIssueHierarchy({client,issue,actions,onChanged:async()=>{if(!current()||sequence!==detailSequence)return;const pending=load(),token=detailSequence;await pending;if(current()&&token===detailSequence)await read(id);},current:()=>current()&&sequence===detailSequence,onError:error=>failure(detail,error,()=>read(id)),onNavigate:async targetId=>{const pending=read(targetId),token=detailSequence;await pending;if(current()&&token===detailSequence&&document.activeElement===document.body){const heading=detail.querySelector('h2');heading?.setAttribute('tabindex','-1');heading?.focus();}}}));
      const history = el('section', undefined, {class:'issue-history', 'aria-label':'Requirements history'});
      detail.append(history);
      await version(issue.requirements_revision);
      async function version(number) {
        const request = ++historySequence;
        history.replaceChildren(el('p', 'Loading requirements…', {role:'status'}));
        try {
          const fact = await call('issue.requirements.read', {issue_id:id, number});
          if (!current() || sequence !== detailSequence || request !== historySequence) return;
          history.replaceChildren(el('h2', `Requirements version ${fact.number}`));
          fields(history, fact);
          const previous = button('Previous version', () => version(fact.number - 1));
          const next = button('Next version', () => version(fact.number + 1));
          previous.disabled = fact.number <= 1;
          next.disabled = fact.number >= issue.requirements_revision;
          history.append(previous, next);
        } catch (error) {
          if (current() && sequence === detailSequence && request === historySequence) failure(history, error, () => version(number));
        }
      }
    } catch (error) {
      if (current() && sequence === detailSequence) failure(detail, error, () => read(id));
    }
  }
  try {
    const catalog = await client.catalog();
    if (!current()) return;
    actions = catalog.actions.map(item => item.action_id);
    canEdit = catalog.actions.some(action => action.action_id === 'issue.update');
    if (catalog.actions.some(a => a.action_id === 'issue.create')) {
      const composer = createIssueComposer({client, current, onError, onCreated:async issue => {
        query.value=''; archived.checked=false;
        const pending=load();
        const sequence=detailSequence;
        await pending;
        if(current() && sequence===detailSequence) await read(issue.id);
      }});
      const create=button('Create issue', () => composer.open(create));
      toolbar.append(create);
    }
  } catch(error) { if(current()) failure(status,error,()=>showIssues({client,content,current,onError})); }
  await load();
}
