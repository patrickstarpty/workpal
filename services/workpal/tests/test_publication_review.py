from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.db import connections
from django.test import TestCase, TransactionTestCase

from workpal.access import service
from workpal.access.models import Publication, RegisteredObject, SourceGrant
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Membership
from .access_support import AccessFixtures


class PublicationFixtures(AccessFixtures):
    def setUp(self):
        super().setUp()
        self.creator_grant = self.grant(self.a, read=True)
        self.reviewer = get_user_model().objects.create_user('reviewer')
        self.reviewer_member = Membership.objects.create(user=self.reviewer, workspace=self.workspace, role='member')
        self.review_actor = Actor(self.reviewer.pk, self.workspace.pk)
        self.review_grant = SourceGrant.objects.create(
            user=self.reviewer, source=RegisteredObject.objects.get(kind=self.a.kind, object_id=self.a.id),
            read=True, publish=True,
        )
        service.store_content(self.workspace.pk, self.direct, b'approved content', [self.a])
        self.draft = service.prepare_publication(self.actor, [], 'repo:connection:repository', self.direct)

    def approve(self, actor=None):
        p = self.draft
        return service.approve_publication(actor or self.review_actor, p.id, p.revision, p.content_hash, p.destination)

    def send_check(self, actor=None):
        return service.authorize_publication(actor or self.actor, self.draft.id, self.draft.content_hash)


class PublicationBoundaryTests(PublicationFixtures, TestCase):
    def test_independent_approver_membership_revocation_blocks_release(self):
        self.approve()
        self.send_check()
        self.reviewer_member.delete()
        with self.assertRaises(DomainError):
            self.send_check()

    def test_independent_approver_publish_revocation_blocks_release(self):
        self.approve()
        self.review_grant.publish = False
        self.review_grant.save()
        with self.assertRaises(DomainError):
            self.send_check()

    def test_creator_access_revocation_blocks_release(self):
        self.approve()
        self.creator_grant.delete()
        with self.assertRaises(DomainError):
            self.send_check()

    def test_other_user_cannot_reuse_creator_permission(self):
        self.approve()
        with self.assertRaises(DomainError):
            self.send_check(self.review_actor)

    def test_content_scope_cannot_be_omitted_and_original_stays_restricted(self):
        self.assertEqual(self.draft.source_refs, {self.a})
        self.approve()
        outsider = get_user_model().objects.create_user('outsider')
        Membership.objects.create(user=outsider, workspace=self.workspace, role='owner')
        actor = Actor(outsider.pk, self.workspace.pk)
        for call in (lambda: service.authorize(actor, 'read', [self.direct]),
                     lambda: service.read_publication(actor, self.draft.id)):
            with self.assertRaises(DomainError):
                call()

    def test_explicit_additional_source_needs_both_people_permissions(self):
        with self.assertRaises(DomainError):
            service.prepare_publication(self.actor, [self.b], self.draft.destination, self.direct)
        self.grant(self.b, read=True)
        p = service.prepare_publication(self.actor, [self.b], self.draft.destination, self.direct)
        self.assertEqual(p.source_refs, {self.a, self.b})
        with self.assertRaises(DomainError):
            service.approve_publication(self.review_actor, p.id, p.revision, p.content_hash, p.destination)

    def test_malformed_identifier_is_a_domain_error(self):
        with self.assertRaises(DomainError):
            service.read_publication(self.actor, 'not-a-uuid')

    def test_boolean_revision_cannot_approve_version_one(self):
        p = self.draft
        with self.assertRaises(DomainError):
            service.approve_publication(self.review_actor, p.id, True, p.content_hash, p.destination)

    def test_expiry_cannot_be_extended_without_a_new_approval(self):
        self.approve()
        row = Publication.objects.get(pk=self.draft.id)
        row.expires_at += timedelta(days=1)
        row.save(update_fields=['expires_at'])
        with self.assertRaises(DomainError):
            self.send_check()


class ConcurrentPublicationTests(PublicationFixtures, TransactionTestCase):
    def test_two_reviewers_only_one_revision_is_approved(self):
        second = get_user_model().objects.create_user('reviewer-two')
        Membership.objects.create(user=second, workspace=self.workspace, role='member')
        SourceGrant.objects.create(user=second, source=self.review_grant.source, read=True, publish=True)
        actors = [self.review_actor, Actor(second.pk, self.workspace.pk)]
        barrier = Barrier(2)

        def approve(actor):
            try:
                barrier.wait(timeout=10)
                try:
                    result = self.approve(actor)
                    return ('approved', actor.user_id, result.revision)
                except DomainError as error:
                    return (error.code, actor.user_id, None)
            finally:
                connections.close_all()

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(approve, actors))
        self.assertCountEqual([r[0] for r in results], ['approved', 'revision_conflict'])
        winner = next(r for r in results if r[0] == 'approved')
        row = Publication.objects.get(pk=self.draft.id)
        self.assertEqual((row.approver_id, row.revision), (winner[1], 2))
        self.send_check()
