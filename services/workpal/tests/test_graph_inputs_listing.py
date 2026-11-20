"""R2 checks across the public persistence and Registry interfaces."""
import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, ObjectRef, ActionRequest, DomainError
from workpal.identity.models import Workspace, Membership
from workpal.access import service as access
from workpal.access.models import RegisteredObject, SourceGrant, SourceLink
from workpal.agents import service as agents
from workpal.workflows import persistence as p
from workpal.workflows.graph import compile_graph
from workpal.workflows.graph_models import GraphDraft, GraphVersion
from workpal.actions.registry import execute
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox


class GraphInputsListingTests(TestCase):
    def setUp(self):
        self.ws=Workspace.objects.create(name='R2')
        self.actors=[]
        for role in ('owner','member'):
            user=get_user_model().objects.create(username=role)
            Membership.objects.create(workspace=self.ws,user=user,role=role)
            self.actors.append(Actor(user.pk,self.ws.pk))
        self.owner,self.member=self.actors
        self.agent=agents.create(self.owner,'Agent')
        self.serial=0

    def definition(self, refs=()):
        return dict(nodes=[dict(id='start',type='start',config={}),dict(id='task',type='agent_task',config=dict(agent_id=self.agent['id'],input_refs=list(refs))),dict(id='end',type='end',config={})],edges=[dict(**{'from':a,'to':b},on='always',required=True,max_traversals=0) for a,b in [('start','task'),('task','end')]],declared_fields=['x'])

    def source(self, name, member=False, workspace=None):
        ref=ObjectRef('document',name)
        access.register_object((workspace or self.ws).pk,ref,is_source=True)
        for actor in ([self.owner,self.member] if member else [self.owner]):
            SourceGrant.objects.create(source=access.resolve(ref),user_id=actor.user_id,read=True,write=True,publish=True)
        return ref

    def call(self, action, payload, actor=None, revision=None):
        self.serial+=1
        return execute(actor or self.owner,ActionRequest('workflow_graph.'+action,payload,revision,str(self.serial) if action in ('create','publish') else None)).data

    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in (GraphDraft,GraphVersion,RegisteredObject,SourceGrant,SourceLink,AuditEvent,Outbox,IdempotencyResult)}

    def reject(self, operation, status):
        before=self.snapshot()
        with self.assertRaises(DomainError) as caught: operation()
        self.assertEqual(caught.exception.status,status)
        self.assertEqual(self.snapshot(),before)

    def test_input_reference_public_matrix(self):
        refs=['document:'+str(i) for i in range(49)]+['document:合法é']
        for ref in refs:self.source(ref.split(':')[1])
        for registry in (False,True):
            def create(d):
                return self.call('create',dict(name='Inputs',definition=d)) if registry else p.create(self.owner,'Inputs',d)
            draft=create(self.definition(refs))
            version=p.publish(self.owner,draft['id'],1)
            self.assertEqual(version['resolved_inputs'],[dict(node_id='task',agent_id=self.agent['id'],input_refs=[dict(kind='document',id=r.split(':')[1]) for r in refs])])
            for bad in (refs+['document:extra'],[refs[0],refs[0]],['document:'],['document:a:b'],['Bad:a'],['document:'+'a'*248],['document:\ud800']):
                with self.subTest(registry=registry,bad=repr(bad)):
                    self.reject(lambda:create(self.definition(bad)),400)
            unavailable=self.source('unavailable'+str(registry)); RegisteredObject.objects.filter(pk=access.resolve(unavailable).pk).update(available=False)
            other=Workspace.objects.create(name='Other'+str(registry))
            Membership.objects.create(workspace=other,user_id=self.owner.user_id,role='owner')
            cross=self.source('cross'+str(registry),workspace=other)
            for ref in ('document:unknown','document:'+unavailable.id,'document:'+cross.id):
                self.reject(lambda:create(self.definition([ref])),403)

    def test_condition_literals_registry_roundtrip_and_closed_fields(self):
        d=self.definition(); d['nodes'][1]=dict(id='task',type='condition',config=dict(condition=dict(field='x',op='eq',value=None)))
        d['edges']=[d['edges'][0]]+[dict(**{'from':'task','to':'end'},on=label,required=True,max_traversals=0) for label in ('true','false')]
        for value in (None,True,False,17,1.25,'文字',[],{},[None,{'a':[True,2.5]}],{'nested':{'a':'é'}}):
            definition=copy.deepcopy(d);definition['nodes'][1]['config']['condition']['value']=value
            draft=self.call('create',dict(name='Literal',definition=definition))
            version=self.call('publish',dict(draft_id=draft['id']),revision=1)
            read=self.call('version.read',dict(version_id=version['id']))
            self.assertEqual(read['graph'],compile_graph(definition))
            self.assertEqual(read,version)
        for value in (float('nan'),float('inf'),-float('inf'),object(),'\ud800'):
            definition=copy.deepcopy(d);definition['nodes'][1]['config']['condition']['value']=value
            self.reject(lambda:self.call('create',dict(name='Invalid',definition=definition)),400)
        for location in ('graph','node','config','edge'):
            definition=copy.deepcopy(d)
            target={'graph':definition,'node':definition['nodes'][1],'config':definition['nodes'][1]['config'],'edge':definition['edges'][0]}[location]
            target['extra']='secret'
            self.reject(lambda:self.call('create',dict(name='Invalid',definition=definition)),400)

    def test_real_grant_filtered_pagination_and_read_audits(self):
        visible=[]; sources=[]
        for i in range(7):
            source=self.source('page'+str(i),member=i in (1,3,4,5));sources.append(source)
            draft=p.create(self.owner,'HiddenSensitive'+str(i),self.definition(['document:'+source.id]))
            if i in (1,3,4,5):visible.append(draft['id'])
        def page(**kwargs):
            previous=set(AuditEvent.objects.values_list('pk',flat=True))
            result=self.call('list',kwargs,self.member)
            events=AuditEvent.objects.exclude(pk__in=previous)
            self.assertEqual(events.count(),1)
            self.assertCountEqual(events.get().object_refs,[dict(kind='workflow_graph',id=str(item['id'])) for item in result['items']])
            return result
        before=self.snapshot(); audit_before=set(AuditEvent.objects.values_list('pk',flat=True))
        self.assertEqual([x['id'] for x in page()['items']],visible)
        for limit in (1,2,200):
            cursor=0; found=[]
            while True:
                result=page(cursor=cursor,limit=limit);found += [x['id'] for x in result['items']]
                if result['next_cursor']==0:break
                self.assertGreater(result['next_cursor'],cursor);cursor=result['next_cursor']
            self.assertEqual(found,visible)
        self.assertEqual(page(cursor=visible[-1],limit=1),dict(items=[],next_cursor=0))
        read=self.call('read',dict(draft_id=visible[0]),self.member)
        self.assertEqual(read['id'],visible[0])
        after=self.snapshot()
        for label in before:
            if label!='audit.AuditEvent':self.assertEqual(after[label],before[label])
        events=AuditEvent.objects.exclude(pk__in=audit_before)
        self.assertTrue(events.exists())
        for event in events:
            self.assertEqual(event.actor_id,self.member.user_id)
            self.assertEqual(event.workspace_id,self.ws.pk)
            self.assertNotIn('HiddenSensitive',str(event.fields))
            self.assertTrue(all(ref['kind']=='workflow_graph' and int(ref['id']) in visible for ref in event.object_refs))
            expected=access.derive_scope([p.ref(int(ref['id'])) for ref in event.object_refs]) if event.object_refs else None
            self.assertEqual({(r['kind'],r['id']) for r in event.scope_refs},({(r.kind,r.id) for r in expected.source_refs} if expected else set()) | {(r['kind'],r['id']) for r in event.object_refs})
        SourceGrant.objects.filter(user_id=self.member.user_id,source=access.resolve(sources[1])).update(read=False)
        self.assertEqual([x['id'] for x in page()['items']],visible[1:])
        for payload in (dict(cursor=True),dict(cursor='1'),dict(cursor=-1),dict(limit=0),dict(limit=201),dict(limit=True)):
            self.reject(lambda:page(**payload),400)
        self.reject(lambda:self.call('create',dict(name='No',definition=self.definition()),self.member),403)
