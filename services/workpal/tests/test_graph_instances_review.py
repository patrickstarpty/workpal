"""Independent public Interface checks; fixture reuse is not test inheritance."""
from django.test import TestCase
from django.db import connection
from unittest.mock import patch
from tests import test_graph_instances as fixtures
from workpal.contracts import DomainError, SubjectRef
from workpal.workflows import instances
from workpal.agents import service as agents
from workpal.access import service as access
from workpal.access.models import SourceGrant
from workpal.contracts import ObjectRef

class GraphInstanceReview(TestCase):
    setUp = fixtures.GraphInstanceTests.setUp
    initialize = fixtures.GraphInstanceTests.initialize

    def rows(self):
        with connection.cursor() as cursor:
            result = {}
            for table in connection.introspection.table_names():
                cursor.execute('SELECT * FROM ' + connection.ops.quote_name(table))
                result[table] = sorted(map(repr, cursor.fetchall()))
            return result

    def denied(self, operation, status):
        before = self.rows()
        with self.assertRaises(DomainError) as caught:
            operation()
        self.assertEqual(caught.exception.status, status)
        self.assertEqual(self.rows(), before)

    def test_real_provider_matrix_and_current_agent(self):
        old = self.initialize()
        current = self.agent
        for provider in agents.PROVIDERS[1:]:
            current = agents.update(self.actor,current['id'],current['revision'],provider_key=provider)
            self.denied(lambda: self.initialize(),409)
            self.denied(lambda: self.initialize('new-provider'),409)
            self.assertEqual(instances.read(self.actor,old['id']),old)
        current = agents.update(self.actor,current['id'],current['revision'],provider_key='copilot_cli',name='Changed',model='current')
        self.assertEqual(self.initialize(),old)
        self.assertEqual(self.initialize('current')['snapshot']['agents'],[current])

    def test_saved_requirement_read_only_and_revocation(self):
        from workpal.work import issues
        source = ObjectRef('document','saved-requirements-review')
        access.register_object(self.actor.workspace_id,source,is_source=True)
        grant = SourceGrant.objects.create(user_id=self.actor.user_id,source=access.resolve(source),read=True,write=True,publish=True)
        access.register_object(self.actor.workspace_id,issues.requirement_ref(self.issue['requirements_version_id']),[source])
        old = self.initialize()
        grant.write=False; grant.save()
        self.assertEqual(self.initialize(),old)
        self.initialize('read-only')
        grant.read=False; grant.save()
        self.denied(lambda: self.initialize(),403)
        self.denied(lambda: instances.read(self.actor,old['id']),403)
        grant.read=True; grant.save()
        self.assertEqual(self.initialize(),old)

    def test_wrapper_registry_shared_key_and_read_copy(self):
        old = instances.initialize(self.actor,SubjectRef('issue',str(self.issue['id'])),self.version['id'],'initialize')
        self.assertEqual(self.initialize(),old)
        before = self.rows()
        detached=instances.read(self.actor,old['id'])
        detached['snapshot']['agents'].clear()
        self.assertEqual(instances.read(self.actor,old['id']),old)
        self.assertEqual(self.rows(),before)

    def test_record_failure_restores_every_table_and_retry_hash(self):
        import hashlib,json
        from workpal.actions import registry
        before=self.rows()
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_busy','Retry',status=503)
        with patch.object(registry,'record',side_effect=fail):
            self.denied(lambda:self.initialize(),503)
        self.assertEqual(self.rows(),before)
        old=self.initialize()
        after=self.rows()
        self.assertEqual(self.initialize(),old)
        self.assertEqual(self.rows(),after)
        self.assertEqual(old['sha256'],hashlib.sha256(json.dumps(old['snapshot'],sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest())
