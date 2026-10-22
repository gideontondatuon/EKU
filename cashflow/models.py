import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q

from core.models import AppendOnlyModel


class CashflowTransaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_date = models.DateField(db_index=True)
    bank = models.ForeignKey("core.Bank", on_delete=models.PROTECT)
    region = models.ForeignKey("core.ServiceRegion", on_delete=models.PROTECT)
    denomination = models.ForeignKey("core.Denomination", on_delete=models.PROTECT)
    money_type = models.CharField(max_length=80)
    transaction_type = models.CharField(
        max_length=12, choices=[("DEPOSIT", "Setoran"), ("WITHDRAWAL", "Penarikan")]
    )
    account = models.CharField(max_length=80, blank=True)
    inflow_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    outflow_amount = models.DecimalField(max_digits=20, decimal_places=0, default=0)
    pieces = models.PositiveBigIntegerField()
    fingerprint = models.CharField(max_length=64, db_index=True)
    dataset = models.CharField(max_length=80, default="SETBAY", db_index=True)
    status = models.CharField(
        max_length=20,
        default="VALID",
        choices=[("VALID", "Valid"), ("PENDING_REVIEW", "Menunggu"), ("INVALID", "Invalid")],
    )
    is_demo = models.BooleanField(default=False)
    source_row = models.ForeignKey(
        "imports.ImportRow",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="created_transactions",
    )
    provenance = models.JSONField(default=dict, blank=True)
    revision_number = models.PositiveIntegerField(default=1)
    soft_deleted_at = models.DateTimeField(null=True, blank=True, db_index=True)
    soft_deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    deletion_reason = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-transaction_date", "-created_at"]
        default_permissions = ()
        permissions = [
            (p, label)
            for p, label in [
                ("import_data", "Import Excel"),
                ("add_transaction", "Tambah transaksi"),
                ("edit_transaction", "Ubah transaksi"),
                ("verify_ambiguous", "Verifikasi ambigu"),
                ("publish_manual", "Publikasi manual"),
                ("soft_delete", "Arsip transaksi"),
                ("restore", "Pulihkan transaksi"),
                ("bulk_soft_delete", "Arsip massal"),
                ("bulk_restore", "Pulihkan massal"),
                ("export_internal", "Ekspor internal"),
            ]
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(inflow_amount__gte=0, outflow_amount__gte=0),
                name="cashflow_nonnegative",
            ),
            models.CheckConstraint(
                condition=(
                    Q(transaction_type="DEPOSIT", inflow_amount__gt=0, outflow_amount=0)
                    | Q(transaction_type="WITHDRAWAL", inflow_amount=0, outflow_amount__gt=0)
                ),
                name="cashflow_direction_consistent",
            ),
            models.CheckConstraint(condition=Q(pieces__gt=0), name="cashflow_pieces_positive"),
        ]
        indexes = [
            models.Index(fields=["region", "transaction_date"]),
            models.Index(fields=["bank", "transaction_date"]),
            models.Index(fields=["dataset", "fingerprint"]),
            models.Index(fields=["status", "soft_deleted_at"]),
        ]

    @property
    def netflow(self):
        return self.inflow_amount - self.outflow_amount

    @property
    def masked_account(self):
        return "••••" + self.account[-4:] if self.account else "—"


class TransactionRevision(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(
        CashflowTransaction, on_delete=models.PROTECT, related_name="revisions"
    )
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
