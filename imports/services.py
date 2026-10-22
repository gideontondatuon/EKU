"""Private staging, conservative reconciliation, and audited import mutations."""

import hashlib
import json
import uuid
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import PurePosixPath

from django.conf import settings
from django.core import signing
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from accounts.permissions import require_permission
from cashflow.models import CashflowTransaction, TransactionRevision
from cashflow.services import transaction_snapshot, validate_transaction
from core.models import Bank, Denomination, ServiceRegion
from core.services import audit, changed, lock_settings

from .models import DuplicateMatch, ImportBatch, ImportRow, VerificationDecision
from .parser import fingerprint, integer_decimal, parse_workbook, validate_normalized

CORRECTION_FIELDS = {
    "transaction_date",
    "bank_name",
    "bank_code",
    "account",
    "region_code",
    "region_name",
    "region_kind",
    "money_type",
    "transaction_type",
    "denomination_code",
    "denomination_value",
    "source_amount",
    "source_netflow",
    "pieces",
    "inflow_amount",
    "outflow_amount",
}


def _scope(scope, required=False):
    if not scope and not required:
        return {}
    try:
        start, end = date.fromisoformat(scope["start"]), date.fromisoformat(scope["end"])
        regions = scope["region_codes"]
        if (
            start > end
            or not isinstance(regions, list)
            or not regions
            or any(not isinstance(r, str) or not r.strip() for r in regions)
        ):
            raise ValueError
        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "region_codes": sorted(set(regions)),
        }
    except (TypeError, KeyError, ValueError):
        raise ValidationError(
            "Scope lengkap memerlukan start/end YYYY-MM-DD dan daftar region_codes."
        ) from None


def _inside(data, scope):
    return (
        bool(scope)
        and scope["start"] <= data.get("transaction_date", "") <= scope["end"]
        and data.get("region_code") in scope["region_codes"]
    )


def _stats(batch):
    counts = dict(Counter(batch.rows.values_list("status", flat=True)))
    batch.stats = counts
    batch.save(update_fields=["stats"])
    return counts


def _references(batch):
    refs = dict(batch.metadata.get("denomination_references", {}))
    for denomination in Denomination.objects.filter(verified=True):
        refs[denomination.code] = {"value": str(denomination.value)}
    return refs


def _master_eligible(denomination, is_demo):
    return bool(
        denomination
        and denomination.verified
        and (is_demo or "DATA DUMMY" not in denomination.source_note.upper())
    )


def _source_candidates(batch, data):
    return CashflowTransaction.objects.filter(dataset=batch.dataset, is_demo=batch.is_demo)


def _reconcile(row, *, used=None):
    """Exact attributes are evidence, never a globally unique transaction identity."""
    batch, data = row.batch, row.normalized
    used = used if used is not None else set()
    candidates = list(
        _source_candidates(batch, data)
        .filter(fingerprint=row.fingerprint)
        .select_related("source_row__batch")
        .order_by("created_at", "pk")
    )
    for candidate in candidates:
        DuplicateMatch.objects.get_or_create(
            row=row,
            candidate=candidate,
            defaults={
                "evidence": {
                    "exact_fingerprint": True,
                    "soft_deleted": bool(candidate.soft_deleted_at),
                },
                "reason": "Atribut sama; identitas kejadian sumber tidak tersedia.",
            },
        )
    if candidates:
        if batch.full_snapshot_confirmed and _inside(data, batch.scope):
            provenance = [
                c
                for c in candidates
                if c.source_row_id
                and c.source_row.batch.full_snapshot_confirmed
                and _inside(data, c.source_row.batch.scope)
            ]
            remaining = [c for c in provenance if c.pk not in used]
            if remaining:
                target = remaining[0]
                used.add(target.pk)
                row.linked_transaction = target
                return "ALREADY_IMPORTED"
        return "NEEDS_REVIEW"
    # A changed amount/denomination on the same business context needs an explicit selected UUID.
    nearby = (
        _source_candidates(batch, data)
        .exclude(source_row__batch=batch)
        .filter(
            transaction_date=data.get("transaction_date"),
            region__code=data.get("region_code"),
            bank__name__iexact=data.get("bank_name", ""),
            money_type=data.get("money_type", ""),
        )
    )
    if not any(w.get("code") == "numeric_account" for w in data.get("warnings", [])):
        nearby = nearby.filter(
            Q(account=data.get("account", ""))
            | Q(source_row__normalized__warnings__contains=[{"code": "numeric_account"}])
        )
    nearby = nearby[:50]
    has_nearby = False
    for candidate in nearby:
        has_nearby = True
        DuplicateMatch.objects.get_or_create(
            row=row,
            candidate=candidate,
            defaults={
                "evidence": {"same_date_bank_region_account": True},
                "reason": "Konteks sama dengan atribut berbeda; pilih UUID bila merupakan revisi.",
            },
        )
    return "NEEDS_REVIEW" if has_nearby or batch.mode == "UPDATE" else "NEW_VALID"


def stage_import(
    actor, uploaded_file, mode="ADD", scope=None, full_snapshot_confirmed=False, is_demo=False
):
    require_permission(actor, "import_data")
    if mode not in {"ADD", "UPDATE", "REPLACE"}:
        raise ValidationError("Mode import tidak dikenal.")
    if mode == "REPLACE" and not full_snapshot_confirmed:
        raise ValidationError("Penggantian periode memerlukan pernyataan snapshot lengkap.")
    scope = _scope(scope, required=full_snapshot_confirmed or mode == "REPLACE")
    file_bytes = uploaded_file.read(settings.MAX_UPLOAD_BYTES + 1)
    parsed = parse_workbook(
        file_bytes,
        uploaded_file.name,
        production=settings.ENVIRONMENT == "production",
        row_limit=settings.MAX_WORKBOOK_ROWS,
    )
    demo = bool(is_demo or parsed.metadata["is_demo"])
    if settings.ENVIRONMENT == "production" and demo:
        raise ValidationError("Data dummy dilarang di production.")
    saved_path, storage = None, None
    try:
        with transaction.atomic():
            lock_settings()
            existing = ImportBatch.objects.filter(
                checksum=parsed.metadata["checksum"], dataset="SETBAY"
            ).first()
            if existing:
                audit(actor, "IMPORT_IDENTICAL_REUPLOAD", existing)
                return existing
            batch = ImportBatch.objects.create(
                checksum=parsed.metadata["checksum"],
                original_filename=PurePosixPath(str(uploaded_file.name).replace("\\", "/")).name[
                    :255
                ],
                uploaded_by=actor,
                mode=mode,
                scope=scope,
                full_snapshot_confirmed=full_snapshot_confirmed,
                is_demo=demo,
                metadata={
                    **parsed.metadata,
                    "denomination_references": parsed.denomination_references,
                    "region_references": parsed.region_references,
                    "warning_rows": sum(
                        bool(item.normalized.get("warnings")) for item in parsed.rows
                    ),
                },
            )
            batch.source_file.save(f"{uuid.uuid4()}.xlsx", ContentFile(file_bytes), save=False)
            saved_path, storage = batch.source_file.name, batch.source_file.storage
            batch.save(update_fields=["source_file"])
            used, seen = set(), Counter()
            denominations_by_code = {d.code: d for d in Denomination.objects.all()}
            regions_by_code = {r.code: r for r in ServiceRegion.objects.all()}
            for item in parsed.rows:
                status, errors = item.status, list(item.issues)
                if scope and not _inside(item.normalized, scope):
                    status = "INVALID"
                    errors.append(
                        {
                            "code": "outside_scope",
                            "message": "Baris di luar scope yang dikonfirmasi.",
                        }
                    )
                denomination = denominations_by_code.get(item.normalized.get("denomination_code"))
                if status == "NEW_VALID":
                    if denomination is None:
                        denomination = Denomination.objects.create(
                            code=item.normalized["denomination_code"],
                            value=Decimal(item.normalized["denomination_value"]),
                            verified=True,
                            source_note=("DATA DUMMY; " if demo else "")
                            + f"Referensi DENOM; aritmetika tervalidasi; batch {batch.pk}.",
                        )
                        denominations_by_code[denomination.code] = denomination
                        audit(
                            actor,
                            "IMPORT_DENOMINATION_CREATE",
                            denomination,
                            after={
                                "batch": str(batch.pk),
                                "code": denomination.code,
                                "value": str(denomination.value),
                                "is_demo": demo,
                            },
                            reason="Mapping DENOM dan nominal × lembar konsisten.",
                        )
                    if not _master_eligible(denomination, demo):
                        status = "NEEDS_REVIEW"
                        errors.append(
                            {
                                "code": "unapproved_master",
                                "message": "Master pecahan operasional memerlukan verifikasi Super Admin.",
                            }
                        )
                    elif denomination.value != Decimal(item.normalized["denomination_value"]):
                        status = "NEEDS_REVIEW"
                        errors.append(
                            {
                                "code": "master_conflict",
                                "message": "Pecahan sumber berbeda dari master terverifikasi.",
                            }
                        )
                region = regions_by_code.get(item.normalized.get("region_code"))
                if (
                    status == "NEW_VALID"
                    and region
                    and (
                        region.name != item.normalized.get("region_name")
                        or region.kind != item.normalized.get("region_kind")
                    )
                ):
                    status = "NEEDS_REVIEW"
                    errors.append(
                        {
                            "code": "region_master_conflict",
                            "message": "Nama wilayah berbeda dari master; periksa mapping wilayah.",
                        }
                    )
                row = ImportRow.objects.create(
                    batch=batch,
                    sheet_name=item.sheet,
                    source_row_number=item.row_number,
                    raw=item.raw,
                    normalized=item.normalized,
                    fingerprint=item.fingerprint,
                    status=status,
                    validation_errors=errors,
                )
                if status == "NEW_VALID":
                    row.status = _reconcile(row, used=used)
                    if row.status == "NEW_VALID" and seen[row.fingerprint]:
                        row.status = "NEEDS_REVIEW"
                        row.validation_errors.append(
                            {
                                "code": "repeated_occurrence",
                                "message": "Atribut sama muncul beberapa kali; konfirmasi kejadian tambahan.",
                            }
                        )
                    seen[row.fingerprint] += 1
                    row.save(update_fields=["status", "linked_transaction", "validation_errors"])
            _stats(batch)
            audit(
                actor,
                "IMPORT_STAGED",
                batch,
                after={"mode": mode, "scope": scope, "stats": batch.stats, "is_demo": demo},
            )
            return batch
    except Exception:
        if saved_path and storage:
            storage.delete(saved_path)
        raise


def _create_or_update(actor, row, target=None, reason="Import baris tervalidasi"):
    data = row.normalized
    denomination = Denomination.objects.filter(
        code=data["denomination_code"], verified=True
    ).first()
    if not _master_eligible(denomination, row.batch.is_demo) or denomination.value != Decimal(
        data["denomination_value"]
    ):
        raise ValidationError("Pecahan harus sesuai master yang sudah diverifikasi.")
    # Source provides a name, not an official bank code; stable local identifier is explicit.
    bank_code = (
        data.get("bank_code")
        or "SRC-" + hashlib.sha256(data["bank_name"].casefold().encode()).hexdigest()[:20]
    )
    bank, _ = Bank.objects.get_or_create(code=bank_code, defaults={"name": data["bank_name"]})
    if bank.name.casefold() != data["bank_name"].casefold():
        raise ValidationError("Kode bank dan nama berbeda dari master.")
    region, _ = ServiceRegion.objects.get_or_create(
        code=data["region_code"],
        defaults={
            "name": data["region_name"],
            "kind": data["region_kind"],
        },
    )
    if region.name != data["region_name"] or region.kind != data["region_kind"]:
        raise ValidationError(
            "Wilayah berbeda dari master; koreksi/verifikasi mapping terlebih dahulu."
        )
    tx = target or CashflowTransaction(
        created_by=actor, updated_by=actor, dataset=row.batch.dataset
    )
    before = transaction_snapshot(tx) if target else {}
    if target and (
        target.soft_deleted_at
        or target.is_demo != row.batch.is_demo
        or target.dataset != row.batch.dataset
    ):
        raise ValidationError(
            "Target harus aktif, dataset dan klasifikasi demo harus sama; restore memakai izin terpisah."
        )
    for key in ("transaction_date", "account", "money_type", "transaction_type"):
        setattr(tx, key, data[key])
    tx.bank, tx.region, tx.denomination = bank, region, denomination
    tx.inflow_amount, tx.outflow_amount = (
        Decimal(data["inflow_amount"]),
        Decimal(data["outflow_amount"]),
    )
    tx.pieces = int(data["pieces"])
    tx.fingerprint, tx.source_row = fingerprint(data), row
    tx.is_demo, tx.status, tx.updated_by = row.batch.is_demo, "VALID", actor
    tx.provenance = {
        "batch": str(row.batch_id),
        "sheet": row.sheet_name,
        "row": row.source_row_number,
        "schema_version": row.batch.metadata.get("schema_version"),
        "normalization_notes": data.get("normalization_notes", []),
        "warnings": data.get("warnings", []),
    }
    if target:
        tx.revision_number += 1
    validate_transaction(tx)
    tx.save()
    TransactionRevision.objects.create(
        transaction=tx, actor=actor, before=before, after=transaction_snapshot(tx), reason=reason
    )
    audit(
        actor,
        "IMPORT_TRANSACTION_UPDATE" if target else "IMPORT_TRANSACTION_CREATE",
        tx,
        before=before,
        after=transaction_snapshot(tx),
        reason=reason,
    )
    row.linked_transaction, row.status = tx, "IMPORTED"
    row.save(update_fields=["linked_transaction", "status"])
    return tx


@transaction.atomic
def commit_batch(actor, batch_id):
    require_permission(actor, "import_data")
    lock_settings()
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    if batch.mode == "REPLACE":
        raise ValidationError("Gunakan pratinjau dan konfirmasi penggantian periode.")
    count, used = 0, set()
    for row in batch.rows.select_for_update().filter(status="NEW_VALID"):
        row.status = _reconcile(row, used=used)
        if row.status == "NEW_VALID":
            _create_or_update(actor, row)
            count += 1
        else:
            row.save(update_fields=["status", "linked_transaction"])
    _stats(batch)
    pending = any(batch.stats.get(key) for key in ("NEEDS_REVIEW", "INVALID"))
    batch.status = "PARTIAL" if pending else "COMMITTED"
    batch.committed_at = timezone.now()
    batch.save(update_fields=["status", "committed_at"])
    audit(actor, "IMPORT_COMMIT", batch, after={"created": count, "stats": batch.stats})
    if count:
        changed(actor)
    return batch


def _validate_corrections(row, corrections):
    corrections = corrections or {}
    if set(corrections) - CORRECTION_FIELDS:
        raise ValidationError("Kolom koreksi tidak diizinkan.")
    data = {**row.normalized, **{k: str(v).strip() for k, v in corrections.items()}}
    if "transaction_type" in data:
        data["transaction_type"] = data["transaction_type"].upper()
    status, issues = validate_normalized(data, _references(row.batch))
    master = Denomination.objects.filter(code=data.get("denomination_code"), verified=True).first()
    if not _master_eligible(master, row.batch.is_demo) or str(master.value) != data.get(
        "denomination_value"
    ):
        issues.append(
            {
                "code": "unapproved_master",
                "message": "Pilih pecahan terverifikasi beserta nilai yang benar.",
            }
        )
    try:
        if Decimal(integer_decimal(data.get("source_netflow"))) != Decimal(
            integer_decimal(data.get("inflow_amount"))
        ) - Decimal(integer_decimal(data.get("outflow_amount"))):
            issues.append(
                {
                    "code": "netflow_conflict",
                    "message": "Koreksi netflow sumber diperlukan secara eksplisit.",
                }
            )
    except ValueError:
        issues.append(
            {
                "code": "invalid_netflow",
                "message": "Koreksi nominal/netflow harus angka Rupiah utuh.",
            }
        )
    for issue in row.validation_errors:
        if (
            issue["code"] in {"numeric_account", "numeric_account_precision"}
            and "account" not in corrections
        ):
            issues.append(issue)
        if issue["code"] == "numeric_region" and "region_code" not in corrections:
            issues.append(issue)
    if row.batch.scope and not _inside(data, row.batch.scope):
        issues.append({"code": "outside_scope", "message": "Koreksi berada di luar scope batch."})
    if status == "INVALID" or issues:
        raise ValidationError([issue["message"] for issue in issues])
    return data


@transaction.atomic
def decide_row(actor, row_id, decision, reason, target_id=None, corrections=None):
    require_permission(actor, "verify_ambiguous")
    if not reason.strip():
        raise ValidationError("Alasan verifikasi wajib diisi.")
    if decision not in {"SKIP_AS_EXISTING", "CREATE_NEW", "UPDATE_SELECTED_EXISTING", "DEFER"}:
        raise ValidationError("Keputusan tidak dikenal.")
    lock_settings()
    row = ImportRow.objects.select_for_update().select_related("batch").get(pk=row_id)
    if row.status != "NEEDS_REVIEW":
        raise ValidationError(
            "Hanya baris ambigu yang dapat diverifikasi; baris invalid harus diperbaiki di sumber."
        )
    target = None
    if decision in {"SKIP_AS_EXISTING", "UPDATE_SELECTED_EXISTING"}:
        if not target_id:
            raise ValidationError("UUID transaksi target wajib dipilih secara eksplisit.")
        target = CashflowTransaction.objects.select_for_update().get(pk=target_id)
        if target.dataset != row.batch.dataset or target.is_demo != row.batch.is_demo:
            raise ValidationError("Target berbeda dataset/klasifikasi data.")
        if row.batch.mode == "REPLACE" and not _inside(
            {
                "transaction_date": target.transaction_date.isoformat(),
                "region_code": target.region.code,
            },
            row.batch.scope,
        ):
            raise ValidationError("Target berada di luar scope penggantian.")
    changed_data = False
    if decision == "DEFER":
        pass
    elif decision == "SKIP_AS_EXISTING":
        row.status, row.linked_transaction = "ALREADY_IMPORTED", target
    else:
        if decision == "UPDATE_SELECTED_EXISTING":
            require_permission(actor, "edit_transaction")
        row.normalized = _validate_corrections(row, corrections)
        row.fingerprint = fingerprint(row.normalized)
        row.validation_errors = []
        if row.batch.mode == "REPLACE":
            row.status = "READY_UPDATE" if target else "NEW_VALID"
            row.linked_transaction = target
            row.normalized["explicit_create_confirmed"] = not bool(target)
        else:
            _create_or_update(actor, row, target=target, reason=reason)
            changed_data = True
    row.save(
        update_fields=[
            "status",
            "linked_transaction",
            "normalized",
            "fingerprint",
            "validation_errors",
        ]
    )
    VerificationDecision.objects.create(
        row=row,
        decision=decision,
        reason=reason,
        actor=actor,
        target=target,
        corrections=corrections or {},
    )
    audit(
        actor,
        "IMPORT_VERIFY",
        row,
        after={
            "decision": decision,
            "target": str(target_id or ""),
            "corrections": corrections or {},
        },
        reason=reason,
    )
    _stats(row.batch)
    if row.batch.committed_at and row.batch.mode != "REPLACE":
        row.batch.status = (
            "PARTIAL"
            if any(row.batch.stats.get(key) for key in ("NEEDS_REVIEW", "INVALID", "NEW_VALID"))
            else "COMMITTED"
        )
        row.batch.save(update_fields=["status"])
    if changed_data:
        changed(actor)
    return row


def _replace_plan(batch, revision):
    if batch.mode != "REPLACE" or not batch.full_snapshot_confirmed:
        raise ValidationError("Batch bukan snapshot lengkap yang dikonfirmasi.")
    scope = _scope(batch.scope, required=True)
    rows = list(batch.rows.select_related("linked_transaction"))
    if any(row.status not in {"NEW_VALID", "ALREADY_IMPORTED", "READY_UPDATE"} for row in rows):
        raise ValidationError(
            "Selesaikan seluruh baris ambigu/invalid sebelum penggantian periode."
        )
    existing = list(
        CashflowTransaction.objects.filter(
            dataset=batch.dataset,
            is_demo=batch.is_demo,
            soft_deleted_at__isnull=True,
            transaction_date__range=(scope["start"], scope["end"]),
            region__code__in=scope["region_codes"],
        )
    )
    ids = {tx.pk for tx in existing}
    linked = [row.linked_transaction_id for row in rows if row.linked_transaction_id]
    if len(linked) != len(set(linked)):
        raise ValidationError("Satu transaksi target tidak boleh mewakili dua occurrence snapshot.")
    if any(pk not in ids for pk in linked):
        raise ValidationError(
            "Target snapshot sudah diarsipkan atau berada di luar scope; tidak dipulihkan otomatis."
        )
    remove = [tx for tx in existing if tx.pk not in set(linked)]
    before_in = sum((tx.inflow_amount for tx in existing), Decimal(0))
    before_out = sum((tx.outflow_amount for tx in existing), Decimal(0))
    after_in = sum(
        (
            row.linked_transaction.inflow_amount
            if row.status == "ALREADY_IMPORTED"
            else Decimal(row.normalized["inflow_amount"])
            for row in rows
        ),
        Decimal(0),
    )
    after_out = sum(
        (
            row.linked_transaction.outflow_amount
            if row.status == "ALREADY_IMPORTED"
            else Decimal(row.normalized["outflow_amount"])
            for row in rows
        ),
        Decimal(0),
    )
    plan = {
        "batch_id": str(batch.pk),
        "revision": revision,
        "scope": scope,
        "add": [str(row.pk) for row in rows if row.status == "NEW_VALID"],
        "update": [
            {
                "row": str(row.pk),
                "transaction": str(row.linked_transaction_id),
                "before": transaction_snapshot(row.linked_transaction),
                "after": {
                    k: v
                    for k, v in row.normalized.items()
                    if k not in {"account", "normalization_notes"}
                },
            }
            for row in rows
            if row.status == "READY_UPDATE"
        ],
        "deactivate": [str(tx.pk) for tx in remove],
        "before": {
            "inflow": str(before_in),
            "outflow": str(before_out),
            "netflow": str(before_in - before_out),
            "count": len(existing),
        },
        "after": {
            "inflow": str(after_in),
            "outflow": str(after_out),
            "netflow": str(after_in - after_out),
            "count": len(rows),
        },
        "row_state": [
            [str(row.pk), row.status, row.fingerprint, str(row.linked_transaction_id)]
            for row in rows
        ],
    }
    plan["digest"] = hashlib.sha256(json.dumps(plan, sort_keys=True).encode()).hexdigest()
    return plan


@transaction.atomic
def preview_replace(actor, batch_id):
    require_permission(actor, "import_data")
    state = lock_settings()
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    plan = _replace_plan(batch, state.data_revision)
    plan["confirmation_token"] = signing.dumps(
        {"batch": str(batch.pk), "digest": plan["digest"], "actor": str(actor.pk)},
        salt="eku.replace",
    )
    return plan


@transaction.atomic
def commit_replace(actor, batch_id, confirmation_token, reason):
    require_permission(actor, "import_data")
    if not reason.strip():
        raise ValidationError("Alasan konfirmasi penggantian wajib diisi.")
    state = lock_settings()
    batch = ImportBatch.objects.select_for_update().get(pk=batch_id)
    plan = _replace_plan(batch, state.data_revision)
    try:
        signed = signing.loads(confirmation_token, salt="eku.replace", max_age=900)
    except signing.BadSignature:
        raise ValidationError("Pratinjau kedaluwarsa/tidak valid. Buat pratinjau baru.") from None
    if signed != {"batch": str(batch.pk), "digest": plan["digest"], "actor": str(actor.pk)}:
        raise ValidationError(
            "Data berubah sejak pratinjau atau konfirmasi berasal dari pengguna lain."
        )
    if plan["deactivate"]:
        require_permission(actor, "bulk_soft_delete")
    if plan["update"]:
        require_permission(actor, "edit_transaction")
    # Logical before-image is persisted in the same transaction before any mutation.
    audit(
        actor,
        "IMPORT_REPLACE_BEFORE",
        batch,
        after={
            "plan": plan,
            "transactions": [
                {"id": str(tx.pk), **transaction_snapshot(tx)}
                for tx in CashflowTransaction.objects.filter(pk__in=plan["deactivate"])
            ],
        },
        reason=reason,
    )
    for row in batch.rows.select_for_update().filter(status__in=["NEW_VALID", "READY_UPDATE"]):
        _create_or_update(
            actor,
            row,
            target=row.linked_transaction if row.status == "READY_UPDATE" else None,
            reason=reason,
        )
    for tx in CashflowTransaction.objects.select_for_update().filter(pk__in=plan["deactivate"]):
        before = transaction_snapshot(tx)
        tx.soft_deleted_at, tx.soft_deleted_by, tx.deletion_reason = timezone.now(), actor, reason
        tx.updated_by = actor
        tx.revision_number += 1
        tx.save()
        TransactionRevision.objects.create(
            transaction=tx,
            actor=actor,
            before=before,
            after=transaction_snapshot(tx),
            reason=reason,
        )
        audit(
            actor,
            "IMPORT_REPLACE_ARCHIVE",
            tx,
            before=before,
            after=transaction_snapshot(tx),
            reason=reason,
        )
    batch.status, batch.committed_at = "COMMITTED", timezone.now()
    batch.save(update_fields=["status", "committed_at"])
    _stats(batch)
    changed(actor)
    audit(actor, "IMPORT_REPLACE_COMMIT", batch, after={"stats": batch.stats}, reason=reason)
    return batch


@transaction.atomic
def discard_review_rows(actor, row_ids):
    """Remove pending rows from the queue without creating transactions."""
    require_permission(actor, "verify_ambiguous")
    lock_settings()
    ids = set(row_ids)
    if not ids or len(ids) > 30:
        raise ValidationError("Pilih 1–30 baris pada halaman ini.")
    try:
        rows = list(
            ImportRow.objects.select_for_update().filter(pk__in=ids).select_related("batch")
        )
    except (ValueError, ValidationError):
        raise ValidationError("Pilihan baris tidak valid.") from None
    if len(rows) != len(ids) or any(
        r.status != "NEEDS_REVIEW" or r.batch.mode == "REPLACE" for r in rows
    ):
        raise ValidationError(
            "Pilihan berubah atau berasal dari snapshot pengganti. Tinjau ulang baris."
        )
    for row in rows:
        row.status = "SKIPPED"
        row.save(update_fields=["status"])
        VerificationDecision.objects.create(
            row=row,
            actor=actor,
            decision="DISCARD",
            reason="Dihapus dari antrean verifikasi oleh operator.",
        )
        audit(actor, "IMPORT_ROW_DISCARD", row, reason="Dihapus dari antrean verifikasi.")
    for batch in {r.batch for r in rows}:
        _stats(batch)
    return len(rows)


def smart_import(actor, uploaded_file, **options):
    """Stage once, then commit safe additions; period replacement keeps its preview."""
    batch = stage_import(actor, uploaded_file, **options)
    if batch.mode != "REPLACE":
        # Otomatisasi: baris yang hanya memiliki isu presisi rekening langsung disahkan sebagai NEW_VALID
        for row in batch.rows.filter(status="NEEDS_REVIEW"):
            codes = {e.get("code") for e in row.validation_errors}
            if codes <= {"numeric_account", "numeric_account_precision"}:
                row.normalized = _validate_corrections(
                    row, {"account": row.normalized.get("account", "")}
                )
                row.fingerprint = fingerprint(row.normalized)
                row.validation_errors = []
                row.status = "NEW_VALID"
                row.save(update_fields=["status", "normalized", "fingerprint", "validation_errors"])
        if batch.rows.filter(status="NEW_VALID").exists():
            batch = commit_batch(actor, batch.pk)
    return batch


def import_summary(batch):
    counts = batch.stats
    return {
        "total": batch.rows.count(),
        "saved": counts.get("IMPORTED", 0),
        "existing": counts.get("ALREADY_IMPORTED", 0),
        "warnings": batch.rows.filter(normalized__warnings__0__isnull=False).count(),
        "review": counts.get("NEEDS_REVIEW", 0),
        "failed": counts.get("INVALID", 0),
    }
