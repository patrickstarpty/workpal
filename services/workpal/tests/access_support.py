from django.contrib.auth import get_user_model
from workpal.contracts import Actor, ObjectRef, DomainError
from workpal.identity.models import Workspace, Membership


class AccessFixtures:
    def setUp(self):
        from workpal.access.service import register_object
        self.register = register_object
        self.user = get_user_model().objects.create(username='reader')
        self.workspace = Workspace.objects.create(name='one')
        self.other = Workspace.objects.create(name='two')
        self.member = Membership.objects.create(user=self.user, workspace=self.workspace, role='member')
        self.actor = Actor(self.user.pk, self.workspace.pk)
        self.a = self.register(self.workspace.pk, ObjectRef('source', 'a'), is_source=True)
        self.b = self.register(self.workspace.pk, ObjectRef('source', 'b'), is_source=True)
        self.direct = self.register(self.workspace.pk, ObjectRef('doc', 'direct'), [self.a])
        self.deep = self.register(self.workspace.pk, ObjectRef('doc', 'deep'), [self.direct])

    def grant(self, ref, **kwargs):
        from workpal.access.models import SourceGrant, RegisteredObject
        return SourceGrant.objects.create(user=self.user, source=RegisteredObject.objects.get(kind=ref.kind, object_id=ref.id), **kwargs)

    def allowed(self, refs, action='read'):
        from workpal.access.service import authorize
        authorize(self.actor, action, refs)

    def denied(self, refs, action='read'):
        with self.assertRaises(DomainError):
            self.allowed(refs, action)
