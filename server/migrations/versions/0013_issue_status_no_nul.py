"""Reject NUL without normalizing historical status values.

Use stored SQLite DDL: reflection omits expression indexes and unnamed checks.
"""
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = depends_on = None


def upgrade():
    bind = op.get_bind()
    if bind.dialect.name != 'sqlite':
        raise RuntimeError('0013 requires SQLite')
    if not bind.connection.driver_connection.in_transaction:
        bind.exec_driver_sql('BEGIN')
    ddl = bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE type='table' AND name='issue_status'").scalar_one()
    indexes = bind.exec_driver_sql("SELECT sql FROM sqlite_master WHERE tbl_name='issue_status' AND type IN ('index','trigger') AND sql IS NOT NULL ORDER BY name").scalars().all()
    # Change only the table identifier and append one table constraint.
    body = ddl[ddl.index('('):].rstrip()
    constraint = 'instr(id, char(0)) = 0 AND instr(workspace_id, char(0)) = 0 AND instr(key, char(0)) = 0 AND instr(name, char(0)) = 0 AND instr(category, char(0)) = 0 AND instr(color, char(0)) = 0 AND instr(description, char(0)) = 0 AND instr(icon, char(0)) = 0 AND instr(created_at, char(0)) = 0 AND instr(updated_at, char(0)) = 0 AND instr(archived_at, char(0)) = 0'
    bind.exec_driver_sql('CREATE TABLE "_issue_status_nul_upgrade" ' + body[:-1] + ', CONSTRAINT issue_status_no_nul CHECK (' + constraint + '))')
    bind.exec_driver_sql('INSERT INTO "_issue_status_nul_upgrade" SELECT * FROM issue_status')
    bind.exec_driver_sql('DROP TABLE issue_status')
    bind.exec_driver_sql('ALTER TABLE "_issue_status_nul_upgrade" RENAME TO "issue_status"')
    for index in indexes:
        bind.exec_driver_sql(index)


def downgrade():
    raise RuntimeError('Status contract downgrade requires explicit data review')
