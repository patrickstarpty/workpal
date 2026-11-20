from django.db import models
class WorkflowDraft(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    definition = models.JSONField()
    revision = models.PositiveBigIntegerField(default=1)
    current_version = models.ForeignKey('WorkflowVersion', null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
class WorkflowVersion(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    draft = models.ForeignKey(WorkflowDraft, on_delete=models.PROTECT)
    number = models.PositiveBigIntegerField()
    name = models.CharField(max_length=200)
    definition = models.JSONField()
    sha256 = models.CharField(max_length=64)
    published_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    published_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['draft', 'number'], name='workflow_version_number')]

from .graph_models import GraphDraft, GraphVersion
