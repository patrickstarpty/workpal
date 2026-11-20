"""Final Registry races and isolated historical-schema upgrade evidence."""
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase, SimpleTestCase
from django.db import connections
from django.contrib.auth import get_user_model
from workpal.identity.models import Workspace, Membership
from workpal.contracts import Actor, ActionRequest, DomainError
from workpal.actions import registry
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from workpal.access.models import SourceLink
from workpal.workflows import persistence
from workpal.workflows.graph_models import GraphDraft, GraphVersion


class FinalPublishRaces(TransactionTestCase):
    def setUp(self):
        u = get_user_model().objects.create(username='final-race')
        w = Workspace.objects.create(name='Final')
        Membership.objects.create(user=u, workspace=w, role='owner')
        self.actor = Actor(u.pk, w.pk)
        self.draft = persistence.create(self.actor, 'Final', dict(nodes=[
            dict(id='s', type='start', config={}), dict(id='e', type='end', config={})],
            edges=[dict(**{'from': 's', 'to': 'e'}, on='always', required=True,
                        max_traversals=0)], declared_fields=[]))

    def counts(self):
        return [m.objects.count() for m in (AuditEvent, Outbox, IdempotencyResult)]

    def old_rows(self):
        c = connections['default']
        with c.cursor() as cursor:
            return {t: cursor.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall()
                    for t in c.introspection.table_names()
                    if t.startswith(('work_', 'execution_', 'workflows_workflow'))}

    def call(self, key, revision):
        for attempt in range(8):
            try:
                return registry.execute(self.actor, ActionRequest('workflow_graph.publish',
                    dict(draft_id=self.draft['id']), revision, key))
            except DomainError as error:
                if error.code != 'storage_busy' or attempt == 7:
                    raise

    def race(self, keys):
        barrier = Barrier(2)
        def worker(key):
            c = connections['default']
            try:
                c.ensure_connection()
                raw = c.connection
                self.assertNotIn('memory', str(c.settings_dict['NAME']))
                self.assertTrue(Path(c.settings_dict['NAME']).is_file())
                barrier.wait(timeout=15)
                try:
                    result = self.call(key, self.draft['revision'])
                except DomainError as error:
                    result = error
                return raw, result
            finally:
                c.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, key) for key in keys]
            results = [f.result(timeout=60) for f in futures]
        self.assertIsNot(results[0][0], results[1][0])
        return [r[1] for r in results]

    def assert_fact(self, number):
        draft = GraphDraft.objects.get(pk=self.draft['id'])
        self.assertEqual(draft.revision, self.draft['revision'] + number)
        self.assertEqual(GraphVersion.objects.count(), number)
        self.assertEqual(draft.current_version.number, number)
        pairs = list(SourceLink.objects.values_list('derived_id', 'source_id'))
        self.assertEqual(len(pairs), len(set(pairs)))
        return draft.current_version_id

    def test_same_key_two_connections(self):
        before, old = self.counts(), self.old_rows()
        results = self.race(['same', 'same'])
        for result in results:
            self.assertNotIsInstance(result, DomainError)
            self.assertEqual(result.state, 'completed')
        self.assertEqual(results[0].data, results[1].data)
        self.assertEqual(self.assert_fact(1), results[0].data['id'])
        self.assertEqual(self.counts(), [x+1 for x in before])
        self.assertEqual(self.old_rows(), old)

    def test_independent_keys_conflict_retry_and_replay(self):
        before, old = self.counts(), self.old_rows()
        results = self.race(['left', 'right'])
        losers = [i for i, r in enumerate(results) if isinstance(r, DomainError)]
        self.assertEqual(len(losers), 1)
        loser = losers[0]; winner = 1-loser
        self.assertEqual((results[loser].code, results[loser].status), ('revision_conflict', 409))
        self.assertEqual(results[winner].state, 'completed')
        self.assertEqual(self.assert_fact(1), results[winner].data['id'])
        self.assertEqual(self.counts(), [x+1 for x in before])
        keys = ['left', 'right']
        self.assertFalse(IdempotencyResult.objects.filter(key=keys[loser]).exists())
        second = self.call(keys[loser], self.draft['revision']+1)
        self.assertEqual(second.state, 'completed')
        self.assertEqual(self.assert_fact(2), second.data['id'])
        self.assertEqual(self.counts(), [x+2 for x in before])
        links = list(SourceLink.objects.order_by('pk').values())
        replay = self.call(keys[winner], self.draft['revision'])
        self.assertEqual(replay.data, results[winner].data)
        self.assertEqual(self.assert_fact(2), second.data['id'])
        self.assertEqual(self.counts(), [x+2 for x in before])
        self.assertEqual(list(SourceLink.objects.order_by('pk').values()), links)
        self.assertEqual(self.old_rows(), old)


class FinalHistoricalUpgrade(SimpleTestCase):
    def test_real_0001_database_upgrade(self):
        script = r'''
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
try:
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    old = [t for t in leaves if t[0] != 'workflows'] + [('workflows','0001_initial')]
    executor.migrate(old)
    assert not MigrationRecorder(connection).migration_qs.filter(app='workflows',name='0002_graph_persistence').exists()
    assert not any('graph' in t for t in connection.introspection.table_names())
    apps = executor.loader.project_state(old).apps
    U=apps.get_model('auth','User'); W=apps.get_model('identity','Workspace')
    D=apps.get_model('workflows','WorkflowDraft'); V=apps.get_model('workflows','WorkflowVersion')
    P=apps.get_model('work','Project'); I=apps.get_model('work','Issue'); R=apps.get_model('work','IssueRequirements')
    u=U.objects.create(username='historical'); w=W.objects.create(name='historical')
    definition={'states':[{'key':'todo','name':'To do'}], 'transitions':[], 'review_policy':{}}
    d=D.objects.create(workspace=w,name='Legacy',definition=definition)
    v=V.objects.create(workspace=w,draft=d,number=1,name='Legacy',definition=definition,sha256='a'*64,published_by=u)
    d.current_version=v; d.save()
    p=P.objects.create(workspace=w,name='Bound',workflow_version=v)
    i=I.objects.create(workspace=w,project=p,created_by=u,status_key='todo',workflow_snapshot={'definition':definition,'sha256':'a'*64})
    for n in (1,2):
        r=R.objects.create(issue=i,number=n,title='History '+str(n),description='Unicode 历史',criteria=[{'key':'a','text':str(n)}],sha256=str(n)*64,created_by=u)
    i.current_requirements=r; i.save()
    tables=[t for t in connection.introspection.table_names() if t.startswith(('work_', 'workflows_'))]
    def rows():
        with connection.cursor() as c:
            return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall() for t in tables}
    before=rows()
    MigrationExecutor(connection).migrate(leaves)
    assert rows()==before, (before,rows())
    from workpal.workflows.graph_models import GraphDraft, GraphVersion
    assert GraphDraft.objects.count()==GraphVersion.objects.count()==0
    MigrationExecutor(connection).migrate(leaves)
    assert rows()==before
    assert GraphDraft.objects.count()==GraphVersion.objects.count()==0
    print('0001 absent graph -> historical FK data -> current leaves -> exact SQL unchanged -> repeat unchanged')
finally:
    connection.close()
'''
        with tempfile.TemporaryDirectory(prefix='workpal-final-upgrade-') as directory:
            result = subprocess.run([sys.executable, '-c', script],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, 'WORKPAL_DB_PATH': str(Path(directory)/'old.sqlite3'),
                     'DJANGO_SETTINGS_MODULE': 'config.settings'},
                capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
