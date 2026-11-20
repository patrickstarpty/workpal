from django.db import models
from django.conf import settings
from .contracts import ACTIVE,STATES
class Run(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    issue=models.ForeignKey('work.Issue',on_delete=models.PROTECT)
    requirements=models.ForeignKey('work.IssueRequirements',on_delete=models.PROTECT)
    project=models.ForeignKey('work.Project',on_delete=models.PROTECT)
    agent=models.ForeignKey('agents.Agent',on_delete=models.PROTECT)
    status=models.CharField(max_length=32,choices=[(s,s) for s in STATES],default='deferred')
    lease_owner=models.ForeignKey('agents.Runtime',null=True,on_delete=models.PROTECT)
    lease_epoch=models.PositiveBigIntegerField(default=0)
    lease_expires_at=models.DateTimeField(null=True)
    revision=models.PositiveIntegerField(default=1)
    input_snapshot=models.JSONField()
    sha256=models.CharField(max_length=64)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['workspace','issue','agent'],condition=models.Q(status__in=ACTIVE),name='one_active_manual_run')]
class Intent(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    key=models.CharField(max_length=200)
    digest=models.CharField(max_length=64)
    run=models.ForeignKey(Run,on_delete=models.CASCADE)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['workspace','actor','key'],name='unique_run_start_intent')]

class RuntimeClaimScan(models.Model):
    runtime=models.OneToOneField('agents.Runtime',on_delete=models.PROTECT,primary_key=True)
    last_pk=models.PositiveBigIntegerField(default=0)
    revision=models.PositiveBigIntegerField(default=0)

class TaskToken(models.Model):
    run=models.ForeignKey(Run,on_delete=models.PROTECT)
    runtime=models.ForeignKey('agents.Runtime',on_delete=models.PROTECT)
    epoch=models.PositiveBigIntegerField()
    secret_hash=models.CharField(max_length=64,unique=True)
    expires_at=models.DateTimeField()
    revoked_at=models.DateTimeField(null=True)
    scope_refs=models.JSONField(default=list)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['run'],condition=models.Q(revoked_at__isnull=True),name='one_live_task_token_per_run')]
