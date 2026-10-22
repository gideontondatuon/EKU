import json

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied, ValidationError

from core.data_reset import data_counts, reset_data
from core.models import AuditLog, SystemSettings
from imports.models import ImportBatch, ImportRow, VerificationDecision
from imports.services import commit_batch, discard_review_rows, stage_import
from publications.services import publish
from tests.test_imports import source_rows, upload, workbook_bytes


@pytest.mark.django_db
def test_discard_selected_rows_is_audited_and_cannot_discard_imported(superuser):
    batch = stage_import(superuser, upload(workbook_bytes(source_rows(pieces=9))), is_demo=True)
    row = batch.rows.get()
    assert discard_review_rows(superuser, [str(row.pk)]) == 1
    row.refresh_from_db()
    assert row.status == "SKIPPED"
    assert VerificationDecision.objects.filter(row=row, decision="DISCARD").exists()
    with pytest.raises(ValidationError):
        discard_review_rows(superuser, [str(row.pk)])
    commit_batch(superuser, batch.pk)
    assert row.linked_transaction_id is None


@pytest.mark.django_db
def test_review_permissions_and_human_messages(client, superuser, staff):
    batch = stage_import(superuser, upload(workbook_bytes(source_rows(pieces=9))), is_demo=True)
    row = batch.rows.get()
    client.force_login(staff)
    assert client.post("/admin/review/", {"ids": [str(row.pk)]}).status_code == 403
    assert client.get("/admin/reset-data/").status_code == 403
    client.force_login(superuser)
    page = client.get("/admin/review/")
    assert page.status_code == 200
    assert b"Hapus pilihan" in page.content
    assert b"numeric_account" not in page.content
    assert client.get(f"/admin/review/{row.pk}/").status_code == 200
    assert client.get("/admin/reset-data/").status_code == 200


@pytest.mark.django_db
def test_reset_requires_superuser_and_exact_confirmation(superuser, staff):
    with pytest.raises(PermissionDenied):
        reset_data(staff, "KOSONGKAN DATA")
    with pytest.raises(ValidationError):
        reset_data(superuser, "")


@pytest.mark.django_db(transaction=True)
def test_reset_backups_then_clears_dataset_and_allows_same_file(superuser, settings, tmp_path):
    settings.BASE_DIR = tmp_path
    settings.MEDIA_ROOT = tmp_path / "uploads"
    content = workbook_bytes()
    batch = stage_import(superuser, upload(content), is_demo=True)
    commit_batch(superuser, batch.pk)
    publish(superuser, "Publikasi uji sebelum reset", is_demo=True)
    old_revision = SystemSettings.load().data_revision
    counts, backup = reset_data(superuser, "KOSONGKAN DATA")
    assert counts["cashflow.CashflowTransaction"] == 1
    assert not any(data_counts().values())
    assert get_user_model().objects.filter(pk=superuser.pk).exists()
    assert AuditLog.objects.filter(action="DATA_RESET").exists()
    assert SystemSettings.load().current_publication_version_id is None
    assert SystemSettings.load().data_revision == old_revision + 1
    import sys

    if sys.platform != "win32":
        assert backup.stat().st_mode & 0o777 == 0o600
    assert any(x["model"] == "cashflow.cashflowtransaction" for x in json.loads(backup.read_text()))
    assert ImportBatch.objects.count() == ImportRow.objects.count() == 0
    new = stage_import(superuser, upload(content), is_demo=True)
    assert new.pk != batch.pk
    assert new.stats == {"NEW_VALID": 1}


@pytest.mark.django_db
def test_reset_backup_failure_keeps_data(superuser, settings, tmp_path, monkeypatch):
    settings.BASE_DIR = tmp_path
    settings.MEDIA_ROOT = tmp_path / "uploads"
    batch = stage_import(superuser, upload(workbook_bytes()), is_demo=True)

    def fail(*args, **kwargs):
        raise OSError("Backup gagal")

    monkeypatch.setattr("core.data_reset.serializers.serialize", fail)
    with pytest.raises(OSError):
        reset_data(superuser, "KOSONGKAN DATA")
    assert ImportBatch.objects.filter(pk=batch.pk).exists()
    assert not AuditLog.objects.filter(action="DATA_RESET").exists()
