from sqlalchemy import inspect
from workpal_backend.infrastructure.database import Database, migrate


def test_status_schema(settings):
    migrate(settings)
    db = Database(settings)
    columns = {c['name']: c for c in inspect(db.engine).get_columns('issue_status')}
    assert 'icon' in columns
    assert str(columns['position']['type']) == 'FLOAT'
    assert len(inspect(db.engine).get_check_constraints('issue_status')) >= 8
    db.close()
