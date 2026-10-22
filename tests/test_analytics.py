from datetime import date
from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from openpyxl import load_workbook

from cashflow.models import CashflowTransaction
from core.models import Bank, Denomination, ServiceRegion
from dashboard.analytics import (
    FilterForm,
    internal_analytics,
    internal_queryset,
    public_analytics,
    transaction_queryset,
)
from dashboard.exports import build_export, safe_spreadsheet_text
from publications.models import PublicationVersion, PublishedCashflowAggregate

pytestmark = pytest.mark.django_db


@pytest.fixture
def analytic_data():
    user = get_user_model().objects.create_user("analytic-operator")
    bank = Bank.objects.create(code="secret-bank", name="BANK_RAHASIA_JANGAN_PUBLIC")
    region = ServiceRegion.objects.create(code="MANADO", name="Manado", kind="MANADO")
    denomination = Denomination.objects.create(code="KTEST", value=100000, verified=True)

    def transaction(day, inflow=0, outflow=0, **changes):
        values = {
            "transaction_date": date.fromisoformat(day),
            "bank": bank,
            "region": region,
            "denomination": denomination,
            "money_type": "ULE",
            "transaction_type": "DEPOSIT" if inflow else "WITHDRAWAL",
            "inflow_amount": Decimal(str(inflow)),
            "outflow_amount": Decimal(str(outflow)),
            "pieces": 1,
            "fingerprint": "a" * 64,
            "account": "000012341234",
            "created_by": user,
            "updated_by": user,
        }
        values.update(changes)
        return CashflowTransaction.objects.create(**values)

    def publication(dimensions=False):
        return PublicationVersion.objects.create(
            published_by=user,
            source_cutoff=timezone.now(),
            data_revision=1,
            checksum="a" * 64,
            reason="Fixture sintetis",
            is_demo=True,
            dimensions_included=dimensions,
        )

    return transaction, publication, bank, region


def test_exact_totals_negative_netflow_and_active_only(analytic_data):
    transaction, _, _, _ = analytic_data
    transaction("2025-03-01", inflow="100000000000000001")
    transaction("2025-03-02", outflow="100000000000000003")
    transaction("2025-03-03", inflow=99, status="PENDING_REVIEW")
    transaction("2025-03-04", inflow=99, soft_deleted_at=timezone.now())
    result = internal_analytics(FilterForm({"period": "monthly", "month": "2025-03"}))
    assert result["totals"] == {
        "inflow": Decimal("100000000000000001"),
        "outflow": Decimal("100000000000000003"),
        "netflow": Decimal("-2"),
        "count": 2,
    }
    assert len(result["series"]) == 2
    assert result["regions"][0]["netflow"] == -2
    assert result["denominations"][0]["denomination"] == 100000


def test_missing_is_none_not_zero(analytic_data):
    result = internal_analytics(FilterForm({"start": "2025-01-01", "end": "2025-01-31"}))
    assert result["totals"] == {"inflow": None, "outflow": None, "netflow": None, "count": 0}
    assert not result["has_data"]
    assert result["series"] == []
    assert result["mom"] == result["yoy"] == "N/A"


def test_archive_defaults_include_archived_history_when_no_active_rows(analytic_data):
    transaction, _, _, _ = analytic_data
    record = transaction("2021-09-10", inflow=100, soft_deleted_at=timezone.now())
    form = FilterForm({}, archived=True)
    assert form.bounds() == (date(2021, 9, 10), date(2021, 9, 10))
    assert list(transaction_queryset(form, archived=True)) == [record]
    assert not internal_queryset(form).exists()


def test_no_false_zero_series_and_defaults_use_observed_dates(analytic_data):
    transaction, _, _, _ = analytic_data
    transaction("2021-09-10", inflow=100)
    transaction("2021-09-15", inflow=200)
    form = FilterForm({})
    assert form.bounds() == (date(2021, 9, 10), date(2021, 9, 15))
    result = internal_analytics(form)
    assert [row["period"] for row in result["series"]] == ["2021-09-10", "2021-09-15"]


def test_filters_consistent_date_bank_region_denomination(analytic_data):
    transaction, _, bank, _ = analytic_data
    transaction("2025-01-10", inflow=100)
    transaction("2025-02-10", outflow=200)
    form = FilterForm(
        {
            "period": "daily",
            "date": "2025-01-10",
            "bank": bank.pk,
            "region": "MANADO",
            "money_type": "ULE",
            "denomination": "100000",
        }
    )
    assert internal_queryset(form).count() == 1
    assert internal_analytics(form)["totals"]["inflow"] == 100
    other = FilterForm({"start": "2025-01-01", "end": "2025-12-31", "denomination": "50000"})
    assert not internal_analytics(other)["has_data"]


@pytest.mark.parametrize(
    "data",
    [
        {"start": "2025-02-01", "end": "2025-01-01"},
        {"period": "monthly", "month": "2025-99"},
        {"period": "yearly", "year": "bad"},
        {"start": "not-a-date"},
    ],
)
def test_invalid_filters_never_run_unfiltered_queries(data):
    form = FilterForm(data)
    assert not form.is_valid()
    with pytest.raises(ValidationError):
        internal_queryset(form)


def test_mom_zero_and_missing_baseline_are_na(analytic_data):
    transaction, _, _, _ = analytic_data
    transaction("2025-02-01", inflow=100)
    transaction("2025-02-02", outflow=100)
    transaction("2025-03-01", inflow=200)
    result = internal_analytics(FilterForm({"period": "monthly", "month": "2025-03"}))
    assert result["mom"] == "N/A"
    assert result["mom_info"]["reason"] == "Baseline netflow nol."
    assert result["yoy"] == "N/A"


def test_comparable_month_leap_year_clamp_and_negative_baseline(analytic_data):
    transaction, _, _, _ = analytic_data
    transaction("2024-02-29", outflow=200)
    transaction("2024-03-31", outflow=100)
    result = internal_analytics(FilterForm({"period": "monthly", "month": "2024-03"}))
    assert result["mom"] == "+50.00% (netflow)"
    assert result["mom_info"]["start"] == "2024-02-01"
    assert result["mom_info"]["end"] == "2024-02-29"
    day_result = internal_analytics(FilterForm({"period": "daily", "day": "2024-02-29"}))
    assert day_result["yoy_info"]["start"] == "2023-02-28"


def test_public_only_projection_and_choices_do_not_leak_master(analytic_data):
    transaction, publication, _, _ = analytic_data
    transaction("2025-01-01", inflow=999999)
    ServiceRegion.objects.create(code="SECRET-REGION", name="INTERNAL_SECRET_REGION", kind="SKM")
    version = publication()
    PublishedCashflowAggregate.objects.create(
        version=version,
        date=date(2025, 1, 1),
        region_code="PUBLIC",
        region_name="Wilayah Publik",
        inflow_amount=12,
        outflow_amount=20,
        transaction_count=2,
    )
    form = FilterForm({}, public=True, version=version)
    assert "bank" not in form.fields
    assert "denomination" not in form.fields
    assert "money_type" not in form.fields
    assert list(form.fields["region"].choices) == [
        ("", "Semua wilayah"),
        ("PUBLIC", "Wilayah Publik"),
    ]
    result = public_analytics(form, version)
    assert result["totals"]["netflow"] == -8
    assert result["totals"]["count"] == 2
    assert result["denominations"] == []
    assert "BANK_RAHASIA" not in str(result)
    assert "000012341234" not in str(result)
    with pytest.raises(ValidationError):
        internal_analytics(form)


@pytest.mark.parametrize(
    "parameter,value",
    [("bank", "1"), ("account", "00001"), ("denomination", "100000"), ("money_type", "ULE")],
)
def test_public_rejects_unapproved_filters(parameter, value, analytic_data):
    _, publication, _, _ = analytic_data
    version = publication()
    assert not FilterForm({parameter: value}, public=True, version=version).is_valid()


def test_public_approved_dimensions_are_version_scoped(analytic_data):
    _, publication, _, _ = analytic_data
    version = publication(dimensions=True)
    PublishedCashflowAggregate.objects.create(
        version=version,
        date=date(2025, 1, 1),
        region_code="PUBLIC",
        region_name="Publik",
        denomination_value=100000,
        money_type="ULE",
        inflow_amount=100,
        outflow_amount=0,
        transaction_count=1,
    )
    form = FilterForm({"denomination": "100000", "money_type": "ULE"}, public=True, version=version)
    assert public_analytics(form, version)["denominations"] == [
        {"denomination": Decimal("100000"), "inflow": Decimal("100"), "outflow": Decimal("0")}
    ]
    with pytest.raises(ValidationError):
        public_analytics(form, publication())


def test_seasonality_requires_two_historical_years(analytic_data):
    transaction, _, _, _ = analytic_data
    transaction("2023-01-15", inflow=100)
    transaction("2025-03-01", inflow=300)
    form = FilterForm({})
    assert internal_analytics(form)["seasonality"] == []
    transaction("2024-01-10", inflow=200)
    result = internal_analytics(FilterForm({}))
    assert result["seasonality"] == [
        {"month": 1, "inflow": Decimal("300"), "outflow": Decimal("0"), "observations": 2}
    ]
    assert any("bukan prediksi" in note for note in result["notes"])


@pytest.mark.parametrize(
    "text", ["=SUM(1,2)", "+cmd", "-evil()", "@SUM(A1)", "  =1", "\t@bad", "\n=1"]
)
def test_formula_injection_text_is_neutralized(text):
    assert safe_spreadsheet_text(text).startswith("'")


def test_csv_xlsx_pdf_scope_and_exact_amounts(analytic_data):
    transaction, _, _, region = analytic_data
    region.name = "  =HYPERLINK(evil)"
    region.save()
    transaction("2025-01-01", inflow="100000000000000001")
    analytics = internal_analytics(FilterForm({}))
    metadata = {"source": "Fixture sintetis", "version": "test-version", "is_demo": True}
    csv_response = build_export(analytics, "csv", metadata)
    content = csv_response.content.decode("utf-8-sig")
    assert "'  =HYPERLINK(evil)" in content
    assert "100000000000000001" in content
    assert "DATA DUMMY" in content and "test-version" in content
    assert "BANK_RAHASIA" not in content and "000012341234" not in content
    excel = load_workbook(BytesIO(build_export(analytics, "xlsx", metadata).content))
    cells = [cell for row in excel.active for cell in row]
    assert not any(cell.data_type == "f" for cell in cells)
    assert any(cell.value == "100000000000000001" for cell in cells)
    assert build_export(analytics, "pdf", metadata).content.startswith(b"%PDF")
    assert csv_response["Cache-Control"] == "no-store"
