import pytest
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import DatabaseError, transaction

from cashflow.models import CashflowTransaction
from cashflow.services import archive_transactions, save_transaction
from core.models import AuditLog, SystemSettings
from publications.models import PublicationVersion, PublishedCashflowAggregate
from publications.services import current_version, publish, rollback

pytestmark = pytest.mark.django_db


def test_manual_snapshot_and_rollback(superuser, tx_data):
    tx = save_transaction(superuser, tx_data, reason="Awal")
    first = publish(superuser, "Publikasi dummy", is_demo=True)
    assert first.aggregates.get().inflow_amount == 1000000
    archive_transactions(superuser, [tx.pk], "Arsip")
    assert current_version().pk == first.pk
    second = publish(superuser, "Versi kosong setelah arsip", is_demo=True)
    assert second.aggregates.count() == 0
    rollback(superuser, first.pk, "Uji rollback")
    tx.refresh_from_db()
    assert current_version().pk == first.pk and tx.soft_deleted_at is not None


def test_publication_permissions_and_gate(superuser, staff, tx_data, grant):
    tx_data["is_demo"] = False
    save_transaction(superuser, tx_data, reason="Internal uji")
    with pytest.raises(PermissionDenied):
        publish(staff, "Tidak berizin")
    grant(staff, "publish_manual")
    with pytest.raises(ValidationError):
        publish(staff, "Belum ada persetujuan")
    s = SystemSettings.load()
    s.publication_approval_reference = "SYNTHETIC TEST APPROVAL - NOT REAL"
    s.save()
    version = publish(staff, "Uji gate")
    assert version.sealed
    with pytest.raises(PermissionDenied):
        rollback(staff, version.pk, "Tidak boleh rollback")


def test_auto_eligible_only(superuser, tx_data):
    s = SystemSettings.load()
    s.publication_mode = "AUTOMATIC"
    s.save()
    tx = save_transaction(superuser, tx_data, reason="Auto")
    first = current_version()
    assert first.aggregates.get().transaction_count == 1
    CashflowTransaction.objects.filter(pk=tx.pk).update(status="PENDING_REVIEW")
    second = publish(superuser, "Pending tidak boleh muncul", is_demo=True)
    assert second.aggregates.count() == 0


def test_database_immutability(superuser, tx_data):
    tx = save_transaction(superuser, tx_data, reason="Initial")
    version = publish(superuser, "Dummy", is_demo=True)
    operations = [
        lambda: PublicationVersion.objects.filter(pk=version.pk).update(reason="Changed"),
        lambda: PublishedCashflowAggregate.objects.filter(version=version).update(inflow_amount=0),
        lambda: AuditLog.objects.all().update(action="ERASED"),
        lambda: CashflowTransaction.objects.filter(pk=tx.pk).delete(),
        lambda: PublishedCashflowAggregate.objects.create(
            version=version,
            date=tx.transaction_date,
            region_code="X",
            region_name="X",
            inflow_amount=1,
            outflow_amount=0,
            transaction_count=1,
        ),
    ]
    for operation in operations:
        with pytest.raises((DatabaseError, ValidationError)), transaction.atomic():
            operation()


def test_atomic_pointer_on_failed_publish(superuser, tx_data, monkeypatch):
    save_transaction(superuser, tx_data, reason="Initial")
    version = publish(superuser, "Dummy", is_demo=True)

    def fail(*a, **kw):
        raise RuntimeError("Synthetic failure")

    monkeypatch.setattr(PublishedCashflowAggregate.objects, "bulk_create", fail)
    with pytest.raises(RuntimeError):
        publish(superuser, "Fail", is_demo=True)
    assert PublicationVersion.objects.count() == 1
    assert current_version().pk == version.pk
