from django.db import models
from django.conf import settings
class Agent(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
    provider_key=models.CharField(max_length=30,default='copilot_cli')
    model=models.CharField(max_length=200,blank=True)
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

class Runtime(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
    credential_hash=models.CharField(max_length=64,unique=True)
    revoked_at=models.DateTimeField(null=True)
    revision=models.PositiveIntegerField(default=1)
    created_at=models.DateTimeField(auto_now_add=True)

class RuntimePairing(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
    secret_hash=models.CharField(max_length=64,unique=True)
    expires_at=models.DateTimeField()
    consumed_at=models.DateTimeField(null=True)
    runtime=models.OneToOneField(Runtime,on_delete=models.PROTECT,null=True)
    revision=models.PositiveIntegerField(default=1)

class RuntimeBinding(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    agent=models.ForeignKey(Agent,on_delete=models.PROTECT)
    runtime=models.ForeignKey(Runtime,on_delete=models.PROTECT)
    enabled=models.BooleanField(default=True)
    revision=models.PositiveIntegerField(default=1)

    class Meta:
        constraints=[models.UniqueConstraint(fields=('workspace','agent'), name='unique_workspace_agent_runtime_binding')]
