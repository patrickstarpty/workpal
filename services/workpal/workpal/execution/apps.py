from django.apps import AppConfig
class ExecutionConfig(AppConfig):
    name='workpal.execution'
    def ready(self):
        from .actions import register_actions
        register_actions()
