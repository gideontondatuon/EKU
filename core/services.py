import re
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from django.db import transaction

from .models import AuditLog, SystemSettings


def sanitize(value, key=""):
    if any(s in key.lower() for s in ("account", "password", "secret", "token", "raw")):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): sanitize(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [sanitize(v) for v in value]
    if isinstance(value, (Decimal, UUID, date, datetime)):
        return str(value)
    if isinstance(value, str) and any(
        word in key
        for word in (
            "amount",
            "inflow",
            "outflow",
            "netflow",
            "pieces",
            "denomination",
            "date",
            "count",
        )
    ):
        return value
    if isinstance(value, str):
        return re.sub(r"(?<!\d)\d{7,}(?!\d)", "[ANGKA DISENSOR]", value)
    return value


def audit(actor, action, obj=None, before=None, after=None, reason=""):
    return AuditLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_type=type(obj).__name__ if obj else "System",
        object_id=str(obj.pk) if getattr(obj, "pk", None) is not None else "",
        before=sanitize(before or {}),
        after=sanitize(after or {}),
        reason=sanitize(reason),
    )


def lock_settings():
    if not transaction.get_connection().in_atomic_block:
        raise RuntimeError("lock_settings membutuhkan transaction.atomic().")
    SystemSettings.objects.get_or_create(pk=1)
    return SystemSettings.objects.select_for_update().get(pk=1)


def changed(actor):
    settings = lock_settings()
    settings.data_revision += 1
    settings.save(update_fields=["data_revision"])
    from publications.services import maybe_auto_publish

    maybe_auto_publish(actor, settings)
