from .access_support import AccessFixtures
from django.test import TestCase
from workpal.contracts import DomainError

class PublicationTests(AccessFixtures, TestCase):
    def test_publication_lifecycle(self):
        from workpal.access.service import store_content, prepare_publication, approve_publication, authorize_publication
        self.grant(self.a, read=True, publish=True)
        store_content(self.workspace.pk, self.direct, b'hello', [self.a])
        p = prepare_publication(self.actor, [], 'jira:connection:project', self.direct)
        with self.assertRaises(DomainError):
            authorize_publication(self.actor, p.id, p.content_hash)
        p = approve_publication(self.actor, p.id, p.revision, p.content_hash, p.destination)
        authorize_publication(self.actor, p.id, p.content_hash)

    def test_guards_and_tampering(self):
        import hashlib
        from dataclasses import replace
        from workpal.access.service import store_content, prepare_publication, approve_publication, authorize_publication
        from workpal.access.models import Publication
        from django.utils import timezone
        from datetime import timedelta
        store_content(self.workspace.pk, self.direct, b'hello', [self.a])
        for body in (b'changed', b'x' * (1048576 + 1)):
            with self.assertRaises(DomainError):
                store_content(self.workspace.pk, self.direct, body)
        with self.assertRaises(DomainError):
            prepare_publication(self.actor, [], 'repo:c:r', self.direct)
        grant = self.grant(self.a, read=True)
        p = prepare_publication(self.actor, [], 'repo:c:r', self.direct)
        self.assertEqual(p.content_hash, hashlib.sha256(b'hello').hexdigest())
        self.assertEqual(p.source_refs, {self.a})
        def approve(actor=self.actor, revision=p.revision, hash=p.content_hash, destination=p.destination):
            return approve_publication(actor, p.id, revision, hash, destination)
        with self.assertRaises(DomainError): approve()
        grant.publish = True; grant.save()
        for kwargs in ({'actor': replace(self.actor, executor_id='agent')}, {'hash': 'wrong'}, {'destination': 'repo:other:r'}, {'revision': 99}):
            with self.assertRaises(DomainError): approve(**kwargs)
        approved = approve()
        with self.assertRaises(DomainError) as caught: approve()
        self.assertEqual(caught.exception.status, 409)
        authorize_publication(self.actor, p.id, p.content_hash)
        for changes in ({'body': b'evil'}, {'destination': 'repo:other:r'}, {'expires_at': timezone.now() - timedelta(seconds=1)}):
            row = Publication.objects.get(pk=p.id)
            original = {key: getattr(row, key) for key in changes}
            Publication.objects.filter(pk=p.id).update(**changes)
            with self.assertRaises(DomainError): authorize_publication(self.actor, p.id, p.content_hash)
            Publication.objects.filter(pk=p.id).update(**original)
        grant.publish = False; grant.save()
        with self.assertRaises(DomainError): authorize_publication(self.actor, p.id, p.content_hash)
        grant.publish = True; grant.read = False; grant.save()
        with self.assertRaises(DomainError): authorize_publication(self.actor, p.id, p.content_hash)
