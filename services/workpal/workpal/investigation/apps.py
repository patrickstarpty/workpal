from django.apps import AppConfig
class InvestigationConfig(AppConfig):
    name='workpal.investigation'
    def ready(self):
        from .actions import register_actions
        register_actions()
        from .evidence_actions import register_actions as register_evidence_actions
        register_evidence_actions()
