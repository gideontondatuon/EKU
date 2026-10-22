import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import AppendOnlyModel


class PublicationVersion(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    published_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    published_at = models.DateTimeField(auto_now_add=True)
    source_cutoff = models.DateTimeField()
    data_revision = models.PositiveBigIntegerField()
    sealed = models.BooleanField(default=False)
    checksum = models.CharField(max_length=64)
    parent = models.ForeignKey("self", null=True, on_delete=models.PROTECT)
    is_demo = models.BooleanField(default=False)
    dimensions_included = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict)
    reason = models.TextField()

    class Meta:
        ordering = ["-published_at"]


class PublishedCashflowAggregate(AppendOnlyModel):
    version = models.ForeignKey(
        PublicationVersion, on_delete=models.PROTECT, related_name="aggregates"
    )
    date = models.DateField()
    region_code = models.CharField(max_length=40)
    region_name = models.CharField(max_length=120)
    denomination_value = models.DecimalField(max_digits=20, decimal_places=0, null=True)
    money_type = models.CharField(max_length=80, blank=True)
    inflow_amount = models.DecimalField(max_digits=28, decimal_places=0)
    outflow_amount = models.DecimalField(max_digits=28, decimal_places=0)
    transaction_count = models.PositiveBigIntegerField()

    class Meta:
        indexes = [models.Index(fields=["version", "date", "region_code"])]
        constraints = [
            models.CheckConstraint(
                condition=Q(inflow_amount__gte=0, outflow_amount__gte=0),
                name="published_nonnegative",
            )
        ]
