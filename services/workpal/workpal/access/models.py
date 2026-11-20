from django.conf import settings
from django.db import models

class RegisteredObject(models.Model):
    workspace = models.ForeignKey("identity.Workspace", on_delete=models.PROTECT)
    kind = models.CharField(max_length=100)
    object_id = models.CharField(max_length=255)
    is_source = models.BooleanField(default=False)
    available = models.BooleanField(default=True)
    sources = models.ManyToManyField("self", through="SourceLink", symmetrical=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["kind", "object_id"], name="unique_object_ref")]

class SourceLink(models.Model):
    derived = models.ForeignKey(RegisteredObject, on_delete=models.CASCADE, related_name="source_links")
    source = models.ForeignKey(RegisteredObject, on_delete=models.PROTECT, related_name="derived_links")

    class Meta:
        constraints = [models.UniqueConstraint(fields=["derived", "source"], name="unique_source_link")]

class SourceGrant(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    source = models.ForeignKey(RegisteredObject, on_delete=models.PROTECT)
    read = models.BooleanField(default=False)
    write = models.BooleanField(default=False)
    publish = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["user", "source"], name="unique_source_grant")]

class ContentSnapshot(models.Model):
    ref = models.OneToOneField(RegisteredObject, on_delete=models.PROTECT)
    body = models.BinaryField()
    content_hash = models.CharField(max_length=64)

class Publication(models.Model):
    id = models.UUIDField(primary_key=True, default=__import__('uuid').uuid4, editable=False)
    workspace = models.ForeignKey('identity.Workspace', on_delete=models.PROTECT)
    creator = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='+')
    content = models.ForeignKey(ContentSnapshot, on_delete=models.PROTECT)
    sources = models.ManyToManyField(RegisteredObject)
    body = models.BinaryField()
    content_hash = models.CharField(max_length=64)
    destination = models.CharField(max_length=255)
    revision = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, default='draft')
    approver = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT, related_name='+')
    approved_at = models.DateTimeField(null=True)
    expires_at = models.DateTimeField(null=True)
    approval = models.JSONField(default=dict)
