"""Bounded file-SQLite races and historical graph-instance upgrade checks."""
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.test import TransactionTestCase, SimpleTestCase
from django.db import connections
from workpal.contracts import DomainError
from workpal.audit.models import AuditEvent, Outbox
from workpal.actions.models import IdempotencyResult
from workpal.access.models import RegisteredObject, SourceLink
from workpal.workflows.graph_models import GraphInstance
from workpal.workflows import instances
from tests import test_graph_instances as fixture


class InstanceRaces(TransactionTestCase):
    setUp = fixture.GraphInstanceTests.setUp
    initialize = fixture.GraphInstanceTests.initialize

    def old_rows(self):
        c = connections['default']
        with c.cursor() as cursor:
            return {t: cursor.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall()
                    for t in c.introspection.table_names()
                    if t.startswith(('work_', 'execution_', 'workflows_workflow'))}

    def counts(self):
        return [m.objects.count() for m in
                (GraphInstance, RegisteredObject, AuditEvent, Outbox, IdempotencyResult)]

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
                for attempt in range(8):
                    try:
                        return raw, self.initialize(key)
                    except DomainError as error:
                        if error.code != 'storage_busy' or attempt == 7:
                            raise
            finally:
                c.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker, key) for key in keys]
            results = [f.result(timeout=60) for f in futures]
        self.assertIsNot(results[0][0], results[1][0])
        return [r[1] for r in results]

    def verify(self, results, number, before, old):
        self.assertEqual(self.counts(), [n+number for n in before])
        self.assertEqual(self.old_rows(), old)
        for data in results:
            row = GraphInstance.objects.get(pk=data['id'])
            self.assertEqual(row.state, 'initialized')
            self.assertEqual(row.snapshot, data['snapshot'])
            digest = hashlib.sha256(json.dumps(row.snapshot, sort_keys=True,
                separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
            self.assertEqual(row.sha256, digest)
            self.assertEqual(data['sha256'], digest)
            registered = RegisteredObject.objects.get(kind='workflow_graph_instance', object_id=str(row.pk))
            links = list(SourceLink.objects.filter(derived=registered).values_list('source__kind','source__object_id'))
            expected = {(ref['kind'], ref['id']) for ref in row.snapshot['source_refs']}
            self.assertEqual(set(links), expected)
            self.assertEqual(len(links), len(expected))

    def test_same_key_two_connections(self):
        before, old = self.counts(), self.old_rows()
        results = self.race(['same', 'same'])
        self.assertEqual(results[0], results[1])
        self.verify(results, 1, before, old)

    def test_independent_keys_two_initialized_facts(self):
        before, old = self.counts(), self.old_rows()
        results = self.race(['left', 'right'])
        self.assertNotEqual(results[0]['id'], results[1]['id'])
        self.verify(results, 2, before, old)
        links = list(SourceLink.objects.order_by('pk').values())
        for key, data in zip(['left', 'right'], results):
            self.assertEqual(self.initialize(key), data)
            detached = instances.read(self.actor, data['id'])
            detached['snapshot']['agents'].clear()
            self.assertEqual(instances.read(self.actor, data['id']), data)
        self.verify(results, 2, before, old)
        self.assertEqual(list(SourceLink.objects.order_by('pk').values()), links)


class HistoricalInstanceUpgrade(SimpleTestCase):
    def test_real_0002_database_upgrade(self):
        script = r'''
import django
django.setup()
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.db.migrations.recorder import MigrationRecorder
try:
    executor = MigrationExecutor(connection)
    leaves = executor.loader.graph.leaf_nodes()
    old = [t for t in leaves if t[0] != 'workflows'] + [('workflows','0002_graph_persistence')]
    executor.migrate(old)
    assert not MigrationRecorder(connection).migration_qs.filter(app='workflows',name='0003_graph_instance').exists()
    assert 'workflows_graphinstance' not in connection.introspection.table_names()
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
    GD=apps.get_model('workflows','GraphDraft'); GV=apps.get_model('workflows','GraphVersion')
    graph={'nodes':[{'id':'s','type':'start','config':{}},{'id':'e','type':'end','config':{}}],'edges':[],'declared_fields':[]}
    gd=GD.objects.create(workspace=w,name='Historical graph',definition=graph)
    gv=GV.objects.create(workspace=w,draft=gd,number=1,name='Historical graph',graph={'definition':graph,'sha256':'b'*64},resolved_inputs=[],published_by=u)
    gd.current_version=gv; gd.save()
    tables=[t for t in connection.introspection.table_names() if t.startswith(('work_', 'workflows_', 'execution_'))]
    def rows():
        with connection.cursor() as c:
            return {t:c.execute('SELECT * FROM "'+t+'" ORDER BY 1').fetchall() for t in tables}
    before=rows()
    MigrationExecutor(connection).migrate(leaves)
    assert rows()==before, (before,rows())
    from workpal.workflows.graph_models import GraphInstance
    assert GraphInstance.objects.count()==0
    assert all(not data for table,data in rows().items() if table.startswith('execution_'))
    MigrationExecutor(connection).migrate(leaves)
    assert rows()==before
    assert GraphInstance.objects.count()==0
    assert all(not data for table,data in rows().items() if table.startswith('execution_'))
    print('0001 absent graph -> historical FK data -> current leaves -> exact SQL unchanged -> repeat unchanged')
finally:
    connection.close()
'''
        with tempfile.TemporaryDirectory(prefix='workpal-instance-upgrade-') as directory:
            result = subprocess.run([sys.executable, '-c', script],
                cwd=Path(__file__).resolve().parents[1],
                env={**os.environ, 'WORKPAL_DB_PATH': str(Path(directory)/'old.sqlite3'),
                     'DJANGO_SETTINGS_MODULE': 'config.settings'},
                capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
