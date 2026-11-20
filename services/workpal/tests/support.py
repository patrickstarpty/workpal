from django.test import TestCase
from workpal.actions.registry import execute
from workpal.contracts import ActionRequest

class WorkpalCase(TestCase):
    """Shared business seam; HTTP tests also use TestCase's real Django client."""
    def act(self, actor, action, payload, key=None, revision=None, confirmation_id=None):
        return execute(actor, ActionRequest(action, payload, revision, key, confirmation_id))


def identity_post(client, path, payload, token):
    import json
    from uuid import uuid4
    headers = dict(HTTP_X_CSRFTOKEN=token, HTTP_IDEMPOTENCY_KEY=str(uuid4()))
    response = client.post(path, json.dumps(payload), content_type='application/json', **headers)
    if response.status_code == 200 and response.json().get('state') == 'waiting_confirmation':
        headers['HTTP_X_CONFIRMATION_ID'] = response.json()['data']['confirmation_id']
        response = client.post(path, json.dumps(payload), content_type='application/json', **headers)
    return response
