from django.apps import AppConfig
class AgentsConfig(AppConfig):
    name='workpal.agents'
    def ready(self):
        from .actions import register_actions
        register_actions()
        from .runtime_actions import register_actions as register_runtime_actions
        register_runtime_actions()
