from django.apps import AppConfig
class WorkflowsConfig(AppConfig):
    name = 'workpal.workflows'
    def ready(self):
        from .actions import register_actions
        register_actions()
        from .graph_actions import register_actions as register_graph_actions
        register_graph_actions()
        from .instance_actions import register_actions as register_instance_actions
        register_instance_actions()
