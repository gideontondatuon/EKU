import uuid

from django.conf import settings
from django.db import models


class EstimateImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    status = models.CharField(max_length=24, default="UNCONFIGURED")
    schema_version = models.CharField(max_length=80, blank=True)
    mapping = models.JSONField(default=dict)
    approval_reference = models.CharField(max_length=255, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)


class CashflowEstimate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(EstimateImportBatch, on_delete=models.PROTECT)
    period_start = models.DateField()
    period_end = models.DateField()
    region = models.ForeignKey("core.ServiceRegion", on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=20, decimal_places=0)
    status = models.CharField(max_length=24, default="UNCONFIGURED")
    scope = models.JSONField(default=dict)
