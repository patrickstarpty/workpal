"""Independent current-permission and provenance regression checks."""
import copy
from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, ObjectRef, ActionRequest, DomainError
from workpal.identity.models import Workspace, Membership
from workpal.access import service as access
from workpal.access.models import SourceGrant, RegisteredObject, SourceLink
from workpal.agents import service as agents
from workpal.workflows import persistence as p
from workpal.workflows.graph_models import GraphDraft, GraphVersion
from workpal.actions.registry import execute
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox


class GraphPermissionsTests(TestCase):
    def setUp(self):
        self.ws = Workspace.objects.create(name='Permissions')
        self.actors = {}
        for role in ('owner', 'admin', 'member'):
            user = get_user_model().objects.create(username=role)
            Membership.objects.create(workspace=self.ws, user=user, role=role)
            self.actors[role] = Actor(user.pk, self.ws.pk)
        self.actor = self.actors['owner']
        other = Workspace.objects.create(name='Other')
        self.outside = Actor(self.actor.user_id, other.pk)
        agent = agents.create(self.actor, 'Agent')
        self.sources = [ObjectRef('document', name) for name in ('agent', 'input')]
        self.grants = []
        for source in self.sources:
            access.register_object(self.ws.pk, source, is_source=True)
            for actor in self.actors.values():
                grant = SourceGrant.objects.create(user_id=actor.user_id, source=access.resolve(source), read=True, write=True, publish=True)
                if actor == self.actor: self.grants.append(grant)
        access.register_object(self.ws.pk, agents.ref(agent['id']), [self.sources[0]])
        self.definition = dict(nodes=[dict(id='start', type='start', config={}), dict(id='task', type='agent_task', config=dict(agent_id=agent['id'], input_refs=['document:input'])), dict(id='end', type='end', config={})], edges=[dict(**{'from': a, 'to': b}, on='always', required=True, max_traversals=0) for a,b in [('start','task'),('task','end')]], declared_fields=[])

    def snapshot(self):
        return {m._meta.label: list(m.objects.order_by('pk').values()) for m in (GraphDraft, GraphVersion, RegisteredObject, SourceLink, AuditEvent, Outbox, IdempotencyResult)}

    def denied(self, operation, expected=(403, 'permission_denied')):
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught: operation()
        self.assertEqual((caught.exception.status, caught.exception.code), expected)
        self.assertEqual(self.snapshot(), before)

    def request(self, action, draft=None, key='key', definition=None):
        payload = dict(name='Graph', definition=definition or self.definition)
        if action != 'create': payload['draft_id'] = draft['id']
        if action == 'publish': payload = dict(draft_id=draft['id'])
        return ActionRequest('workflow_graph.'+action, payload, None if action=='create' else draft['revision'], key)

    def test_current_roles_and_independent_source_capabilities(self):
        for role, actor in self.actors.items():
            if role == 'member':
                self.denied(lambda: p.create(actor, 'Graph', self.definition))
                self.denied(lambda: execute(actor, self.request('create', key=role)))
            else:
                draft = p.create(actor, 'Graph', self.definition)
                execute(actor, self.request('create', key=role))
                self.assertEqual(p.read(self.actors['member'], draft['id']), draft)
        self.denied(lambda: p.create(self.outside, 'Graph', self.definition), (404, 'not_found'))
        self.denied(lambda: execute(self.outside, self.request('create')), (404, 'not_found'))
        for grant in self.grants:
            grant.write = grant.publish = False; grant.save()
            draft = execute(self.actor, self.request('create', key='read-'+str(grant.pk))).data
            self.assertEqual(p.read(self.actor, draft['id']), draft)
            for action in ('update','publish'):
                self.denied(lambda: execute(self.actor, self.request(action, draft, action+str(grant.pk))))
                self.denied(lambda: p.update(self.actor,draft['id'],draft['revision'],'Graph',self.definition) if action=='update' else p.publish(self.actor,draft['id'],draft['revision']))
            grant.write = grant.publish = True; grant.save()
            updated = p.update(self.actor,draft['id'],draft['revision'],'Graph',self.definition)
            p.publish(self.actor,updated['id'],updated['revision'])

    def test_cached_replay_rechecks_sources_membership_and_role(self):
        for action, capability in [('create','read'),('update','write'),('publish','publish')]:
            draft = p.create(self.actor,'Graph',self.definition)
            request = self.request(action,draft,action)
            original = execute(self.actor,request).data
            for grant in self.grants:
                setattr(grant,capability,False); grant.save()
                self.denied(lambda: execute(self.actor,request))
                self.denied(lambda: execute(self.actor,self.request(action,draft,action+'new'+str(grant.pk))))
                if action=='publish': self.assertEqual(p.read_version(self.actor,original['id']),original)
                setattr(grant,capability,True); grant.save()
                before=self.snapshot(); self.assertEqual(execute(self.actor,request).data,original); self.assertEqual(self.snapshot(),before)
            membership=Membership.objects.get(user_id=self.actor.user_id,workspace=self.ws)
            for removed in (False,True):
                membership.role='member'; membership.save()
                if removed: membership.delete()
                self.denied(lambda: execute(self.actor,request), (404, 'not_found') if removed else (403, 'permission_denied'))
                self.denied(lambda: execute(self.actor,self.request(action,draft,action+'role'+str(removed))), (404, 'not_found') if removed else (403, 'permission_denied'))
                if removed: membership=Membership.objects.create(user_id=self.actor.user_id,workspace=self.ws,role='owner')
                else: membership.role='owner'; membership.save()
                before=self.snapshot(); self.assertEqual(execute(self.actor,request).data,original); self.assertEqual(self.snapshot(),before)

    def test_history_inherits_later_sources_without_rewriting_snapshots(self):
        request=self.request('create',key='history')
        draft=execute(self.actor,request).data
        v1=p.publish(self.actor,draft['id'],1)
        source=ObjectRef('document','later'); access.register_object(self.ws.pk,source,is_source=True)
        grant=SourceGrant.objects.create(user_id=self.actor.user_id,source=access.resolve(source),read=True,write=True,publish=True)
        definition=copy.deepcopy(self.definition); definition['nodes'][1]['config']['input_refs']=['document:later']
        changed=p.update(self.actor,draft['id'],2,'Later',definition); v2=p.publish(self.actor,draft['id'],changed['revision'])
        self.assertEqual(v1['resolved_inputs'][0]['input_refs'],[dict(kind='document',id='input')])
        self.assertEqual(v2['resolved_inputs'][0]['input_refs'],[dict(kind='document',id='later')])
        self.assertEqual(access.derive_scope([p.ref(draft['id'])]).source_refs,set(self.sources+[source]))
        grant.read=False; grant.save()
        for operation in (lambda:p.read(self.actor,draft['id']),lambda:p.read_version(self.actor,v1['id']),lambda:p.read_version(self.actor,v2['id']),lambda:execute(self.actor,request)): self.denied(operation)
        grant.read=True; grant.save()
        self.assertEqual(p.read_version(self.actor,v1['id']),v1); self.assertEqual(p.read_version(self.actor,v2['id']),v2)

    def test_self_and_downstream_cycles_roll_back_and_key_can_retry(self):
        for downstream in (False,True):
            draft=p.create(self.actor,'Graph',self.definition)
            target=p.ref(draft['id'])
            if downstream:
                target=ObjectRef('document','downstream'); access.register_object(self.ws.pk,target,[p.ref(draft['id'])])
            definition=copy.deepcopy(self.definition); definition['nodes'][1]['config']['input_refs']=[target.kind+':'+target.id]
            request=self.request('update',draft,'cycle'+str(downstream),definition)
            self.denied(lambda:execute(self.actor,request))
            legal=self.request('update',draft,request.key if hasattr(request,'key') else 'cycle'+str(downstream))
            result=execute(self.actor,legal).data
            before=self.snapshot(); self.assertEqual(execute(self.actor,legal).data,result); self.assertEqual(self.snapshot(),before)
