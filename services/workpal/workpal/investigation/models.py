from django.db import models
from django.conf import settings
class Environment(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    project=models.ForeignKey('work.Project',on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
    timezone=models.CharField(max_length=100)
    revision=models.PositiveIntegerField(default=1)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['project','name'],name='unique_environment_name')]
class Service(models.Model):
    environment=models.ForeignKey(Environment,on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
class Source(models.Model):
    environment=models.ForeignKey(Environment,on_delete=models.PROTECT)
    name=models.CharField(max_length=200)
    adapter_type=models.CharField(max_length=20,default='upload')
    allowed_services=models.ManyToManyField(Service)
    current_policy=models.ForeignKey('EvidencePolicyVersion',on_delete=models.PROTECT,null=True,related_name='+')
    policy_revision=models.PositiveIntegerField(default=1)
    query_revision=models.PositiveIntegerField(default=1)
    current_query_config=models.ForeignKey('SourceQueryVersion',on_delete=models.PROTECT,null=True,related_name='+')
class Investigation(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    project=models.ForeignKey('work.Project',on_delete=models.PROTECT)
    environment=models.ForeignKey(Environment,on_delete=models.PROTECT)
    service=models.ForeignKey(Service,on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    problem=models.TextField()
    key=models.CharField(max_length=200)
    revision=models.PositiveIntegerField(default=1)
    status=models.CharField(max_length=30,default='investigating')
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['workspace','actor','key'],name='unique_investigation_intent')]

class EvidencePolicyVersion(models.Model):
    source=models.ForeignKey(Source,on_delete=models.PROTECT)
    revision=models.PositiveIntegerField()
    policy=models.JSONField()
    policy_sha256=models.CharField(max_length=64)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source','revision'],name='unique_evidence_policy_revision')]

class EvidenceSnapshot(models.Model):
    workspace=models.ForeignKey('identity.Workspace',on_delete=models.PROTECT)
    project=models.ForeignKey('work.Project',on_delete=models.PROTECT)
    environment=models.ForeignKey('investigation.Environment',on_delete=models.PROTECT)
    service=models.ForeignKey('investigation.Service',on_delete=models.PROTECT)
    source=models.ForeignKey('investigation.Source',on_delete=models.PROTECT)
    investigation=models.ForeignKey('investigation.Investigation',on_delete=models.PROTECT)
    actor=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    policy_version=models.ForeignKey('investigation.EvidencePolicyVersion',on_delete=models.PROTECT)
    key=models.CharField(max_length=200)
    request_hash=models.CharField(max_length=64)
    raw_sha256=models.CharField(max_length=64)
    content_sha256=models.CharField(max_length=64)
    policy_sha256=models.CharField(max_length=64)
    timezone=models.CharField(max_length=100)
    format=models.CharField(max_length=20)
    origin=models.CharField(max_length=30)
    coverage=models.CharField(max_length=30)
    status=models.CharField(max_length=20)
    raw_bytes=models.PositiveIntegerField()
    content_bytes=models.PositiveIntegerField()
    total_records=models.PositiveIntegerField()
    included_records=models.PositiveIntegerField()
    redaction_count=models.PositiveIntegerField()
    omitted_fields=models.PositiveIntegerField()
    content=models.TextField()
    included_line_numbers=models.JSONField()
    truncated=models.BooleanField()
    created_at=models.DateTimeField(auto_now_add=True)
    event_time=models.DateTimeField(null=True)
    deployment_id=models.TextField(null=True)
    commit_sha=models.TextField(null=True)
    original_location=models.TextField(null=True)
    range_start=models.CharField(max_length=64,null=True)
    range_end=models.CharField(max_length=64,null=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['workspace','actor','key'],name='unique_evidence_intent'),models.CheckConstraint(condition=models.Q(included_records__lte=models.F('total_records'),raw_bytes__lte=2097152,content_bytes__lte=2097152),name='bounded_evidence_counts')]

class SourceQueryVersion(models.Model):
    source=models.ForeignKey(Source,on_delete=models.PROTECT)
    revision=models.PositiveIntegerField()
    config=models.JSONField()
    config_sha256=models.CharField(max_length=64)
    policy_version=models.ForeignKey(EvidencePolicyVersion,on_delete=models.PROTECT)
    creator=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.PROTECT)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=['source','revision'],name='unique_source_query_revision')]
