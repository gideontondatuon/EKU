from decimal import Decimal

from django.conf import settings as django_settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from accounts.permissions import require_permission
from core.services import audit, changed, lock_settings

from .models import CashflowTransaction, TransactionRevision

BUSINESS_FIELDS = (
    "transaction_date",
    "bank",
    "region",
    "denomination",
    "money_type",
    "transaction_type",
    "account",
    "inflow_amount",
    "outflow_amount",
    "pieces",
)


def transaction_fingerprint(data):
    from imports.parser import fingerprint

    return fingerprint(data)


def model_fingerprint(tx):
    return transaction_fingerprint(
        {
            "transaction_date": tx.transaction_date,
            "bank_code": tx.bank.code,
            "bank_name": tx.bank.name,
            "region_code": tx.region.code,
            "region_kind": tx.region.kind,
            "denomination_code": tx.denomination.code,
            "denomination_value": tx.denomination.value,
            "money_type": tx.money_type,
            "transaction_type": tx.transaction_type,
            "account": tx.account,
            "inflow_amount": tx.inflow_amount,
            "outflow_amount": tx.outflow_amount,
            "pieces": tx.pieces,
        }
    )


def transaction_snapshot(tx):
    return {
        f: str(
            getattr(tx, f + "_id") if f in ("bank", "region", "denomination") else getattr(tx, f)
        )
        for f in BUSINESS_FIELDS
        if f != "account"
    } | {
        "account": tx.masked_account,
        "soft_deleted_at": str(tx.soft_deleted_at) if tx.soft_deleted_at else None,
        "revision_number": tx.revision_number,
        "status": tx.status,
        "is_demo": tx.is_demo,
    }


def validate_transaction(tx):
    if django_settings.ENVIRONMENT == "production" and tx.is_demo:
        raise ValidationError("Data dummy dilarang di production.")
    if not tx.is_demo and "DATA DUMMY" in tx.denomination.source_note.upper():
        raise ValidationError("Master pecahan dummy belum mendapat verifikasi operasional.")
    if not tx.denomination.verified:
        raise ValidationError("Mapping pecahan belum diverifikasi.")
    if Decimal(tx.pieces) * tx.denomination.value != tx.inflow_amount + tx.outflow_amount:
        raise ValidationError("Nominal tidak sesuai pecahan × jumlah lembar/keping.")
    tx.full_clean()


@transaction.atomic
def save_transaction(actor, data, tx_id=None, reason="", expected_revision=None):
    require_permission(actor, "edit_transaction" if tx_id else "add_transaction")
    if not reason.strip():
        raise ValidationError("Alasan perubahan wajib diisi.")
    lock_settings()
    if tx_id:
        tx = CashflowTransaction.objects.select_for_update().get(pk=tx_id)
        if tx.soft_deleted_at:
            raise ValidationError("Pulihkan transaksi melalui workflow arsip sebelum mengubah.")
        if expected_revision is None or tx.revision_number != int(expected_revision):
            raise ValidationError(
                "Data berubah sejak formulir dibuka. Muat ulang dan periksa kembali."
            )
        before = transaction_snapshot(tx)
    else:
        tx = CashflowTransaction(created_by=actor, updated_by=actor, dataset="MANUAL")
        before = {}
    for field in BUSINESS_FIELDS:
        if field in data:
            setattr(tx, field, data[field])
    if not tx_id:
        tx.is_demo = bool(data.get("is_demo", False))
    tx.fingerprint = model_fingerprint(tx)
    tx.updated_by = actor
    if tx_id:
        tx.revision_number += 1
    validate_transaction(tx)
    tx.save()
    after = transaction_snapshot(tx)
    TransactionRevision.objects.create(
        transaction=tx, actor=actor, before=before, after=after, reason=reason
    )
    audit(actor, "TRANSACTION_EDIT" if tx_id else "TRANSACTION_ADD", tx, before, after, reason)
    changed(actor)
    return tx


@transaction.atomic
def archive_transactions(actor, ids, reason, restore=False, bulk=False, expected_revisions=None):
    require_permission(
        actor,
        ("bulk_restore" if restore else "bulk_soft_delete")
        if bulk
        else ("restore" if restore else "soft_delete"),
    )
    if not reason.strip() or not ids or (not bulk and len(ids) != 1):
        raise ValidationError("Pilih transaksi dan isi alasan konfirmasi.")
    if len(ids) > 500:
        raise ValidationError("Maksimum 500 transaksi per tindakan.")
    lock_settings()
    rows = list(CashflowTransaction.objects.select_for_update().filter(pk__in=ids))
    if len(rows) != len(set(str(i) for i in ids)):
        raise ValidationError("Sebagian transaksi tidak ditemukan.")
    for tx in rows:
        if (
            expected_revisions is not None
            and expected_revisions.get(str(tx.pk)) != tx.revision_number
        ):
            raise ValidationError("Data berubah sejak pratinjau. Ulangi konfirmasi.")
        if bool(tx.soft_deleted_at) != restore:
            raise ValidationError("Status transaksi sudah berubah. Muat ulang daftar.")
        before = transaction_snapshot(tx)
        if restore:
            validate_transaction(tx)
        tx.soft_deleted_at = None if restore else timezone.now()
        tx.soft_deleted_by = None if restore else actor
        tx.deletion_reason = "" if restore else reason
        tx.updated_by = actor
        tx.revision_number += 1
        tx.save()
        after = transaction_snapshot(tx)
        TransactionRevision.objects.create(
            transaction=tx, actor=actor, before=before, after=after, reason=reason
        )
        audit(
            actor,
            "TRANSACTION_RESTORE" if restore else "TRANSACTION_ARCHIVE",
            tx,
            before,
            after,
            reason,
        )
    changed(actor)
    return rows
