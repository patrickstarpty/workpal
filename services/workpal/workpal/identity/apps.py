from django.apps import AppConfig
from django.db.backends.signals import connection_created

def configure(sender, connection, **kwargs):
    if connection.vendor == "sqlite":
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA busy_timeout=5000")

class IdentityConfig(AppConfig):
    name = "workpal.identity"
    def ready(self):
        connection_created.connect(configure, dispatch_uid="workpal.sqlite")
        from .action_specs import register_actions
        register_actions()
        from .directory_actions import register_actions as register_directory
        register_directory()
