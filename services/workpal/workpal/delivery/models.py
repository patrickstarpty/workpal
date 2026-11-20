from django.conf import settings
from django.db import models

class Upload(models.Model):
    artifact = models.OneToOneField("Artifact", null=True, blank=True, on_delete=models.PROTECT)
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.CASCADE)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    filename = models.CharField(max_length=255)
    media_type = models.CharField(max_length=127)
    size = models.PositiveIntegerField()
    received = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

class UploadChunk(models.Model):
    upload = models.ForeignKey(Upload, on_delete=models.CASCADE)
    offset = models.PositiveIntegerField()
    bytes = models.BinaryField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['upload', 'offset'], name='unique_upload_offset')]

class ArtifactBlob(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    sha256 = models.CharField(max_length=64)
    size = models.PositiveIntegerField()
    content = models.BinaryField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace', 'sha256', 'size'], name='unique_workspace_blob')]

class Artifact(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    filename = models.CharField(max_length=255)
    media_type = models.CharField(max_length=127)
    blob = models.ForeignKey(ArtifactBlob, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

class Delivery(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    subject_type = models.CharField(max_length=32)
    subject_id = models.CharField(max_length=255)
    number = models.PositiveIntegerField()
    source = models.CharField(max_length=16, default='human')
    submitted_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    summary = models.TextField()
    limitations = models.TextField(default='')
    requirements_snapshot = models.JSONField()
    workflow_snapshot = models.JSONField()
    artifacts_snapshot = models.JSONField()
    evidence = models.JSONField()
    sha256 = models.CharField(max_length=64)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace','subject_type','subject_id','number'], name='unique_delivery_number')]

class DeliveryArtifact(models.Model):
    delivery = models.ForeignKey(Delivery, on_delete=models.CASCADE)
    artifact = models.ForeignKey(Artifact, on_delete=models.PROTECT)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['delivery','artifact'], name='unique_delivery_artifact')]

class DeliveryCurrent(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    subject_type = models.CharField(max_length=32)
    subject_id = models.CharField(max_length=255)
    current_delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT)
    revision = models.PositiveIntegerField()
    class Meta:
        constraints = [models.UniqueConstraint(fields=['workspace','subject_type','subject_id'], name='unique_delivery_current')]

class DeliverySelection(models.Model):
    current = models.ForeignKey(DeliveryCurrent, on_delete=models.PROTECT)
    before_delivery = models.ForeignKey(Delivery, null=True, on_delete=models.PROTECT, related_name='+')
    after_delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT, related_name='+')
    revision = models.PositiveIntegerField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['current','revision'], name='unique_delivery_selection_revision')]

class Review(models.Model):
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    delivery = models.ForeignKey(Delivery, on_delete=models.PROTECT)
    current = models.ForeignKey(DeliveryCurrent, on_delete=models.PROTECT)
    version = models.PositiveIntegerField()
    revision = models.PositiveIntegerField()
    delivery_sha256 = models.CharField(max_length=64)
    requirements_snapshot = models.JSONField()
    workflow_snapshot = models.JSONField()
    outcome = models.CharField(max_length=32)
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints = [models.UniqueConstraint(fields=['current','revision'], name='unique_review_revision')]
