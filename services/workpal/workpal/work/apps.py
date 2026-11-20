from django.apps import AppConfig

class WorkConfig(AppConfig):
    name = 'workpal.work'
    def ready(self):
        from .actions import register_actions
        register_actions()
        from .resource_actions import register_actions as register_resource_actions
        register_resource_actions()
        from .issue_actions import register_actions as register_issue_actions
        register_issue_actions()

        from .issue_actions import register_fact_actions
        register_fact_actions()

        from .issue_actions import register_hierarchy_actions
        register_hierarchy_actions()

        from .activity_actions import register_actions as register_activity_actions
        register_activity_actions()
