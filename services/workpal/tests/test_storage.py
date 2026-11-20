import sqlite3
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from django.db import connection, connections, IntegrityError, OperationalError
from django.test import TransactionTestCase
from django.contrib.auth import get_user_model
from workpal.contracts import Actor, DomainError
from workpal.identity.models import Workspace, Membership
from workpal.identity.service import rename_workspace
from workpal.storage import atomic_write


class StorageTests(TransactionTestCase):
    def test_connection_defaults(self):
        with connection.cursor() as c:
            for pragma, expected in [('journal_mode', 'wal'), ('foreign_keys', 1), ('busy_timeout', 5000)]:
                self.assertEqual(c.execute('PRAGMA ' + pragma).fetchone()[0], expected)
        self.assertEqual(connection.settings_dict['OPTIONS']['transaction_mode'], 'IMMEDIATE')
        self.assertNotIn('memory', connection.settings_dict['NAME'])

    def test_concurrent_revision(self):
        w = Workspace.objects.create(name='original')
        u = get_user_model().objects.create_user(username='owner')
        Membership.objects.create(workspace=w, user=u, role='owner')
        barrier = Barrier(2)
        def rename(name):
            try:
                barrier.wait(timeout=10)
                try:
                    rename_workspace(Actor(u.pk, w.pk), w.pk, name, w.revision)
                    return name
                except DomainError as e:
                    return e.code
            finally:
                connections.close_all()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(rename, ['one', 'two']))
        self.assertEqual(results.count('revision_conflict'), 1)
        w.refresh_from_db()
        self.assertEqual(w.revision, 2)
        self.assertIn(w.name, results)

    def test_real_lock(self):
        locker = sqlite3.connect(connection.settings_dict['NAME'])
        try:
            locker.execute('BEGIN IMMEDIATE')
            with connection.cursor() as c:
                c.execute('PRAGMA busy_timeout=10')
            with self.assertRaises(DomainError) as caught:
                atomic_write(lambda: Workspace.objects.create(name='blocked'))
            self.assertEqual((caught.exception.code, caught.exception.status, caught.exception.retryable), ('storage_busy', 503, True))
            self.assertFalse(Workspace.objects.exists())
        finally:
            locker.rollback()
            locker.close()
            with connection.cursor() as c:
                c.execute('PRAGMA busy_timeout=5000')

    def test_exception_rolls_back(self):
        def write():
            Workspace.objects.create(name='rollback')
            raise ValueError('stop')
        with self.assertRaises(ValueError):
            atomic_write(write)
        self.assertFalse(Workspace.objects.exists())

    def test_foreign_key_rolls_back(self):
        def write():
            Workspace.objects.create(name='rollback')
            Membership.objects.create(workspace_id=99999, user_id=99999, role='owner')
        with self.assertRaises(IntegrityError):
            atomic_write(write)
        self.assertFalse(Workspace.objects.exists())

    def test_non_lock_error_is_private(self):
        def write():
            Workspace.objects.create(name='rollback')
            with connection.cursor() as c:
                c.execute('INSERT INTO nonexistent_secret_table VALUES (1)')
        with self.assertRaises(DomainError) as caught:
            atomic_write(write)
        self.assertEqual(caught.exception.code, 'storage_unavailable')
        self.assertEqual(caught.exception.status, 503)
        self.assertNotIn('secret', str(caught.exception))
        self.assertFalse(Workspace.objects.exists())
