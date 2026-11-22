"""Real historical 0012 upgrade and rollback coverage."""
import pytest
from sqlalchemy.exc import IntegrityError
from test_issue_status_migration import legacy, upgrade, snapshot, schema


def test_historical_nul_baseline_and_atomic_failure(legacy):
    upgrade(legacy, '0012')
    with legacy.begin() as c:
        c.exec_driver_sql('UPDATE issue_status SET icon=? WHERE id=?', ('a\0b', 'custom'))
    before, ddl = snapshot(legacy), schema(legacy)
    with pytest.raises(IntegrityError):
        upgrade(legacy, '0013')
    assert snapshot(legacy) == before
    assert schema(legacy) == ddl


def test_valid_upgrade_preserves_schema_and_values(legacy):
    upgrade(legacy, '0012')
    before, ddl = snapshot(legacy), schema(legacy)
    upgrade(legacy, '0013')
    after = snapshot(legacy)
    assert after.pop('alembic_version') == [('0013',)]
    before.pop('alembic_version')
    assert after == before
    newddl = schema(legacy)
    assert [(t,n,tbl,s) for t,n,tbl,s in ddl if n != 'issue_status'] == [(t,n,tbl,s) for t,n,tbl,s in newddl if n != 'issue_status']
    oldsql = next(s for t,n,tbl,s in ddl if n == 'issue_status')
    newsql = next(s for t,n,tbl,s in newddl if n == 'issue_status')
    assert oldsql.rstrip()[:-1] in newsql
    with legacy.begin() as c:
        for statement, params in [
            ('UPDATE issue_status SET icon=? WHERE id=?', ('a\0b','custom')),
            ("INSERT INTO issue_status(id,workspace_id,key,name,category,color,created_at,updated_at,icon) VALUES ('new','w','new','New','started','#abcdef','c','u',?)", ('a\0b',)),
            ("UPDATE issue_status SET name='TODO' WHERE id='custom'", ()),
        ]:
            with pytest.raises(IntegrityError):
                c.exec_driver_sql(statement, params)
        c.exec_driver_sql("UPDATE issue_status SET archived_at='a' WHERE id='custom'")
        c.exec_driver_sql("INSERT INTO issue_status(id,workspace_id,key,name,category,color,created_at,updated_at) VALUES ('new','w','new','CUSTOM','started','#abcdef','c','u')")
    final = snapshot(legacy)
    upgrade(legacy, '0013')
    assert snapshot(legacy) == final
