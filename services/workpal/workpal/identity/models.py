from django.conf import settings
from django.db import models

class Workspace(models.Model):
    name = models.CharField(max_length=200)
    revision = models.PositiveIntegerField(default=1)

class Membership(models.Model):
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=[(x,x) for x in ("owner","admin","member")])
    revision = models.PositiveIntegerField(default=1)
    class Meta:
        constraints = [models.UniqueConstraint(fields=["workspace","user"], name="unique_workspace_member")]

class LoginAttempt(models.Model):
    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    updated = models.DateTimeField(auto_now=True)
