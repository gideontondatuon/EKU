import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class Bank(models.Model):
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=255)
    aliases = models.JSONField(default=list, blank=True)

    def __str__(self):
        return self.name


class ServiceRegion(models.Model):
    code = models.CharField(max_length=40, unique=True)
    name = models.CharField(max_length=120)
    kind = models.CharField(max_length=10, choices=[("MANADO", "Manado"), ("SKM", "Kas Titipan")])

    def __str__(self):
        return self.name


class Denomination(models.Model):
    code = models.CharField(max_length=40, unique=True)
    value = models.DecimalField(max_digits=20, decimal_places=0)
    verified = models.BooleanField(default=False)
    source_note = models.CharField(max_length=255, blank=True)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(value__gt=0), name="denom_positive")]

    def __str__(self):
        return f"{self.code} — Rp{self.value:,.0f}"


def default_menus():
    return ["summary", "trend", "denominations", "seasonality", "estimates"]


class SystemSettings(models.Model):
    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)
    publication_mode = models.CharField(
        max_length=12, default="MANUAL", choices=[("MANUAL", "Manual"), ("AUTOMATIC", "Otomatis")]
    )
    current_publication_version = models.ForeignKey(
        "publications.PublicationVersion",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    publication_approval_reference = models.CharField(max_length=255, blank=True)
    public_dimensions_approved = models.BooleanField(default=False)
    automatic_estimation_enabled = models.BooleanField(default=False)
    public_menus = models.JSONField(default=default_menus)
    data_revision = models.PositiveBigIntegerField(default=0)

    class Meta:
        constraints = [models.CheckConstraint(condition=Q(id=1), name="settings_singleton")]

    @classmethod
    def load(cls):
        return cls.objects.get_or_create(pk=1)[0]


class AppendOnlyModel(models.Model):
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Record ini tidak dapat diubah.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Record ini tidak dapat dihapus.")


class AuditLog(AppendOnlyModel):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True)
    action = models.CharField(max_length=80, db_index=True)
    object_type = models.CharField(max_length=60)
    object_id = models.CharField(max_length=80, blank=True)
    before = models.JSONField(default=dict)
    after = models.JSONField(default=dict)
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
