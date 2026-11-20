from copy import deepcopy
from django.apps import apps
from django.contrib.auth import get_user_model

from workpal.contracts import Actor, DomainError, ObjectRef
from workpal.identity.models import Workspace, Membership
from workpal.work import issues, dependencies, hierarchy, transitions
from workpal.work.models import Issue
from workpal.access.service import register_object, derive_scope
from workpal.access.models import SourceGrant, RegisteredObject
from workpal.actions.models import IdempotencyResult
from workpal.audit.models import AuditEvent, Outbox
from .support import WorkpalCase


class RequirementsSecurityReview(WorkpalCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user('review-owner')
        self.reader = get_user_model().objects.create_user('review-member')
        self.workspace = Workspace.objects.create(name='Content')
        self.other = Workspace.objects.create(name='Other')
        for ws in (self.workspace, self.other):
            Membership.objects.create(user=self.user, workspace=ws, role='owner')
        Membership.objects.create(user=self.reader, workspace=self.workspace, role='member')
        self.actor = Actor(self.user.pk, self.workspace.pk)
        self.project = self.act(self.actor, 'project.create', {'name':'Project'}, key='p').data
        self.payload = {'project_id':self.project['id'], 'title':'Protected title',
                        'description':'Protected body', 'criteria':[{'key':'a', 'text':'Protected acceptance'}]}
        self.item = self.act(self.actor, 'issue.create', self.payload, key='i').data
        self.source = register_object(self.workspace.pk, ObjectRef('source','review-content'), is_source=True)
        self.source_row = RegisteredObject.objects.get(kind=self.source.kind, object_id=self.source.id)

    def snapshot(self):
        return {m._meta.label:list(m.objects.order_by('pk').values()) for m in apps.get_models()}

    def restrict(self, item=None):
        register_object(self.workspace.pk, issues.requirement_ref((item or self.item)['requirements_version_id']), [self.source])

    def grant(self, user=None, read=True, write=True):
        return SourceGrant.objects.create(user=user or self.user, source=self.source_row, read=read, write=write)

    def deny_unchanged(self, fn):
        before = self.snapshot()
        with self.assertRaises(DomainError) as caught:
            fn()
        self.assertEqual(caught.exception.status, 403)
        self.assertEqual(self.snapshot(), before)

    def legacy(self):
        saved = IdempotencyResult.objects.get(action_id='issue.create', key='i')
        saved.result['object_refs'] = [r for r in saved.result['object_refs'] if r['kind'] != 'issue_requirements']
        saved.scope_refs = [r for r in saved.scope_refs if r['kind'] != 'issue_requirements']
        saved.save()
        return saved

    def test_malformed_legacy_content_cannot_skip_its_requirement_scope(self):
        self.restrict()
        saved = self.legacy()
        del saved.result['data']['title']
        saved.save()
        self.deny_unchanged(lambda:self.act(self.actor, 'issue.create', self.payload, key='i'))

    def test_cached_requirement_must_match_its_issue_workspace_and_version(self):
        same = issues.create(self.actor, self.project['id'], 'Other issue')
        other_actor = Actor(self.user.pk, self.other.pk)
        project = self.act(other_actor, 'project.create', {'name':'Other'}, key='other').data
        foreign = issues.create(other_actor, project['id'], 'Other workspace')
        newer = self.act(self.actor, 'issue.update', {'issue_id':self.item['id'], 'title':'New content'}, revision=1, key='new').data
        saved = self.legacy(); original = deepcopy(saved.result)
        self.restrict()
        variants = [
            {'requirements_version_id':same['requirements_version_id']},
            {'requirements_version_id':foreign['requirements_version_id']},
            {'requirements_version_id':newer['requirements_version_id']},
            {'requirements_version_id':True},
            {'id':same['id'], 'requirements_version_id':same['requirements_version_id']},
        ]
        for changes in variants:
            with self.subTest(changes=changes):
                saved.result = deepcopy(original); saved.result['data'].update(changes); saved.save()
                self.deny_unchanged(lambda:self.act(self.actor, 'issue.create', self.payload, key='i'))

    def test_legacy_replay_uses_public_saved_version_even_when_current_is_private(self):
        newer = self.act(self.actor, 'issue.update', {'issue_id':self.item['id'], 'title':'New'}, revision=1, key='new').data
        saved = self.legacy(); self.restrict(newer)
        before = self.snapshot()
        result = self.act(self.actor, 'issue.create', self.payload, key='i')
        self.assertEqual(result.data, self.item)
        self.assertIn(issues.requirement_ref(self.item['requirements_version_id']), result.object_refs)
        self.assertEqual(self.snapshot(), before)
        self.deny_unchanged(lambda:issues.read(self.actor, newer['id']))

    def test_children_filter_content_before_pagination_and_preserve_displayed_scope(self):
        parent = issues.create(self.actor, self.project['id'], 'Parent')
        hidden = issues.create(self.actor, self.project['id'], 'Hidden child', parent_issue_id=parent['id'])
        visible = issues.create(self.actor, self.project['id'], 'Visible child', parent_issue_id=parent['id'])
        self.restrict(hidden); before_outbox = list(Outbox.objects.values())
        result = self.act(self.actor, 'issue.children.list', {'issue_id':parent['id'], 'limit':1})
        self.assertEqual([i['id'] for i in result.data['items']], [visible['id']])
        self.assertEqual(result.data['next_cursor'], 0)
        expected = issues.requirement_ref(visible['requirements_version_id'])
        self.assertIn(expected, result.object_refs)
        self.assertNotIn(issues.requirement_ref(hidden['requirements_version_id']), result.object_refs)
        event = AuditEvent.objects.filter(action_id='issue.children.list').latest('created_at')
        self.assertIn({'kind':expected.kind, 'id':expected.id}, event.scope_refs)
        self.assertEqual(list(Outbox.objects.values()), before_outbox)

    def test_output_denial_rolls_back_each_direct_and_registry_write(self):
        target = issues.create(self.actor, self.project['id'], 'Relation target')
        for action in ('archive', 'transition', 'dependency.add', 'dependency.remove', 'set_parent'):
            item = issues.create(self.actor, self.project['id'], action)
            if action == 'dependency.remove':
                item = dependencies.add(self.actor, item['id'], target['id'], item['revision'])
            self.restrict(item)
            payload = {'issue_id':item['id']}
            if action.startswith('dependency.'):
                payload['depends_on_id'] = target['id']
                direct = lambda:getattr(dependencies, action.split('.')[1])(self.actor, item['id'], target['id'], item['revision'])
            elif action == 'set_parent':
                payload['parent_issue_id'] = target['id']
                direct = lambda:hierarchy.set_parent(self.actor, item['id'], target['id'], item['revision'])
            elif action == 'transition':
                payload.update(target='blocked', reason='Waiting', blocked_owner_user_id=self.reader.pk)
                direct = lambda:transitions.transition(self.actor, item['id'], 'blocked', item['revision'], 'Waiting', self.reader.pk)
            else:
                direct = lambda:issues.archive(self.actor, item['id'], item['revision'])
            with self.subTest(action=action):
                self.deny_unchanged(direct)
                self.deny_unchanged(lambda:self.act(self.actor, 'issue.'+action, payload, key=action, revision=item['revision']))

    def test_read_only_requirement_grant_permits_metadata_change_but_not_content_edit(self):
        self.restrict(); self.grant(write=False)
        self.deny_unchanged(lambda:issues.update(self.actor, self.item['id'], 1, description='New'))
        self.deny_unchanged(lambda:self.act(self.actor, 'issue.update', {'issue_id':self.item['id'], 'description':'New'}, key='edit', revision=1))
        row = self.act(self.actor, 'issue.transition', {'issue_id':self.item['id'], 'target':'todo'}, key='status', revision=1).data
        self.assertEqual(row['status_key'], 'todo')
        self.assertTrue(issues.archive(self.actor, row['id'], row['revision'])['archived'])

    def test_content_edit_propagates_roots_and_tracks_input_and_output_versions(self):
        self.restrict(); grant = self.grant()
        result = self.act(self.actor, 'issue.update', {'issue_id':self.item['id'], 'description':'Updated'}, key='edit', revision=1)
        old = issues.requirement_ref(self.item['requirements_version_id'])
        new = issues.requirement_ref(result.data['requirements_version_id'])
        self.assertIn(self.source, derive_scope([issues.ref(self.item['id']), new]).source_refs)
        for refs in (AuditEvent.objects.filter(action_id='issue.update').get().scope_refs,
                     Outbox.objects.filter(action_id='issue.update').get().scope_refs,
                     IdempotencyResult.objects.get(action_id='issue.update', key='edit').scope_refs):
            for ref in (old, new, self.source):
                self.assertIn({'kind':ref.kind, 'id':ref.id}, refs)
        grant.delete()
        self.deny_unchanged(lambda:issues.read(self.actor, result.data['id']))

    def test_existing_and_new_assignees_without_requirement_access_roll_back(self):
        assigned = self.act(self.actor, 'issue.update', {'issue_id':self.item['id'], 'assignee_user_id':self.reader.pk}, key='assign', revision=1).data
        self.restrict(assigned); self.grant()
        self.deny_unchanged(lambda:self.act(self.actor, 'issue.update', {'issue_id':assigned['id'], 'title':'Copy'}, key='copy', revision=assigned['revision']))
        fresh = issues.create(self.actor, self.project['id'], 'Fresh')
        self.restrict(fresh)
        self.deny_unchanged(lambda:issues.update(self.actor, fresh['id'], fresh['revision'], assignee_user_id=self.reader.pk))
