from django.test import TestCase
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, ObjectRef, DomainError
from workpal.identity.models import Workspace, Membership

class AccessTests(TestCase):
    def test_unknown_capability_denied(self):
        from workpal.access.service import authorize
        u = get_user_model().objects.create(username='access')
        w = Workspace.objects.create(name='access')
        Membership.objects.create(user=u, workspace=w, role='owner')
        with self.assertRaises(DomainError):
            authorize(Actor(u.pk, w.pk), 'unknown', [])

from .access_support import AccessFixtures

class SourceAccessTests(AccessFixtures, TestCase):
    def test_plain_and_empty(self):
        ref = self.register(self.workspace.pk, ObjectRef('doc', 'plain'))
        self.allowed([ref]); self.allowed([ref], 'write'); self.allowed([])

    def test_cross_workspace_and_unknown(self):
        ref = self.register(self.other.pk, ObjectRef('doc', 'other'))
        self.denied([ref]); self.denied([ObjectRef('missing', 'x')])
        from workpal.access.service import derive_scope
        for refs in ([], [self.a, ref]):
            with self.assertRaises(DomainError):
                derive_scope(refs)

    def test_all_sources_required(self):
        ref = self.register(self.workspace.pk, ObjectRef('doc', 'combined'), [self.a, self.b])
        self.grant(self.a, read=True)
        self.denied([ref])
        self.grant(self.b, read=True)
        self.allowed([ref])

    def test_admin_cannot_bypass(self):
        self.member.role = 'admin'; self.member.save()
        self.denied([self.a]); self.denied([self.deep])

    def test_revocation_is_immediate(self):
        grant = self.grant(self.a, read=True)
        self.allowed([self.a, self.direct, self.deep])
        grant.delete()
        for ref in (self.a, self.direct, self.deep):
            self.denied([ref])

    def test_source_requires_grant_and_capabilities(self):
        self.denied([self.a])
        grant = self.grant(self.a, write=True, publish=True)
        self.denied([self.a], 'write'); self.denied([self.a], 'publish')
        grant.read = True; grant.save()
        for action in ('read', 'write', 'publish'):
            self.allowed([self.deep], action)

    def test_unavailable_stays_restricted(self):
        from workpal.access.models import RegisteredObject
        self.grant(self.a, read=True)
        RegisteredObject.objects.filter(kind=self.a.kind, object_id=self.a.id).update(available=False)
        self.denied([self.deep])
        with self.assertRaises(DomainError):
            self.register(self.workspace.pk, ObjectRef('doc', 'bad'), [self.a])

    def test_foreign_source_rejected(self):
        with self.assertRaises(DomainError):
            self.register(self.other.pk, ObjectRef('doc', 'bad'), [self.a])

    def test_provenance_cannot_be_removed_and_cycles_rejected(self):
        self.register(self.workspace.pk, self.direct)
        self.denied([self.direct])
        with self.assertRaises(DomainError):
            self.register(self.workspace.pk, self.direct, [self.deep])
        self.grant(self.a, read=True)
        self.allowed([self.deep])

    def test_membership_and_account_rechecked(self):
        self.grant(self.a, read=True)
        self.user.is_active = False; self.user.save()
        self.denied([self.deep])
        self.user.is_active = True; self.user.save()
        self.member.delete()
        self.denied([self.deep])

    def test_referenced_source_cannot_be_deleted_into_public_access(self):
        from django.db.models.deletion import ProtectedError
        from workpal.access.models import RegisteredObject
        source = RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id)
        with self.assertRaises(ProtectedError):
            source.delete()
        self.denied([self.deep])
