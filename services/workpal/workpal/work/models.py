from django.db import models

class Project(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    workflow_version = models.ForeignKey('workflows.WorkflowVersion', null=True, blank=True, on_delete=models.PROTECT)
    name = models.CharField(max_length=200)
    description = models.TextField(max_length=10000, blank=True, default='')
    archived = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class ProjectResource(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    label = models.CharField(max_length=200)
    provider = models.CharField(max_length=20, choices=[('github','github'),('azure_repos','azure_repos')])
    repository_ref = models.CharField(max_length=2000)
    checkout_ref = models.CharField(max_length=500, blank=True, default='')
    verification_status = models.CharField(max_length=20, default='unverified', editable=False)
    archived = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class Issue(models.Model):
    parent = models.ForeignKey("self", null=True, blank=True, on_delete=models.PROTECT, related_name="children")
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    project = models.ForeignKey(Project, on_delete=models.PROTECT)
    archived = models.BooleanField(default=False)
    revision = models.PositiveBigIntegerField(default=1)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT, related_name='+')
    assignee = models.ForeignKey('auth.User', null=True, on_delete=models.PROTECT, related_name='+')
    blocked_reason = models.TextField(default="")
    blocked_owner = models.ForeignKey("auth.User", null=True, on_delete=models.PROTECT, related_name="+")
    status_key = models.CharField(max_length=64)
    workflow_snapshot = models.JSONField()
    current_requirements = models.ForeignKey('IssueRequirements', null=True, on_delete=models.PROTECT, related_name='+')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class IssueRequirements(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT)
    number = models.PositiveBigIntegerField()
    title = models.CharField(max_length=300)
    description = models.TextField(default='')
    criteria = models.JSONField(default=list)
    sha256 = models.CharField(max_length=64)
    created_by = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['issue','number'], name='issue_requirements_number')]

class IssueTransition(models.Model):
    completion_review = models.ForeignKey("delivery.Review", null=True, on_delete=models.PROTECT, related_name="+")
    completion_snapshot = models.JSONField(default=dict)
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT)
    from_key = models.CharField(max_length=64)
    to_key = models.CharField(max_length=64)
    actor_user_id = models.PositiveBigIntegerField()
    actor_executor_id = models.CharField(max_length=200, null=True)
    reason = models.TextField(default='')
    before_blocked_owner_id = models.PositiveBigIntegerField(default=0)
    after_blocked_owner_id = models.PositiveBigIntegerField(default=0)
    before_blocked_reason = models.TextField(default='')
    after_blocked_reason = models.TextField(default='')
    requirements_version = models.ForeignKey(IssueRequirements, on_delete=models.PROTECT)
    workflow_sha256 = models.CharField(max_length=64)
    revision = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

class IssueDependency(models.Model):
    issue = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='dependencies')
    depends_on = models.ForeignKey(Issue, on_delete=models.PROTECT, related_name='+')
    active = models.BooleanField(default=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['issue','depends_on'], name='issue_dependency_pair')]
