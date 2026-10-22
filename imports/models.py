import uuid

from django.conf import settings
from django.db import models

from core.models import AppendOnlyModel


class ImportBatch(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    checksum = models.CharField(max_length=64)
    source_file = models.FileField(upload_to="imports/%Y/%m/", max_length=255)
    original_filename = models.CharField(max_length=255)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    dataset = models.CharField(max_length=80, default="SETBAY")
    mode = models.CharField(
        max_length=12,
        default="ADD",
        choices=[
            ("ADD", "Tambah"),
            ("UPDATE", "Perbarui terpilih"),
            ("REPLACE", "Snapshot periode"),
        ],
    )
    scope = models.JSONField(default=dict)
    full_snapshot_confirmed = models.BooleanField(default=False)
    is_demo = models.BooleanField(default=False)
    status = models.CharField(max_length=20, default="STAGED")
    stats = models.JSONField(default=dict)
    metadata = models.JSONField(default=dict)
    error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    committed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["checksum", "dataset"], name="batch_checksum_dataset_unique"
            )
        ]


class ImportRow(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name="rows")
    sheet_name = models.CharField(max_length=80)
    source_row_number = models.PositiveIntegerField()
    raw = models.JSONField(default=dict)
    normalized = models.JSONField(default=dict)
    fingerprint = models.CharField(max_length=64, blank=True, db_index=True)
    status = models.CharField(max_length=24, default="INVALID")
    validation_errors = models.JSONField(default=list)
    linked_transaction = models.ForeignKey(
        "cashflow.CashflowTransaction",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="import_occurrences",
    )

    class Meta:
        ordering = ["sheet_name", "source_row_number"]
        constraints = [
            models.UniqueConstraint(
                fields=["batch", "sheet_name", "source_row_number"], name="import_occurrence_unique"
            )
        ]


class DuplicateMatch(models.Model):
    row = models.ForeignKey(ImportRow, on_delete=models.PROTECT, related_name="matches")
    candidate = models.ForeignKey("cashflow.CashflowTransaction", on_delete=models.PROTECT)
    evidence = models.JSONField(default=dict)
    reason = models.CharField(max_length=255)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["row", "candidate"], name="candidate_unique")
        ]


class VerificationDecision(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    row = models.ForeignKey(ImportRow, on_delete=models.PROTECT, related_name="decisions")
    decision = models.CharField(max_length=30)
    reason = models.TextField()
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    target = models.ForeignKey("cashflow.CashflowTransaction", on_delete=models.PROTECT, null=True)
    corrections = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True)
