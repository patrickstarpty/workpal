from django.apps import AppConfig

class DeliveryConfig(AppConfig):
    name = 'workpal.delivery'
    def ready(self):
        from .artifact_actions import register_actions
        register_actions()
        from .actions import register_actions as register_deliveries
        register_deliveries()
        from .selection_actions import register_actions as register_selection
        register_selection()
        from .review_actions import register_actions as register_reviews
        register_reviews()
        from .comparison_actions import register_actions as register_comparison
        register_comparison()
        from .approval_actions import register_actions as register_approval
        register_approval()
