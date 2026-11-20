from django.apps import AppConfig

class CollaborationConfig(AppConfig):
    name = 'workpal.collaboration'
    def ready(self):
        from .actions import register_actions
        register_actions()
