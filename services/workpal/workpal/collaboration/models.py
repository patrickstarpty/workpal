from django.conf import settings
from django.db import models

class Comment(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    issue = models.ForeignKey('work.Issue', on_delete=models.PROTECT)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    body = models.TextField()
    mention_user_ids = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    archived = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

class Subscription(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    issue = models.ForeignKey('work.Issue', on_delete=models.PROTECT)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace','issue','user'], name='collaboration_subscription_unique')]

class Notification(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    issue = models.ForeignKey('work.Issue', on_delete=models.PROTECT)
    comment = models.ForeignKey(Comment, on_delete=models.PROTECT, null=True)
    kind = models.CharField(max_length=20, choices=[('comment','comment'),('mention','mention'),('assignment','assignment'),('blocked','blocked')])
    event_key = models.CharField(max_length=100)
    revision = models.PositiveIntegerField(default=1)
    read_at = models.DateTimeField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace','recipient','event_key'], name='collaboration_notification_unique')]
