import test from 'node:test';
import assert from 'node:assert/strict';
import '../src/data.js';
const { filterSkills, skills, escapeHtml } = globalThis.WorkpalData;

test('search combines author, category and bookmarked constraints', () => {
  assert.deepEqual(filterSkills(skills, ' ANTHROPIC ', '研发与质量', true, ['webapp-testing']).map(s => s.id), ['webapp-testing']);
  assert.equal(filterSkills(skills, 'anthropic', '需求与设计').length, 0);
});
test('search supports Chinese use cases and empty results', () => {
  assert.ok(filterSkills(skills, '验收').some(s => s.id === 'brainstorming'));
  assert.equal(filterSkills(skills, 'nonexistent-example').length, 0);
  assert.equal(filterSkills(skills, '', '全部', true, []).length, 0);
});
test('user content is escaped in text and attribute contexts', () => {
  assert.equal(escapeHtml('<img src=x onerror="alert(1)"> & \'test\''), '&lt;img src=x onerror=&quot;alert(1)&quot;&gt; &amp; &#39;test&#39;');
});
