import {createPersonPicker} from './people.js';
import {createRequirementsForm} from './requirements-form.js';
import {el, openDialog} from '../ui.js';

export function createIssueComposer({client, current, onError, onCreated}) {
  let draft = {title:'', description:'', criteria:[], project_id:0, assignee_user_id:0};
  let requirements = createRequirementsForm();
  let selected = {};
  let generation = 0, intent = null, busy = false;
  const button = (name, action) => {
    const node = el('button', name, {type:'button'});
    node.onclick = action;
    return node;
  };
  return {open(returnFocus) {
    const sequence = ++generation;
    const valid = () => current() && sequence === generation;
    const form = el('form', undefined, {class:'issue-composer'});
    const error = el('p', '', {role:'alert'});
    const errors = new Map();
    function setError(source, message) {
      if (message) errors.set(source, message); else errors.delete(source);
      error.textContent = [...errors.values()].join('\n');
    }
    if (intent) setError('save', 'Creation has not been confirmed. Retry the original request.');
    const controls = el('fieldset');
    const dialog = openDialog(form, {returnFocus, label:'Create issue'});
    dialog.classList.add('issue-create-dialog');
    dialog.addEventListener('close', () => { ++generation; busy = false; });
    const save = el('button', intent ? 'Retry original request' : 'Create issue', {type:'submit'});
    function failure(e, source='save') {
      if (!valid() || e.code === 'context_changed') return;
      if ([403,404].includes(e.status)) {
        draft = {title:'', description:'', criteria:[], project_id:0, assignee_user_id:0};
        intent = null; selected = {}; requirements=createRequirementsForm(); dialog.close(); onError(e); return;
      }
      setError(source, e.message);
    }
    function selector(action, name, idField, selectedField, max) {
      const section = el('section');
      const search = el('input', undefined, {type:'search', 'aria-label':`Search ${name}`, placeholder:`Search ${name}`, maxlength:String(max)});
      const emptyChoice = selectedField === 'project_id' ? 'Select a project.' : 'Unassigned';
      const chosen = el('p', selected[selectedField] ?? emptyChoice);
      const rows = el('div');
      const status = el('p', '', {role:'status'});
      let cursor = 0, request = 0, retry = null;
      const more = button(`Load more ${name}`, () => load(true));
      section.append(el('h3', selectedField === 'project_id' ? 'Project' : 'Assignee'));
      if (selectedField === 'assignee_user_id') section.append(button('Unassigned', () => {
        draft[selectedField]=0; delete selected[selectedField]; chosen.textContent='Unassigned';
      }));
      section.append(search, chosen, status, rows, more); controls.append(section);
      search.oninput = () => load();
      async function load(append=false) {
        const token = ++request;
        retry?.remove(); retry=null;
        if (!append) {cursor=0; rows.replaceChildren();}
        more.hidden=true;
        status.textContent=`Loading ${name}…`;
        try {
          const result = await client.perform(action, {query:search.value, cursor, limit:20, ...(action==='project.list'?{include_archived:false}:{})});
          if (!valid() || token!==request) return;
          if (result.state!=='completed') throw Error('Reading has not been confirmed. Please retry.');
          setError(selectedField, '');
          for (const item of result.data.items) {
            const title = `${item.name ?? item.username} (#${item[idField]})`;
            const row = el('div', undefined, {class:'issue-picker-option'});
            row.append(button(title, () => {
              draft[selectedField]=item[idField]; selected[selectedField]=title;
              chosen.textContent=title; save.disabled=!draft.project_id;
            }));
            if (item.description) row.append(el('p', item.description));
            rows.append(row);
            if (draft[selectedField] === item[idField]) {
              selected[selectedField]=title; chosen.textContent=title;
            }
          }
          cursor=result.data.next_cursor; more.hidden=!cursor;
          status.textContent = rows.childElementCount ? '' : 'No results found.';
        } catch(e) {
          if(valid() && token===request) {
            status.textContent=''; failure(e, selectedField);
            if (valid()) {retry=button('Retry', () => load(append)); rows.append(retry);}
          }
        }
      }
      load();
    }
    selector('project.list', 'projects', 'id', 'project_id', 200);
    controls.append(createPersonPicker({client,value:draft.assignee_user_id,current:valid,onChange:value=>{draft.assignee_user_id=value;},onError:e=>failure(e,'assignee_user_id')}));
    controls.append(requirements.element);
    controls.disabled=!!intent;
    save.disabled=!draft.project_id;
    form.append(el('h2','Create issue'), controls, error, save, button('Cancel',()=>dialog.close()));
    form.onsubmit=async event => {
      event.preventDefault();
      if(busy || !valid()) return;
      Object.assign(draft, requirements.read());
      if(!intent) {
        if(!draft.project_id || !draft.title.trim() || draft.criteria.some(c=>!c.text.trim())) {setError('save', 'Enter a project, title and nonempty criteria.'); return;}
        intent={key:crypto.randomUUID(), payload:{project_id:draft.project_id,title:draft.title,description:draft.description,criteria:draft.criteria,assignee_user_id:draft.assignee_user_id}};
      }
      busy=true; controls.disabled=true; save.disabled=true;
      setError('save', '');
      try {
        const result=await client.perform('issue.create',intent.payload,{key:intent.key});
        if(!valid()) return;
        if(result.state!=='completed') throw Error('Creation outcome is unknown. Retry the original request.');
        intent=null; selected={}; draft={title:'',description:'',criteria:[],project_id:0,assignee_user_id:0}; requirements=createRequirementsForm();
        dialog.close(); onCreated(result.data);
      } catch(e) {
        if(!valid()) return;
        if([400,409].includes(e.status)) {intent=null; controls.disabled=false;}
        failure(e);
      } finally {
        if(valid()) {busy=false; save.disabled=false; save.textContent=intent?'Retry original request':'Create issue';}
      }
    };
    return dialog;
  }};
}
