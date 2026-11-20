import uuid
from django.db import models
class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    workspace = models.ForeignKey('identity.Workspace',on_delete=models.CASCADE)
    actor_id = models.BigIntegerField()
    action_id = models.CharField(max_length=160)
    outcome = models.CharField(max_length=40)
    object_refs = models.JSONField(default=list)
    scope_refs = models.JSONField(default=list)
    fields = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
class Outbox(models.Model):
    event = models.OneToOneField(AuditEvent,on_delete=models.CASCADE)
    workspace = models.ForeignKey('identity.Workspace',on_delete=models.CASCADE)
    action_id = models.CharField(max_length=160)
    object_refs = models.JSONField(default=list)
    scope_refs = models.JSONField(default=list)
    status = models.CharField(max_length=20,default='pending')
