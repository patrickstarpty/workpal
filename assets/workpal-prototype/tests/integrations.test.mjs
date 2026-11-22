import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import vm from 'node:vm';
import {randomUUID} from 'node:crypto';

const scripts = ['data', 'integrations', 'code-delivery', 'model'].map(name => readFileSync(new URL('../src/' + name + '.js', import.meta.url), 'utf8'));
function storage() {
  const values = new Map();
  return {get length() {return values.size;}, key: i => [...values.keys()][i], getItem: k => values.get(k) ?? null, setItem: (k, v) => values.set(k, v)};
}
function setup(localStorage = storage()) {
  const context = vm.createContext({URL, crypto: {randomUUID}, localStorage});
  for (const script of scripts) vm.runInContext(script, context);
  return {s: context.WorkpalStudio, api: context.WorkpalIntegrations, code: context.WorkpalCode, localStorage};
}

test('repository catalog adds, edits and removes without changing project resources or review history', () => {
  const {s, api} = setup();
  s.db.notes.push({text: 'Keep review notes'});
  s.db.projectSettings[0].resources = [{id: 'resource', kind: 'repository', url: 'https://github.com/acme/code'}];
  const history = JSON.stringify({notes: s.db.notes, projects: s.db.projectSettings, runs: s.db.runs});
  const first = api.saveRepository(s.db, {url: 'https://github.com/acme/code', description: '<b>Code</b>', token: 'not-saved'});
  assert.equal(first.description, '<b>Code</b>');
  assert.equal(first.token, undefined);
  const updated = api.saveRepository(s.db, {id: first.id, url: 'git@github.com:acme/code.git', description: 'Changed'});
  assert.equal(updated.id, first.id);
  assert.equal(api.repositories(s.db).length, 1);
  api.removeRepository(s.db, first.id);
  assert.equal(api.repositories(s.db).length, 0);
  assert.equal(JSON.stringify({notes: s.db.notes, projects: s.db.projectSettings, runs: s.db.runs}), history);
});

test('repository duplicate identity handles HTTPS, SSH, GitHub casing, and nested GitLab paths', () => {
  const {s, api} = setup();
  api.saveRepository(s.db, {url: 'https://github.com/Acme/Code.git/'});
  for (const url of ['git@github.com:acme/code.git', 'ssh://git@github.com:22/acme/code', 'https://GITHUB.com/acme/code/', 'ssh://git@GITHUB.COM/ACME/Code.git']) {
    assert.throws(() => api.saveRepository(s.db, {url}), /already/);
  }
  api.saveRepository(s.db, {url: 'https://gitlab.example.com/Group/nested/Repo.git'});
  assert.throws(() => api.saveRepository(s.db, {url: 'git@gitlab.example.com:Group/nested/Repo'}), /already/);
  api.saveRepository(s.db, {url: 'ssh://git@gitlab.example.com:2222/Group/nested/Repo'});
  assert.equal(api.repositories(s.db).length, 3);
});

test('unsafe or malformed repository values are rejected atomically', () => {
  const {s, api} = setup();
  for (const url of [
    'javascript:alert(1)', 'file:///tmp/repository', 'http://github.com/a/b',
    'https://token@github.com/a/b', 'https://user:token@github.com/a/b',
    'ssh://secret@git.example.com/a/b', 'ssh://git:secret@git.example.com/a/b',
    'https://github.com/a/b?token=secret', 'https://github.com/a/b#secret',
    'git@github.com:a/b?token=secret', 'https://github.com/a',
    'https://github.com/a/b/pull/1', 'https://github.com/a/../b/c',
    'https://github.com/a/%2e%2e/b', 'https://github.com/a/b\nc',
    'https://github.com/a//b', 'https://github.com/a/b\\c',
  ]) {
    const before = JSON.stringify(s.db);
    assert.throws(() => api.saveRepository(s.db, {url}), undefined, url);
    assert.equal(JSON.stringify(s.db), before);
  }
  assert.throws(() => api.saveRepository(s.db, {id: 'missing', url: 'https://github.com/a/b'}), /no longer/);
});

test('Jira and GitHub setups retain only configuration and never report authorization success', () => {
  const {s, api} = setup();
  const record = api.saveSetup(s.db, {provider: 'jira', scope: 'team', name: 'Engineering', token: 'secret', status: 'connected'});
  assert.equal(record.status, 'authorization-required');
  assert.equal(record.token, undefined);
  assert.equal(record.createdBy, 'Patrick');
  assert.throws(() => api.saveSetup(s.db, {provider: 'jira', scope: 'team', name: ' engineering '}), /already/);
  api.saveSetup(s.db, {provider: 'jira', scope: 'personal', name: 'Engineering'});
  api.saveSetup(s.db, {provider: 'github', scope: 'team', name: 'Engineering'});
  const updated = api.saveSetup(s.db, {id: record.id, provider: 'jira', scope: 'team', name: 'Delivery'});
  assert.equal(updated.createdAt, record.createdAt);
  api.removeSetup(s.db, record.id);
  assert.equal(api.setups(s.db).length, 2);
  const before = JSON.stringify(s.db);
  for (const data of [{provider: 'other', scope: 'team', name: 'Invalid'}, {provider: 'jira', scope: 'all', name: 'Invalid'}, {provider: 'jira', scope: 'team', name: ''}]) assert.throws(() => api.saveSetup(s.db, data));
  assert.equal(JSON.stringify(s.db), before);
});

test('code preferences preserve prior delivery settings and fail without partial mutation', () => {
  const {s, api} = setup();
  s.db.codeSettings = {reading: 'off', association: 'off', afterMerge: 'complete', retained: 'Keep'};
  api.savePreferences(s.db, {reading: 'requested', association: 'issue', prSidebar: false, coAuthor: true});
  assert.equal(s.db.codeSettings.afterMerge, 'complete');
  assert.equal(s.db.codeSettings.retained, 'Keep');
  assert.equal(s.db.codeSettings.prSidebar, false);
  const before = JSON.stringify(s.db.codeSettings);
  assert.throws(() => api.savePreferences(s.db, {reading: 'off', afterMerge: 'invalid'}));
  assert.throws(() => api.savePreferences(s.db, {coAuthor: 'on'}));
  assert.equal(JSON.stringify(s.db.codeSettings), before);
});

test('configuration persists across reloads and remains workspace scoped', () => {
  const {s, api, localStorage} = setup();
  const repo = api.saveRepository(s.db, {url: 'https://github.com/acme/code'});
  api.saveSetup(s.db, {provider: 'jira', scope: 'team', name: 'TAP Jira'});
  api.savePreferences(s.db, {prSidebar: false});
  s.save();
  const reloaded = setup(localStorage);
  assert.equal(reloaded.api.repositories(reloaded.s.db)[0].id, repo.id);
  assert.equal(reloaded.api.setups(reloaded.s.db)[0].status, 'authorization-required');
  assert.equal(reloaded.s.db.codeSettings.prSidebar, false);
  const other = reloaded.s.createWorkspace('Other integration workspace');
  reloaded.s.selectWorkspace(other);
  assert.equal(reloaded.api.repositories(reloaded.s.db).length, 0);
  assert.equal(reloaded.api.setups(reloaded.s.db).length, 0);
  reloaded.api.saveRepository(reloaded.s.db, {url: 'git@github.com:other/repo.git'});
  reloaded.s.save();
  reloaded.s.selectWorkspace('tap');
  assert.equal(reloaded.api.repositories(reloaded.s.db).length, 1);
  assert.equal(reloaded.api.repositories(reloaded.s.db)[0].id, repo.id);
  assert.equal(reloaded.api.setups(reloaded.s.db)[0].name, 'TAP Jira');
});

function approvedCodeDelivery() {
  const {s, api, code} = setup();
  const project = s.db.projectSettings.find(p => p.project === 'TAP');
  project.deliveryRules = {completion: 'merged', target: 'main'};
  api.savePreferences(s.db, {coAuthor: false, afterMerge: 'complete'});
  const catalog = api.saveRepository(s.db, {url: 'git@github.com:Acme/Code.git', description: 'Workspace code'});
  code.saveResource(s.db, 'TAP', {kind: 'repository', name: 'Code', url: catalog.url, startingRef: 'develop'});
  const task = s.assignWork('Engineering partner', {title: 'SSH repository delivery', project: 'TAP', checks: ['Verified'], status: 'todo', queueRun: false}).task;
  const run = s.start(task, 'brainstorming');
  s.changeRun(run, 'deliver', 'Ready', {artifacts: [{title: 'Patch', body: 'Recorded changes'}], evidence: [{criterion: 'Verified', evidence: 'Reviewed diff', status: 'supported'}]});
  s.decide(run.id, run.stage, 'approve', 'Reviewed', {acknowledged: true});
  const pr = code.savePR(s.db, task.id, {run: run.id, url: 'https://github.com/acme/code/pull/1', source: 'feature', target: 'main', sha: 'abcdef1', state: 'merged', ci: 'passed', review: 'approved', conflicts: 'clear'});
  return {s, api, code, project, task, run, pr, catalog, delivery: s.currentDelivery(task.id)};
}

test('SSH project resources match HTTPS PR records and preserve captured code preferences', () => {
  const {s, api, code, project, task, run, catalog, delivery} = approvedCodeDelivery();
  assert.equal(code.blocker(s.db, task, delivery), '');
  assert.equal(run.inputSnapshot.context.resources[0].url, 'git@github.com:Acme/Code.git');
  assert.equal(run.inputSnapshot.context.codePreferences.coAuthor, false);
  api.savePreferences(s.db, {coAuthor: true, afterMerge: 'keep'});
  api.removeRepository(s.db, catalog.id);
  assert.equal(project.resources.length, 1);
  assert.equal(code.blocker(s.db, task, delivery), '');
  assert.equal(run.inputSnapshot.context.codePreferences.coAuthor, false);
  assert.equal(delivery.inputSnapshot.context.codePreferences.afterMerge, 'complete');
  s.transitionIssue(task, 'done', {manualReason: 'Accepted after merged PR'});
  assert.equal(task.status, 'done');
});

test('legacy captured repository URLs fail closed without crashing issue rendering', () => {
  const {s, code, task, delivery, pr} = approvedCodeDelivery();
  for (const url of ['https://git.example.com/repository', 'https://github.com/acme/code?ref=main', 'https://github.com/a/%62']) {
    delivery.inputSnapshot.context.resources[0].url = url;
    pr.repository = url;
    assert.match(code.blocker(s.db, task, delivery), /valid URL.*new delivery/);
  }
  delivery.inputSnapshot.context.resources[0].url = 'https://github.com/acme/code.git';
  pr.repository = 'https://github.com/acme/code?ref=main';
  assert.match(code.blocker(s.db, task, delivery), /each repository/);
  pr.repository = 'https://github.com/acme/code';
  assert.equal(code.blocker(s.db, task, delivery), '');
});
