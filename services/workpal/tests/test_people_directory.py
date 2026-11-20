from django.test import TransactionTestCase
from tests.access_support import AccessFixtures
from workpal.actions import registry
from workpal.contracts import ActionRequest

class PeopleDirectoryTests(AccessFixtures, TransactionTestCase):
    def test_registered_member_directory(self):
        result = registry.execute(self.actor, ActionRequest('workspace.people.list', {}, None, None))
        self.assertEqual(result.state, 'completed')
        self.assertEqual(result.data, {'items': [{'user_id': self.user.pk, 'username': self.user.username}], 'next_cursor': 0})

    def test_direct_invalid_inputs(self):
        from workpal.identity.directory import list_people
        from workpal.contracts import DomainError
        for field, values in {
            'query': [None, True, 1, 'x' * 151, '\x00', '\ud800'],
            'cursor': [None, True, -1, 2**63, 1.5, '1'],
            'limit': [None, True, 0, 201, 1.5, '1'],
        }.items():
            for value in values:
                with self.subTest(field=field, value=repr(value)):
                    with self.assertRaises(DomainError) as caught:
                        list_people(self.actor, **{field: value})
                    self.assertEqual(caught.exception.status, 400)

    def test_roles(self):
        from workpal.contracts import DomainError
        for role in ('member', 'admin', 'owner'):
            self.member.role = role
            self.member.save()
            self.test_registered_member_directory()
            if role == 'member':
                with self.assertRaises(DomainError) as caught:
                    registry.execute(self.actor, ActionRequest('member.list', {}, None, None))
                self.assertEqual(caught.exception.status, 403)

    def test_literal_search_and_pages(self):
        from django.contrib.auth import get_user_model
        from workpal.identity.models import Membership
        from workpal.identity.directory import list_people
        ids = []
        for i in range(7):
            user = get_user_model().objects.create(username=f'Ab%_{i}')
            Membership.objects.create(user=user, workspace=self.workspace, role='member')
            ids.append(user.pk)
        cursor = 0
        found = []
        for _ in range(3):
            page = list_people(self.actor, query='aB%_', cursor=cursor, limit=3)
            found += [r['user_id'] for r in page['items']]
            cursor = page['next_cursor']
        self.assertEqual(found, ids)
        self.assertEqual(cursor, 0)

    def test_live_membership_and_activity(self):
        from workpal.identity.directory import list_people
        from workpal.contracts import DomainError
        self.test_registered_member_directory()
        self.user.is_active = False
        self.user.save()
        with self.assertRaises(DomainError) as caught:
            list_people(self.actor)
        self.assertEqual(caught.exception.status, 404)
        self.user.is_active = True
        self.user.save()
        self.member.delete()
        with self.assertRaises(DomainError):
            list_people(self.actor)
