from alembic import context
connection = context.config.attributes['connection']
from workpal_backend.infrastructure.sqlite_compat import install
install(connection.engine, connection)
context.configure(connection=connection)
with context.begin_transaction(): context.run_migrations()
