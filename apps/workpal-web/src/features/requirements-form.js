import {el} from '../ui.js';

export function createRequirementsForm(value = {}) {
  let draft, number = 0;
  const used = new Set(), numbers = new Map(), controls = el('div');
  function button(name, action) {
    const node = el('button', name, {type:'button'});
    node.onclick = action;
    return node;
  }
  function field(name, value, max, change, tag = 'input') {
    const input = el(tag, undefined, {'aria-label':name, maxlength:String(max)});
    input.value = value;
    input.oninput = () => change(input.value);
    const label = el('label', name);
    label.append(input);
    controls.append(label);
    return input;
  }
  function replace(value) {
    draft = structuredClone({title:'', description:'', criteria:[], ...value});
    // Reloading values preserves every key already used in this draft.
    for (const criterion of draft.criteria) {
      used.add(criterion.key);
      if (!numbers.has(criterion.key)) numbers.set(criterion.key, ++number);
      criterion.number = numbers.get(criterion.key);
    }
    controls.replaceChildren();
    field('Title', draft.title, 300, v => draft.title=v).required=true;
    field('Description', draft.description, 20000, v => draft.description=v, 'textarea');
    const criteria = el('div');
    controls.append(criteria);
    function renderCriteria() {
      criteria.replaceChildren();
      for (const item of draft.criteria) {
        const row = el('div');
        const input = el('textarea', undefined, {'aria-label':`Acceptance criterion ${item.number}`, maxlength:'2000', required:''});
        input.value = item.text;
        input.oninput = () => item.text = input.value;
        const label = el('label', `Acceptance criterion ${item.number}`);
        label.append(input);
        row.append(label, button(`Remove criterion ${item.number}`, () => {
          draft.criteria = draft.criteria.filter(criterion => criterion !== item);
          renderCriteria();
        }));
        criteria.append(row);
      }
      addCriterion.disabled = draft.criteria.length >= 100;
    }
    const addCriterion = button('Add criterion', () => {
      if (draft.criteria.length >= 100) return;
      number++;
      while (used.has(`criterion_${number}`)) number++;
      const key = `criterion_${number}`;
      used.add(key);
      numbers.set(key, number);
      draft.criteria.push({number, key, text:''});
      renderCriteria();
    });
    controls.append(addCriterion);
    renderCriteria();
  }
  replace(value);
  return {
    element:controls,
    replace,
    read:() => ({
      title:draft.title,
      description:draft.description,
      criteria:draft.criteria.map(({key, text}) => ({key, text}))
    })
  };
}
