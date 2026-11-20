from django.urls import path
from workpal.identity.actions import endpoint
urlpatterns = [path("api/v1/auth/"+name, endpoint) for name in ("csrf","login","logout","revoke-sessions")]
from workpal.actions.http import resource_endpoint
urlpatterns += [path("api/v1/workspaces/<int:workspace_id>", resource_endpoint)]

urlpatterns += [path("api/v1/workspaces/<int:workspace_id>/members", resource_endpoint), path("api/v1/workspaces/<int:workspace_id>/members/<int:membership_id>", resource_endpoint), path("api/v1/workspaces/<int:workspace_id>/members/<int:membership_id>/revoke", resource_endpoint)]

from workpal.actions.http import endpoint as action_endpoint
urlpatterns += [path('api/v1/actions', action_endpoint), path('api/v1/actions/<str:action_id>', action_endpoint)]

from workpal.work.http import endpoint as issue_endpoint
urlpatterns += [path('api/v1/workspaces/<int:workspace_id>/issues', issue_endpoint), path('api/v1/issues/<int:issue_id>/transitions', issue_endpoint)]

from workpal.delivery.http import endpoint as artifact_endpoint
urlpatterns += [path('api/v1/artifact-uploads/<str:upload_id>/chunks', artifact_endpoint), path('api/v1/artifacts/<str:artifact_id>/chunks', artifact_endpoint)]

from workpal.delivery.resource_http import endpoint as delivery_resource_endpoint
urlpatterns += [path('api/v1/issues/<int:issue_id>/deliveries', delivery_resource_endpoint), path('api/v1/deliveries/<int:delivery_id>/reviews', delivery_resource_endpoint)]

from workpal.identity.actions import session_endpoint
urlpatterns += [path("api/v1/auth/session", session_endpoint)]

from workpal.web import page
urlpatterns += [path('', page), path('app-assets/<path:asset>', page)]

from workpal.agents.runtime_http import issue as runtime_issue, pair as runtime_pair
urlpatterns += [path('api/v1/workspaces/<int:workspace_id>/runtime-pairings', runtime_issue), path('api/runtime/v1/pair', runtime_pair)]

from workpal.investigation.evidence_http import endpoint as evidence_endpoint
urlpatterns += [path('api/v1/investigations/<int:investigation_id>/evidence-uploads', evidence_endpoint), path('api/v1/evidence/<int:evidence_id>', evidence_endpoint), path('api/v1/investigations/<int:investigation_id>/evidence', evidence_endpoint)]

from workpal.execution.runtime_http import claim as lease_claim, renew as lease_renew
urlpatterns += [path('api/runtime/v1/claim', lease_claim), path('api/runtime/v1/runs/<int:run_id>/renew', lease_renew)]
