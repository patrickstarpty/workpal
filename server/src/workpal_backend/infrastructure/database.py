from contextlib import contextmanager, closing
import sqlite3
from pathlib import Path
from sqlalchemy import create_engine, event, text, inspect
from sqlalchemy.orm import Session
from sqlalchemy.exc import OperationalError
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
BASE = Path(__file__).resolve().parents[3]
def migration_config():
    cfg = Config(str(BASE/'alembic.ini'))
    cfg.set_main_option('script_location', str(BASE/'migrations'))
    return cfg

def inspect_revisions(settings):
    path = Path(settings.database_url.removeprefix('sqlite:///'))
    if not path.exists(): return None
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if not tables: return None
        if 'alembic_version' not in tables:
            raise ValueError('Refusing an unrecognized existing database')
        return {row[0] for row in conn.execute('SELECT version_num FROM alembic_version')}

class DatabaseBusy(RuntimeError):
    """Retryable contention; caller must decide whether retry is idempotent."""
class Database:
    def __init__(self, settings):
        self.settings = settings
        self.engine = create_engine(settings.database_url, connect_args={'check_same_thread':False,'timeout':settings.busy_timeout_ms/1000})
        @event.listens_for(self.engine,'connect')
        def configure(conn, _):
            inspect_revisions(settings)
            conn.execute('PRAGMA foreign_keys=ON')
            conn.execute(f'PRAGMA busy_timeout={settings.busy_timeout_ms}')
            conn.execute('PRAGMA journal_mode=WAL')
    @contextmanager
    def transaction(self):
        try:
            with Session(self.engine) as session, session.begin(): yield session
        except OperationalError as exc:
            if 'locked' in str(exc).lower() or 'busy' in str(exc).lower():
                raise DatabaseBusy('Database is busy; retry later') from exc
            raise
    def readiness(self):
        revisions = inspect_revisions(self.settings)
        if not revisions: return 'error'
        required = set(ScriptDirectory.from_config(migration_config()).get_heads())
        return 'ok' if revisions == required else 'out_of_date'
    def close(self): self.engine.dispose()

def migrate(settings):
    path = Path(settings.database_url.removeprefix('sqlite:///'))
    inspect_revisions(settings)
    path.parent.mkdir(parents=True, exist_ok=True)
    db = Database(settings)
    try:
        with db.engine.connect() as conn:
            tables = inspect(conn).get_table_names()
            if tables and 'alembic_version' not in tables:
                raise ValueError('Refusing to migrate an unrecognized existing database')
            cfg = migration_config()
            cfg.attributes['connection'] = conn
            conn.commit()
            command.upgrade(cfg,'head')
            conn.commit()
    finally: db.close()
