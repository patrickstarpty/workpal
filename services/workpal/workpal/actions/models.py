import uuid
from django.db import models
class IdempotencyResult(models.Model):
    workspace = models.ForeignKey('identity.Workspace',on_delete=models.CASCADE)
    user = models.ForeignKey('auth.User',on_delete=models.CASCADE)
    action_id = models.CharField(max_length=160)
    key = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    result = models.JSONField()
    scope_refs = models.JSONField(default=list)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['workspace','user','action_id','key'],name='action_idempotency_scope')]

class Confirmation(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.CASCADE)
    user = models.ForeignKey('auth.User', on_delete=models.CASCADE)
    action_id = models.CharField(max_length=160)
    key = models.CharField(max_length=200)
    request_hash = models.CharField(max_length=64)
    expected_revision = models.PositiveIntegerField(null=True)
    scope_refs = models.JSONField(default=list)
    expires_at = models.DateTimeField()
    consumed = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace','user','action_id','key'], name='confirmation_scope')]
