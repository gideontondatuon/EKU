import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction

from cashflow.models import CashflowTransaction
from cashflow.services import archive_transactions, save_transaction
from core.models import AuditLog

pytestmark = pytest.mark.django_db


def test_create_decimal_constraints(superuser, tx_data):
    tx = save_transaction(superuser, tx_data, reason="Uji sintetis")
    assert str(tx.netflow) == "1000000"
    assert tx.masked_account == "••••6789"
    assert tx.revisions.count() == 1
    assert tx.fingerprint
    with pytest.raises(IntegrityError), transaction.atomic():
        CashflowTransaction.objects.filter(pk=tx.pk).update(outflow_amount=1)


def test_permission_independent(staff, superuser, tx_data, grant):
    with pytest.raises(PermissionDenied):
        save_transaction(staff, tx_data, reason="Tidak berizin")
    grant(staff, "add_transaction", "soft_delete")
    tx = save_transaction(staff, tx_data, reason="Uji izin")
    archive_transactions(staff, [tx.pk], "Arsip uji")
    with pytest.raises(PermissionDenied):
        archive_transactions(staff, [tx.pk], "Tidak boleh restore", restore=True)
    grant(staff, "restore")
    archive_transactions(staff, [tx.pk], "Pulihkan", restore=True)
    tx.refresh_from_db()
    assert tx.soft_deleted_at is None
    assert tx.revisions.count() == 3


def test_identical_transactions_not_globally_unique(superuser, tx_data):
    a = save_transaction(superuser, tx_data, reason="Kejadian pertama")
    b = save_transaction(superuser, tx_data, reason="Kejadian kedua dikonfirmasi manual")
    assert a.pk != b.pk and a.fingerprint == b.fingerprint


def test_validation_and_stale_update(superuser, tx_data):
    tx = save_transaction(superuser, tx_data, reason="Buat")
    with pytest.raises(ValidationError):
        save_transaction(superuser, tx_data, tx_id=tx.pk, reason="Edit stale", expected_revision=0)
    tx_data["pieces"] = 9
    with pytest.raises(ValidationError):
        save_transaction(superuser, tx_data, reason="Nominal konflik")


def test_bulk_permission_and_atomicity(superuser, staff, grant, tx_data):
    a = save_transaction(superuser, tx_data, reason="A")
    b = save_transaction(superuser, tx_data, reason="B")
    grant(staff, "soft_delete")
    with pytest.raises(PermissionDenied):
        archive_transactions(staff, [a.pk, b.pk], "Bulk tanpa izin", bulk=True)
    grant(staff, "bulk_soft_delete")
    archive_transactions(staff, [a.pk, b.pk], "Bulk sah", bulk=True)
    assert CashflowTransaction.objects.filter(soft_deleted_at__isnull=False).count() == 2


def test_audit_redacts_account(superuser, tx_data):
    save_transaction(superuser, tx_data, reason="Input uji rekening 0000123456789")
    log = AuditLog.objects.first()
    assert "0000123456789" not in str(log.before) + str(log.after) + log.reason
    with pytest.raises(ValidationError):
        log.save()
