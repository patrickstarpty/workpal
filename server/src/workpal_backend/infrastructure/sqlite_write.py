"""SQLite writer reservation acquired before any mutation-dependent reads."""
import sqlite3
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from .wakeup_transactions import _ACTOR_SQL, _HANDOFF_SQL


class SQLiteWriteTransaction:
    def __init__(self, engine):
        self.connection = engine.connect()
        self._closed = False
        try:
            # The connection's busy_timeout bounds SQLite's lock wait. No
            # callback is replayed: it may eventually include external effects.
            self.connection.exec_driver_sql('BEGIN IMMEDIATE')
        except BaseException as error:
            self.connection.close()
            self._closed = True
            if isinstance(error, OperationalError) and (
                getattr(error.orig, 'sqlite_errorcode', 0) & 255
            ) in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED):
                from .database import DatabaseBusy
                raise DatabaseBusy('Database is busy; retry later') from error
            raise
        self.session = Session(bind=self.connection, join_transaction_mode='rollback_only')

    def execute(self, statement, arguments):
        if self._closed or not self.connection.in_transaction():
            raise RuntimeError('transaction is not active')
        if statement == _ACTOR_SQL:
            keys = ('workpal.actor_type', 'workpal.actor_id', 'workpal.source_task_id')
        elif statement == _HANDOFF_SQL:
            keys = ('workpal.handed_to_agent',)
        else:
            raise ValueError('unsupported transaction statement')
        if len(arguments) != len(keys) or not all(isinstance(value, str) for value in arguments):
            raise ValueError('invalid transaction attribution')
        # SQLite triggers read these through workpal_setting(). This is owned
        # by the physical connection and cleared when its transaction closes.
        self.connection.info['transaction_settings'].update(zip(keys, arguments))

    def commit(self):
        if self._closed:
            raise RuntimeError('transaction is closed')
        self.session.flush()
        self.connection.commit()

    def rollback(self):
        if self._closed:
            return
        try:
            self.session.close()
        finally:
            try:
                self.connection.rollback()
            finally:
                self.connection.info['transaction_settings'] = {}
                self.connection.close()
                self._closed = True
