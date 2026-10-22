import hashlib
import json

from django.conf import settings as django_settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Sum
from django.utils import timezone

from accounts.permissions import is_super, require_permission
from cashflow.models import CashflowTransaction
from core.models import SystemSettings
from core.services import audit, lock_settings

from .models import PublicationVersion, PublishedCashflowAggregate


def _build(actor, settings, reason, is_demo=False):
    if is_demo and django_settings.ENVIRONMENT == "production":
        raise ValidationError("Publikasi dummy dilarang di production.")
    if not is_demo and not settings.publication_approval_reference.strip():
        raise ValidationError("Publikasi data operasional menunggu referensi persetujuan resmi.")
    if not reason.strip():
        raise ValidationError("Alasan publikasi wajib diisi.")
    qs = CashflowTransaction.objects.filter(
        status="VALID", soft_deleted_at__isnull=True, is_demo=is_demo
    )
    grouping = ["transaction_date", "region__code", "region__name"]
    dimensions = settings.public_dimensions_approved
    if dimensions:
        grouping += ["denomination__value", "money_type"]
    groups = list(
        qs.order_by(*grouping)
        .values(*grouping)
        .annotate(inflow=Sum("inflow_amount"), outflow=Sum("outflow_amount"), count=Count("pk"))
    )
    projection = [
        {
            "date": str(row["transaction_date"]),
            "region_code": row["region__code"],
            "region_name": row["region__name"],
            "denomination_value": str(row["denomination__value"]) if dimensions else None,
            "money_type": row["money_type"] if dimensions else "",
            "inflow_amount": str(row["inflow"]),
            "outflow_amount": str(row["outflow"]),
            "transaction_count": row["count"],
        }
        for row in groups
    ]
    checksum = hashlib.sha256(
        json.dumps(projection, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()
    version = PublicationVersion.objects.create(
        published_by=actor,
        source_cutoff=timezone.now(),
        data_revision=settings.data_revision,
        parent=settings.current_publication_version,
        is_demo=is_demo,
        dimensions_included=dimensions,
        checksum=checksum,
        reason=reason,
        metadata={
            "source": "DATA DUMMY" if is_demo else "Data tervalidasi",
            "coverage": "Kelengkapan periode belum disahkan; data kosong bukan nol.",
            "approval_reference": settings.publication_approval_reference
            if not is_demo
            else "DEMO LOCAL",
            "aggregate_rows": len(projection),
        },
    )
    PublishedCashflowAggregate.objects.bulk_create(
        [PublishedCashflowAggregate(version=version, **row) for row in projection]
    )
    # Seal is a one-way transition, enforced by the PostgreSQL trigger as well.
    PublicationVersion.objects.filter(pk=version.pk, sealed=False).update(sealed=True)
    version.sealed = True
    old_id = settings.current_publication_version_id
    settings.current_publication_version = version
    settings.save(update_fields=["current_publication_version"])
    audit(
        actor,
        "PUBLICATION_CREATE",
        version,
        {"version": str(old_id) if old_id else None},
        {"version": str(version.pk), "checksum": checksum, "is_demo": is_demo},
        reason,
    )
    return version


@transaction.atomic
def publish(actor, reason, is_demo=False):
    require_permission(actor, "publish_manual")
    return _build(actor, lock_settings(), reason, is_demo=is_demo)


def maybe_auto_publish(actor, settings=None):
    settings = settings or lock_settings()
    if settings.publication_mode != "AUTOMATIC":
        return None
    has_real = CashflowTransaction.objects.filter(is_demo=False).exists()
    if has_real and not settings.publication_approval_reference:
        return None
    is_demo = not has_real
    if is_demo and django_settings.ENVIRONMENT == "production":
        return None
    return _build(
        actor, settings, "Publikasi otomatis setelah perubahan tervalidasi", is_demo=is_demo
    )


@transaction.atomic
def rollback(actor, version_id, reason):
    if not is_super(actor):
        raise PermissionDenied("Rollback hanya untuk Super Admin.")
    if not reason.strip():
        raise ValidationError("Alasan rollback wajib diisi.")
    settings = lock_settings()
    version = PublicationVersion.objects.get(pk=version_id, sealed=True)
    if django_settings.ENVIRONMENT == "production" and version.is_demo:
        raise ValidationError("Snapshot dummy tidak boleh ditampilkan di production.")
    if not version.is_demo and not settings.publication_approval_reference:
        raise ValidationError("Persetujuan publikasi operasional diperlukan.")
    old = settings.current_publication_version_id
    settings.current_publication_version = version
    settings.save(update_fields=["current_publication_version"])
    audit(
        actor,
        "PUBLICATION_ROLLBACK",
        version,
        {"version": str(old)},
        {"version": str(version.pk)},
        reason,
    )
    return version


def current_version():
    setting = (
        SystemSettings.objects.select_related("current_publication_version").filter(pk=1).first()
    )
    if not setting or not setting.current_publication_version_id:
        return None
    version = setting.current_publication_version
    if not version.sealed or (version.is_demo and django_settings.ENVIRONMENT == "production"):
        return None
    if not version.is_demo and not setting.publication_approval_reference:
        return None
    return version
