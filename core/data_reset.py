"""Explicit, backed-up reset of cashflow datasets; users and audit remain intact."""

import os
import uuid
from itertools import chain
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import connection, transaction

from accounts.permissions import is_super
from cashflow.models import CashflowTransaction, TransactionRevision
from core.models import SystemSettings
from core.services import audit, lock_settings
from estimates.models import CashflowEstimate, EstimateImportBatch
from imports.models import DuplicateMatch, ImportBatch, ImportRow, VerificationDecision
from publications.models import PublicationVersion, PublishedCashflowAggregate

DATA_MODELS = (
    ImportBatch,
    ImportRow,
    DuplicateMatch,
    VerificationDecision,
    CashflowTransaction,
    TransactionRevision,
    PublicationVersion,
    PublishedCashflowAggregate,
    EstimateImportBatch,
    CashflowEstimate,
)


def data_counts():
    return {model._meta.label: model.objects.count() for model in DATA_MODELS}


@transaction.atomic
def reset_data(actor, confirmation):
    if not is_super(actor):
        raise PermissionDenied("Hanya Super Admin yang dapat mengosongkan data.")
    if confirmation != "KOSONGKAN DATA":
        raise ValidationError("Ketik KOSONGKAN DATA untuk mengonfirmasi.")
    if connection.vendor != "postgresql":
        raise ValidationError("Reset hanya didukung pada PostgreSQL.")
    current = lock_settings()
    models = (*DATA_MODELS, SystemSettings)
    tables = ", ".join(connection.ops.quote_name(m._meta.db_table) for m in models)
    with connection.cursor() as cursor:
        cursor.execute(f"LOCK TABLE {tables} IN ACCESS EXCLUSIVE MODE")
        counts = data_counts()
        backup_dir = Path(settings.BASE_DIR) / ".private" / "reset-backups"
        backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        backup = backup_dir / f"before-reset-{uuid.uuid4()}.json"
        # Files referenced by ImportBatch stay in private storage for recovery.
        with os.fdopen(os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "w") as stream:
            serializers.serialize(
                "json",
                chain.from_iterable(m.objects.all().iterator() for m in models),
                stream=stream,
            )
            stream.flush()
            os.fsync(stream.fileno())
        # Explicit table list; never CASCADE into accounts or audit tables.
        cursor.execute(f"TRUNCATE TABLE {tables}")
        current.current_publication_version = None
        current.data_revision += 1
        current.save(force_insert=True)
    audit(
        actor,
        "DATA_RESET",
        before=counts,
        after={"backup": backup.name},
        reason="Mulai ulang impor Excel dari data kosong.",
    )
    return counts, backup
