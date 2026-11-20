"""Public listing Interface checks with shared fixtures, no inherited tests."""
from django import test
from tests import test_graph_instances as fixtures
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest

class GraphInstanceListing(test.TestCase):
    setUp = fixtures.GraphInstanceTests.setUp
    initialize = fixtures.GraphInstanceTests.initialize

    def listing(self, **payload):
        return execute(self.actor, ActionRequest('workflow_graph.instance.list', payload, None, None)).data

    def test_registry_defaults(self):
        data = self.initialize()
        result = self.listing()
        self.assertEqual([item['id'] for item in result['items']], [data['id']])
        self.assertEqual(set(result['items'][0]), {'id','version_id','subject','state','sha256','created_at'})
        self.assertEqual(result['next_cursor'], 0)

    def rows(self):
        from django.db import connection
        with connection.cursor() as cursor:
            result={}
            for table in connection.introspection.table_names():
                cursor.execute('SELECT * FROM '+connection.ops.quote_name(table))
                result[table]=sorted(map(repr,cursor.fetchall()))
            return result

    def source(self, item, name):
        from workpal.access import service as access
        from workpal.access.models import SourceGrant
        from workpal.contracts import ObjectRef
        from workpal.workflows import instances
        source=ObjectRef('document',name)
        access.register_object(self.actor.workspace_id,source,is_source=True)
        grant=SourceGrant.objects.create(user_id=self.actor.user_id,source=access.resolve(source),read=True,write=True,publish=True)
        access.register_object(self.actor.workspace_id,instances.ref(item['id']),[source])
        return grant

    def test_strict_bounds_and_empty(self):
        from workpal.contracts import DomainError
        from workpal.storage import MAX_SQLITE_INTEGER
        from workpal.workflows import instances
        for payload in ({'cursor':True},{'cursor':'0'},{'cursor':-1},{'cursor':MAX_SQLITE_INTEGER},{'limit':False},{'limit':'1'},{'limit':0},{'limit':201},{'extra':1}):
            with self.subTest(payload=payload),self.assertRaises(DomainError): self.listing(**payload)
        for cursor,limit in ((True,1),('0',1),(-1,1),(MAX_SQLITE_INTEGER,1),(0,False),(0,201)):
            with self.assertRaises(DomainError): instances.list_instances(self.actor,cursor,limit)
        self.assertEqual(self.listing(cursor=MAX_SQLITE_INTEGER-1,limit=200),dict(items=[],next_cursor=0))

    def test_authorized_pages_and_exact_scope(self):
        from dataclasses import asdict
        from workpal.access import service as access
        from workpal.audit.models import AuditEvent
        from workpal.workflows import instances
        data=[self.initialize(str(i)) for i in range(7)]
        for i in (0,3,6):
            grant=self.source(data[i],str(i)); grant.read=False; grant.save()
        cursor=0; seen=[]
        for expected in ([data[1],data[2]],[data[4],data[5]]):
            before=self.rows()
            direct=instances.list_instances(self.actor,cursor,2)
            self.assertEqual(self.rows(),before)
            ids=set(AuditEvent.objects.values_list('pk',flat=True))
            old_audits=list(AuditEvent.objects.order_by('pk').values())
            page=self.listing(cursor=cursor,limit=2)
            self.assertEqual(page,direct)
            refs=[instances.ref(item['id']) for item in expected]
            event=AuditEvent.objects.exclude(pk__in=ids).get()
            self.assertEqual(list(AuditEvent.objects.filter(pk__in=ids).order_by('pk').values()),old_audits)
            self.assertEqual(event.object_refs,[asdict(ref) for ref in refs])
            scope=set(refs)|set(access.derive_scope(refs).source_refs)
            self.assertEqual(event.scope_refs,[asdict(ref) for ref in sorted(scope,key=lambda r:(r.kind,r.id))])
            after=self.rows(); before.pop('audit_auditevent'); after.pop('audit_auditevent')
            self.assertEqual(before,after)
            seen.extend(item['id'] for item in page['items'])
            self.assertTrue(all('snapshot' not in item for item in page['items']))
            cursor=page['next_cursor']
        self.assertEqual(seen,[data[i]['id'] for i in (1,2,4,5)])
        self.assertEqual(cursor,0)
        page['items'][0]['subject']['id']='changed'
        self.assertEqual(instances.read(self.actor,data[4]['id']),data[4])

    def test_current_permissions_and_provider(self):
        from workpal.agents import service as agents
        from workpal.identity.models import Workspace,Membership
        from workpal.contracts import Actor,DomainError
        from workpal.contracts import ObjectRef
        from workpal.access import service as access
        from workpal.work import issues
        from workpal.workflows import instances
        data=self.initialize()
        grant=self.source(data,'permission')
        access.register_object(self.actor.workspace_id,issues.ref(self.issue['id']),[ObjectRef('document','permission')])
        grant.write=False; grant.save()
        agents.update(self.actor,self.agent['id'],self.agent['revision'],provider_key=agents.PROVIDERS[1])
        self.assertEqual(self.listing()['items'][0]['id'],data['id'])
        grant.read=False; grant.save()
        self.assertEqual(self.listing()['items'],[])
        other=Workspace.objects.create(name='Other')
        Membership.objects.create(user_id=self.actor.user_id,workspace=other,role='member')
        self.assertEqual(instances.list_instances(Actor(self.actor.user_id,other.pk))['items'],[])
        member=Membership.objects.get(user_id=self.actor.user_id,workspace_id=self.actor.workspace_id)
        member.user.is_active=False; member.user.save()
        with self.assertRaises(DomainError): instances.list_instances(self.actor)
        with self.assertRaises(DomainError): self.listing()

    def test_authorization_and_audit_failures_rollback(self):
        from unittest.mock import patch
        from workpal.actions import registry
        from workpal.contracts import DomainError
        from workpal.workflows import instances
        self.initialize()
        before=self.rows()
        with patch.object(instances.access,'authorize',side_effect=DomainError('storage_busy','Retry',status=503)):
            for operation in (lambda:instances.list_instances(self.actor),self.listing):
                with self.assertRaises(DomainError) as caught: operation()
                self.assertEqual(caught.exception.status,503)
                self.assertEqual(self.rows(),before)
        original=registry.record
        def fail(*args,**kwargs):
            original(*args,**kwargs)
            raise DomainError('storage_busy','Retry',status=503)
        with patch.object(registry,'record',side_effect=fail):
            with self.assertRaises(DomainError) as caught: self.listing()
            self.assertEqual(caught.exception.status,503)
        self.assertEqual(self.rows(),before)
