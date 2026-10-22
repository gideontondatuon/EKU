import csv
import io
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core import signing
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q
from django.http import Http404, HttpResponse, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods

from accounts.permissions import operator_required, require_permission
from accounts.views import consume_limit
from cashflow.models import CashflowTransaction
from cashflow.services import archive_transactions, save_transaction, transaction_snapshot
from core.data_reset import data_counts, reset_data
from core.models import AuditLog, Bank, Denomination, ServiceRegion, SystemSettings, default_menus
from core.services import audit, changed, lock_settings
from imports.models import ImportBatch, ImportRow
from imports.parser import WorkbookError
from imports.services import (
    commit_batch,
    commit_replace,
    decide_row,
    discard_review_rows,
    import_summary,
    preview_replace,
    smart_import,
)
from publications.models import PublicationVersion
from publications.services import current_version, publish, rollback

from .analytics import FilterForm, internal_analytics, internal_queryset, public_analytics
from .exports import build_export
from .forms import (
    BankForm,
    DenominationForm,
    ImportForm,
    PublicationForm,
    RegionForm,
    ReviewForm,
    SettingsForm,
    TransactionForm,
    UserAccessForm,
)

TABS = dict(zip(default_menus(), ["Ringkasan", "Tren", "Pecahan", "Pola Musiman", "Estimasi"]))


def error_message(exc):
    return " ".join(exc.messages) if isinstance(exc, ValidationError) else str(exc)


def paging(request, queryset):
    return Paginator(queryset, 30).get_page(request.GET.get("page", 1))


def filter_query(request):
    params = request.GET.copy()
    params.pop("page", None)
    return params.urlencode()


def filtered(request, public=False, version=None):
    form = FilterForm(request.GET, public=public, version=version)
    form.is_valid()
    return form


def public_context(request):
    if any(k in request.GET for k in ("bank", "bank_id", "account", "raw", "transaction_id")):
        raise ValidationError("Filter tersebut tidak tersedia pada dashboard publik.")
    setting = SystemSettings.load()
    tab = request.GET.get("tab", "summary")
    if tab not in setting.public_menus or tab not in TABS:
        raise Http404("Menu tidak tersedia.")
    version = current_version()
    form = filtered(request, public=True, version=version)
    if not form.is_valid():
        raise ValidationError("Filter tanggal atau cakupan tidak valid.")
    return {
        "page_title": "Dashboard Cashflow EKU",
        "settings": setting,
        "version": version,
        "is_demo": bool(version and version.is_demo),
        "public_tabs": [
            {"key": key, "label": TABS[key]}
            for key in setting.public_menus
            if key in TABS and key != "estimates"
        ],
        "active_tab": tab,
        "filter_form": form,
        "filter_query": filter_query(request),
        "analytics": public_analytics(form, version),
        "export_base": "/export/" if version else None,
    }


@require_GET
def public_home(request):
    try:
        context = public_context(request)
    except ValidationError as exc:
        return HttpResponseBadRequest(error_message(exc))
    return render(request, "public.html", context)


@require_GET
def public_api(request):
    if not consume_limit(
        "public-api:" + request.META.get("REMOTE_ADDR", ""), limit=120, seconds=60
    ):
        return JsonResponse({"error": "Batas permintaan tercapai."}, status=429)
    try:
        context = public_context(request)
    except ValidationError as exc:
        return JsonResponse({"error": error_message(exc)}, status=400)
    version = context["version"]
    return JsonResponse(
        {
            "version": str(version.pk) if version else None,
            "is_demo": context["is_demo"],
            "published_at": version.published_at if version else None,
            "data": context["analytics"],
        }
    )


@operator_required()
@require_GET
def admin_home(request):
    form = filtered(request)
    state, version = SystemSettings.load(), current_version()
    data = (
        internal_analytics(form)
        if form.is_valid()
        else {"has_data": False, "notes": ["Periksa filter yang tidak valid."]}
    )
    return render(
        request,
        "admin_dashboard.html",
        {
            "page_title": "Dashboard Admin",
            "settings": state,
            "analytics": data,
            "filter_form": form,
            "filter_query": filter_query(request),
            "version": version,
            "is_demo": CashflowTransaction.objects.filter(
                is_demo=True, soft_deleted_at__isnull=True
            ).exists(),
            "pending_count": ImportRow.objects.filter(
                status__in=["NEEDS_REVIEW", "INVALID"]
            ).count(),
            "stale_publication": state.data_revision > (version.data_revision if version else 0),
            "export_base": "/admin/export/"
            if request.user.has_perm("cashflow.export_internal")
            else None,
        },
    )


@operator_required()
@require_http_methods(["GET", "POST"])
def transactions(request, archive=False):
    form = filtered(request)
    qs = internal_queryset(form) if form.is_valid() else CashflowTransaction.objects.none()
    if archive and form.is_valid():
        # Retain the identical filter constraints, replacing only the active/deleted predicate.
        from .analytics import transaction_queryset

        qs = transaction_queryset(form, archived=True)
    qs = qs.select_related("bank", "region", "denomination")
    if request.GET.get("q"):
        qs = qs.filter(
            Q(bank__name__icontains=request.GET["q"][:100])
            | Q(region__name__icontains=request.GET["q"][:100])
        )
    ordering = {
        "date": "transaction_date",
        "-date": "-transaction_date",
        "inflow": "inflow_amount",
        "-inflow": "-inflow_amount",
    }
    qs = qs.order_by(ordering.get(request.GET.get("sort"), "-transaction_date"), "-created_at")
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action in ("archive_preview", "restore_preview"):
                restore = action == "restore_preview"
                ids = request.POST.getlist("ids")
                if not ids or len(ids) > 500:
                    raise ValidationError("Pilih 1–500 transaksi.")
                items = list(qs.filter(pk__in=ids))
                if len(items) != len(set(ids)):
                    raise ValidationError("Pilihan tidak sesuai daftar/filter aktif.")
                single_perm, bulk_perm = (
                    ("restore", "bulk_restore") if restore else ("soft_delete", "bulk_soft_delete")
                )
                bulk = len(items) > 1 or not request.user.has_perm("cashflow." + single_perm)
                require_permission(request.user, bulk_perm if bulk else single_perm)
                payload = {
                    "actor": request.user.pk,
                    "restore": restore,
                    "bulk": bulk,
                    "revisions": {str(tx.pk): tx.revision_number for tx in items},
                }
                token = signing.dumps(payload, salt="eku.archive")
                total_in = sum((tx.inflow_amount for tx in items), Decimal(0))
                total_out = sum((tx.outflow_amount for tx in items), Decimal(0))
                return render(
                    request,
                    "confirmation.html",
                    {
                        "page_title": "Konfirmasi pemulihan" if restore else "Konfirmasi arsip",
                        "items": items,
                        "confirmation_token": token,
                        "action": "restore" if restore else "archive",
                        "reason": request.POST.get("reason", ""),
                        "back_url": request.path,
                        "diff": f"{len(items)} transaksi; Inflow Rp{total_in:,.0f}; Outflow Rp{total_out:,.0f}; Netflow Rp{total_in - total_out:,.0f}.",
                    },
                )
            if action not in ("archive", "restore") or not request.POST.get("confirm"):
                raise ValidationError("Konfirmasi tindakan diperlukan.")
            payload = signing.loads(
                request.POST.get("confirmation_token", ""), salt="eku.archive", max_age=900
            )
            if payload["actor"] != request.user.pk or payload["restore"] != (action == "restore"):
                raise ValidationError("Konfirmasi tidak sesuai pengguna/tindakan.")
            archive_transactions(
                request.user,
                list(payload["revisions"]),
                request.POST.get("reason", ""),
                restore=payload["restore"],
                bulk=payload["bulk"],
                expected_revisions=payload["revisions"],
            )
            messages.success(
                request, "Transaksi dipulihkan." if payload["restore"] else "Transaksi diarsipkan."
            )
            return redirect(request.path)
        except (ValidationError, signing.BadSignature, ValueError) as exc:
            messages.error(
                request,
                error_message(exc)
                if isinstance(exc, ValidationError)
                else "Pilihan atau token pratinjau tidak valid. Ulangi pratinjau.",
            )
    page = paging(request, qs)
    return render(
        request,
        "transactions.html",
        {
            "page_title": "Arsip / Soft Delete" if archive else "Data Cashflow",
            "rows": page.object_list,
            "page_obj": page,
            "is_archive": archive,
            "filter_form": form,
            "filter_query": filter_query(request),
            "export_base": "/admin/export/"
            if not archive and request.user.has_perm("cashflow.export_internal")
            else None,
        },
    )


@operator_required()
@require_http_methods(["GET", "POST"])
def transaction_form(request, pk=None):
    require_permission(request.user, "edit_transaction" if pk else "add_transaction")
    instance = get_object_or_404(CashflowTransaction, pk=pk) if pk else None
    form = TransactionForm(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            save_transaction(
                request.user,
                form.cleaned_data,
                tx_id=pk,
                reason=form.cleaned_data["reason"],
                expected_revision=form.cleaned_data.get("expected_revision"),
            )
            messages.success(
                request, "Transaksi tersimpan. Publikasi mengikuti pengaturan yang berlaku."
            )
            return redirect("/admin/transactions/")
        except ValidationError as exc:
            form.add_error(None, exc)
    revisions = (
        instance.revisions.select_related("actor").order_by("-created_at")[:20] if instance else []
    )
    return render(
        request,
        "form.html",
        {
            "page_title": "Ubah transaksi" if pk else "Tambah transaksi",
            "form": form,
            "revisions": revisions,
            "is_demo": bool(instance and instance.is_demo),
            "cancel_url": "/admin/transactions/",
        },
    )


@operator_required("import_data")
@require_http_methods(["GET", "POST"])
def imports_home(request):
    form = ImportForm(request.POST if request.method == "POST" else None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            d = form.cleaned_data
            batch = smart_import(
                request.user,
                d["file"],
                mode=d["mode"],
                scope=form.scope(),
                full_snapshot_confirmed=d["full_snapshot_confirmed"],
                is_demo=d["is_demo"],
            )
            return redirect(f"/admin/imports/{batch.pk}/")
        except (ValidationError, WorkbookError) as exc:
            form.add_error(None, error_message(exc))
    page = paging(request, ImportBatch.objects.select_related("uploaded_by"))
    return render(
        request,
        "imports.html",
        {"page_title": "Import Excel", "form": form, "batches": page.object_list, "page_obj": page},
    )


@operator_required("import_data")
@require_http_methods(["GET", "POST"])
def import_detail(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    if request.method == "POST":
        try:
            action = request.POST.get("action")
            if action == "replace_preview":
                plan = preview_replace(request.user, pk)
                token = plan.pop("confirmation_token")
                return render(
                    request,
                    "confirmation.html",
                    {
                        "page_title": "Konfirmasi snapshot periode",
                        "replace_plan": plan,
                        "confirmation_token": token,
                        "action": "replace_commit",
                        "back_url": request.path,
                        "is_demo": batch.is_demo,
                    },
                )
            if not request.POST.get("confirm"):
                raise ValidationError("Konfirmasi hasil pratinjau diperlukan.")
            if action == "commit":
                batch = commit_batch(request.user, pk)
            elif action == "replace_commit":
                batch = commit_replace(
                    request.user,
                    pk,
                    request.POST.get("confirmation_token", ""),
                    request.POST.get("reason", ""),
                )
            else:
                raise ValidationError("Tindakan tidak dikenal.")
            messages.success(
                request, "Hasil import tersimpan. Baris yang perlu verifikasi tetap ditahan."
            )
            return redirect(request.path)
        except (ValidationError, ObjectDoesNotExist) as exc:
            messages.error(
                request,
                error_message(exc)
                if isinstance(exc, ValidationError)
                else "Target tidak ditemukan.",
            )
    page = paging(request, batch.rows.all())
    return render(
        request,
        "import_detail.html",
        {
            "page_title": "Hasil Import Excel",
            "batch": batch,
            "rows": page.object_list,
            "page_obj": page,
            "stats": batch.stats,
            "summary": import_summary(batch),
            "is_demo": batch.is_demo,
            "can_commit": batch.mode == "REPLACE" or bool(batch.stats.get("NEW_VALID")),
            "quality_report_url": f"/admin/imports/{pk}/quality/",
        },
    )


@operator_required("import_data")
@require_GET
def import_quality(request, pk):
    batch = get_object_or_404(ImportBatch, pk=pk)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Sheet", "Baris", "Status", "Kode masalah", "Penjelasan"])
    for row in batch.rows.all():
        for issue in (row.validation_errors + row.normalized.get("warnings", [])) or [
            {"code": "", "message": "Tidak ada konflik validasi format"}
        ]:
            writer.writerow(
                [
                    row.sheet_name,
                    row.source_row_number,
                    row.status,
                    issue.get("code", ""),
                    issue.get("message", ""),
                ]
            )
    response = HttpResponse("\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="laporan-kualitas.csv"'
    audit(request.user, "IMPORT_QUALITY_EXPORT", batch)
    return response


@operator_required("verify_ambiguous")
@require_http_methods(["GET", "POST"])
def review_home(request):
    if request.method == "POST":
        try:
            count = discard_review_rows(request.user, request.POST.getlist("ids"))
            messages.success(
                request, f"{count} baris dihapus dari antrean; tidak dimasukkan sebagai transaksi."
            )
        except ValidationError as exc:
            messages.error(request, error_message(exc))
        return redirect("review")
    page = paging(request, ImportRow.objects.filter(status="NEEDS_REVIEW").select_related("batch"))
    return render(
        request,
        "review.html",
        {"page_title": "Verifikasi Data", "rows": page.object_list, "page_obj": page},
    )


@operator_required("verify_ambiguous")
@require_http_methods(["GET", "POST"])
def review_detail(request, pk):
    row = get_object_or_404(ImportRow.objects.select_related("batch"), pk=pk)
    form = ReviewForm(request.POST if request.method == "POST" else None)
    diff = None
    if request.method == "POST" and form.is_valid():
        try:
            d = form.cleaned_data
            target = (
                get_object_or_404(CashflowTransaction, pk=d["target_id"])
                if d.get("target_id")
                else None
            )
            payload = {
                "actor": request.user.pk,
                "row": str(row.pk),
                "status": row.status,
                "fingerprint": row.fingerprint,
                "decision": d["decision"],
                "target": str(target.pk) if target else None,
                "target_revision": target.revision_number if target else None,
                "corrections": form.corrections(),
                "reason": d["reason"],
            }
            if not d.get("confirmation_token"):
                token = signing.dumps(payload, salt="eku.review")
                data = request.POST.copy()
                data["confirmation_token"] = token
                form = ReviewForm(data)
                form.is_valid()
                before = transaction_snapshot(target) if target else {}
                proposed = {**row.normalized, **form.corrections()}
                proposed["account"] = "[REDACTED]"
                diff = [
                    {
                        "label": label,
                        "before": before.get(key, "—"),
                        "after": proposed.get(key, "—"),
                    }
                    for key, label in (
                        ("transaction_date", "Tanggal"),
                        ("money_type", "Jenis uang"),
                        ("transaction_type", "Jenis transaksi"),
                        ("pieces", "Lembar / keping"),
                        ("inflow_amount", "Inflow (Rp)"),
                        ("outflow_amount", "Outflow (Rp)"),
                    )
                ]
                messages.info(
                    request,
                    "Periksa nilai sebelum/sesudah di bawah, lalu kirim sekali lagi untuk mengonfirmasi keputusan.",
                )
            else:
                signed = signing.loads(d["confirmation_token"], salt="eku.review", max_age=900)
                if signed != payload:
                    raise ValidationError("Data atau pilihan berubah. Buat pratinjau baru.")
                with transaction.atomic():
                    lock_settings()
                    row.refresh_from_db()
                    if row.status != payload["status"] or row.fingerprint != payload["fingerprint"]:
                        raise ValidationError("Status baris berubah. Muat ulang antrean.")
                    if target:
                        target.refresh_from_db()
                        if target.revision_number != payload["target_revision"]:
                            raise ValidationError("Target berubah. Buat pratinjau ulang.")
                    decide_row(
                        request.user,
                        pk,
                        d["decision"],
                        d["reason"],
                        target_id=d.get("target_id"),
                        corrections=form.corrections(),
                    )
                messages.success(request, "Keputusan verifikasi dicatat.")
                return redirect("/admin/review/")
        except (ValidationError, signing.BadSignature) as exc:
            form.add_error(
                None,
                error_message(exc)
                if isinstance(exc, ValidationError)
                else "Token konfirmasi kedaluwarsa/tidak valid.",
            )
    display = dict(row.normalized)
    display["account"] = "••••" + str(display.get("account", ""))[-4:]
    return render(
        request,
        "review_detail.html",
        {
            "page_title": "Verifikasi baris",
            "row": row,
            "form": form,
            "review_fields": [
                (label, display.get(key, ""))
                for key, label in (
                    ("transaction_date", "Tanggal"),
                    ("bank_name", "Bank"),
                    ("account", "Rekening"),
                    ("region_name", "Wilayah"),
                    ("denomination_value", "Pecahan (Rp)"),
                    ("pieces", "Lembar / keping"),
                    ("inflow_amount", "Inflow (Rp)"),
                    ("outflow_amount", "Outflow (Rp)"),
                )
            ],
            "diff": diff,
            "is_demo": row.batch.is_demo,
            "candidates": row.matches.select_related("candidate__region", "candidate__bank"),
        },
    )


@operator_required("publish_manual")
@require_http_methods(["GET", "POST"])
def publications_home(request):
    form = PublicationForm(
        request.POST
        if request.method == "POST" and request.POST.get("action") == "publish"
        else None
    )
    if request.method == "POST":
        try:
            if request.POST.get("action") == "rollback":
                rollback(
                    request.user, request.POST.get("version_id"), request.POST.get("reason", "")
                )
                messages.success(
                    request, "Versi publikasi diaktifkan. Transaksi internal tidak diubah."
                )
                return redirect(request.path)
            if form.is_valid():
                publish(
                    request.user, form.cleaned_data["reason"], is_demo=form.cleaned_data["is_demo"]
                )
                messages.success(request, "Snapshot baru diterbitkan.")
                return redirect(request.path)
        except (ValidationError, ObjectDoesNotExist) as exc:
            form.add_error(
                None,
                error_message(exc)
                if isinstance(exc, ValidationError)
                else "Versi tidak ditemukan.",
            )
    state = SystemSettings.load()
    page = paging(request, PublicationVersion.objects.select_related("published_by"))
    return render(
        request,
        "publications.html",
        {
            "page_title": "Publikasi",
            "form": form,
            "settings": state,
            "version": current_version(),
            "versions": page.object_list,
            "page_obj": page,
            "publication_gate_message": "Publikasi operasional menunggu persetujuan resmi. Evaluasi dummy hanya di development/staging."
            if not state.publication_approval_reference
            else "",
        },
    )


@operator_required(super_only=True)
@require_http_methods(["GET", "POST"])
def settings_view(request):
    state = SystemSettings.load()
    form = SettingsForm(request.POST if request.method == "POST" else None, instance=state)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            state = lock_settings()
            before = {k: getattr(state, k) for k in form.Meta.fields}
            for key in form.Meta.fields:
                setattr(state, key, form.cleaned_data[key])
            state.save(update_fields=form.Meta.fields)
            audit(
                request.user,
                "SETTINGS_CHANGE",
                state,
                before,
                {k: getattr(state, k) for k in form.Meta.fields},
                form.cleaned_data["reason"],
            )
        messages.success(
            request,
            "Pengaturan disimpan. Estimasi otomatis tetap tidak menghitung tanpa metode yang disahkan.",
        )
        return redirect(request.path)
    return render(
        request, "settings.html", {"page_title": "Pengaturan", "form": form, "settings": state}
    )


@operator_required(super_only=True)
@require_http_methods(["GET", "POST"])
def users_view(request, pk=None):
    selected = get_object_or_404(get_user_model(), pk=pk) if pk else None
    form = UserAccessForm(request.POST if request.method == "POST" else None, instance=selected)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                lock_settings()
                user = form.save(commit=False)
                if user.pk == request.user.pk and (
                    not form.cleaned_data["is_active"] or form.cleaned_data["role"] != "SUPER_ADMIN"
                ):
                    raise ValidationError(
                        "Anda tidak dapat menonaktifkan atau menurunkan akses akun sendiri."
                    )
                existing = get_user_model().objects.get(pk=pk) if pk else None
                before = {
                    "role": "SUPER_ADMIN" if existing and existing.is_superuser else "ADMIN_STAFF",
                    "permissions": list(
                        existing.user_permissions.values_list("codename", flat=True)
                    )
                    if existing
                    else [],
                    "is_active": existing.is_active if existing else None,
                }
                user.is_superuser = form.cleaned_data["role"] == "SUPER_ADMIN"
                user.is_staff = True
                if form.cleaned_data.get("password"):
                    user.set_password(form.cleaned_data["password"])
                user.save()
                user.groups.set([Group.objects.get_or_create(name=form.cleaned_data["role"])[0]])
                user.user_permissions.set(
                    Permission.objects.filter(
                        content_type__app_label="cashflow",
                        codename__in=form.cleaned_data["permissions"],
                    )
                )
                audit(
                    request.user,
                    "USER_ACCESS_CHANGE",
                    user,
                    before,
                    {
                        "role": form.cleaned_data["role"],
                        "permissions": form.cleaned_data["permissions"],
                        "is_active": user.is_active,
                    },
                    form.cleaned_data["reason"],
                )
            messages.success(request, "Akun dan izin berhasil disimpan.")
            return redirect("/admin/users/")
        except ValidationError as exc:
            form.add_error(None, exc)
    page = paging(request, get_user_model().objects.order_by("username"))
    return render(
        request,
        "users.html",
        {
            "page_title": "Manajemen Pengguna",
            "users": page.object_list,
            "page_obj": page,
            "form": form,
            "selected_user": selected,
        },
    )


@operator_required(super_only=True)
@require_GET
def audit_view(request):
    qs = AuditLog.objects.select_related("actor")
    if request.GET.get("action"):
        qs = qs.filter(action=request.GET["action"][:80])
    page = paging(request, qs)
    return render(
        request,
        "audit.html",
        {"page_title": "Audit Log", "events": page.object_list, "page_obj": page},
    )


@operator_required(super_only=True)
@require_http_methods(["GET", "POST"])
def masters_view(request):
    kind = request.POST.get("kind", request.GET.get("kind", "region"))
    forms = {"bank": BankForm, "region": RegionForm, "denomination": DenominationForm}
    if kind not in forms:
        raise Http404
    model = forms[kind].Meta.model
    instance = get_object_or_404(model, pk=request.GET["id"]) if request.GET.get("id") else None
    form = forms[kind](request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                lock_settings()
                original = model.objects.get(pk=instance.pk) if instance else None
                before = (
                    {k: str(getattr(original, k)) for k in form.Meta.fields} if original else {}
                )
                item = form.save(commit=False)
                if (
                    original
                    and kind == "denomination"
                    and CashflowTransaction.objects.filter(denomination=original).exists()
                    and (
                        original.value != item.value
                        or original.code != item.code
                        or not item.verified
                    )
                ):
                    raise ValidationError(
                        "Pecahan sudah dipakai transaksi. Buat kode/version master baru agar histori tidak berubah."
                    )
                if original and kind in ("bank", "region") and original.code != item.code:
                    raise ValidationError(
                        "Kode sumber master tidak diubah; buat master baru untuk kode baru."
                    )
                item.save()
                audit(
                    request.user,
                    "MASTER_CHANGE",
                    item,
                    before,
                    {k: str(getattr(item, k)) for k in form.Meta.fields},
                    form.cleaned_data["reason"],
                )
                changed(request.user)
            messages.success(request, "Master data disimpan dengan audit.")
            return redirect(f"/admin/masters/?kind={kind}")
        except ValidationError as exc:
            form.add_error(None, exc)
    return render(
        request,
        "masters.html",
        {
            "page_title": "Master Data",
            "kind": kind,
            "form": form,
            "banks": Bank.objects.order_by("name")[:200],
            "regions": ServiceRegion.objects.order_by("name"),
            "denominations": Denomination.objects.order_by("-value", "code"),
        },
    )


@operator_required()
@require_GET
def estimates_view(request):
    return render(
        request,
        "estimates.html",
        {
            "page_title": "Estimasi Excel",
            "settings": SystemSettings.load(),
            "adapter_status": "UNCONFIGURED",
        },
    )


@require_GET
def export_view(request, fmt, internal=False):
    if fmt not in {"csv", "xlsx", "pdf"}:
        raise Http404
    if internal:
        require_permission(request.user, "export_internal")
        form = filtered(request)
        if not form.is_valid():
            return HttpResponseBadRequest("Filter tidak valid.")
        data = internal_analytics(form)
        version = None
        is_demo = internal_queryset(form).filter(is_demo=True).exists()
    else:
        if not consume_limit(
            "public-export:" + request.META.get("REMOTE_ADDR", ""), limit=20, seconds=60
        ):
            return HttpResponse("Batas ekspor tercapai. Coba lagi nanti.", status=429)
        try:
            context = public_context(request)
        except ValidationError as exc:
            return HttpResponseBadRequest(error_message(exc))
        version = context["version"]
        if not version:
            return HttpResponseBadRequest("Belum ada versi publikasi.")
        data, is_demo, form = context["analytics"], context["is_demo"], context["filter_form"]
    start, end = form.bounds()
    metadata = {
        "period": f"{start or 'awal'} s.d. {end or 'akhir'}",
        "source": "Agregat internal tervalidasi"
        if internal
        else "Snapshot publikasi agregat wilayah",
        "version": str(version.pk) if version else "INTERNAL",
        "exported_at": timezone.localtime().isoformat(),
        "is_demo": is_demo,
    }
    response = build_export(data, fmt, metadata)
    if internal:
        audit(request.user, "INTERNAL_EXPORT", after={"format": fmt, "period": metadata["period"]})
    return response


@operator_required(super_only=True)
@require_http_methods(["GET", "POST"])
def reset_data_view(request):
    if request.method == "POST":
        try:
            reset_data(request.user, request.POST.get("confirmation", ""))
            messages.success(request, "Data berhasil dikosongkan. Silakan impor Excel dari awal.")
            return redirect("imports")
        except ValidationError as exc:
            messages.error(request, error_message(exc))
    return render(
        request, "reset_data.html", {"page_title": "Kosongkan Data", "counts": data_counts()}
    )
