"""Independent graph configuration storage; no execution state."""
from django.db import models

class GraphDraft(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    definition = models.JSONField()
    revision = models.PositiveBigIntegerField(default=1)
    current_version = models.ForeignKey('GraphVersion', null=True, on_delete=models.PROTECT, related_name='+')

class GraphVersion(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    draft = models.ForeignKey(GraphDraft, on_delete=models.PROTECT)
    number = models.PositiveBigIntegerField()
    name = models.CharField(max_length=200)
    graph = models.JSONField()
    resolved_inputs = models.JSONField()
    published_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    published_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['draft', 'number'], name='graph_version_number')]

class GraphInstance(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    version = models.ForeignKey(GraphVersion, on_delete=models.PROTECT)
    issue = models.ForeignKey('work.Issue', on_delete=models.PROTECT)
    requirements = models.ForeignKey('work.IssueRequirements', on_delete=models.PROTECT)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    state = models.CharField(max_length=16, default='initialized')
    snapshot = models.JSONField()
    sha256 = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
