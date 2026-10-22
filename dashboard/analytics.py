"""Analitik exact; jalur public hanya membaca projection versi publikasi."""

import calendar
import re
from datetime import date
from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Count, Max, Min, Sum
from django.db.models.functions import ExtractMonth, ExtractYear, TruncDay, TruncMonth
from django.utils import timezone

from cashflow.models import CashflowTransaction
from core.models import Bank, ServiceRegion
from publications.models import PublishedCashflowAggregate

ZERO = Decimal("0")


class FilterForm(forms.Form):
    period = forms.ChoiceField(
        label="Periode",
        choices=[
            ("all", "Semua Periode"),
            ("daily", "Harian"),
            ("monthly", "Bulanan"),
            ("yearly", "Tahunan"),
            ("custom", "Rentang tanggal"),
        ],
    )
    day = forms.DateField(
        label="Tanggal", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    date = forms.DateField(label="Tanggal", required=False, widget=forms.HiddenInput)
    month = forms.CharField(
        label="Bulan", required=False, widget=forms.TextInput(attrs={"type": "month"})
    )
    year = forms.IntegerField(label="Tahun", min_value=1900, max_value=9998, required=False)
    start = forms.DateField(
        label="Mulai", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    end = forms.DateField(
        label="Sampai", required=False, widget=forms.DateInput(attrs={"type": "date"})
    )
    region = forms.ChoiceField(label="Wilayah", required=False)
    money_type = forms.ChoiceField(label="Jenis uang", required=False)
    denomination = forms.DecimalField(
        label="Pecahan (Rp)", required=False, min_value=1, max_digits=20, decimal_places=0
    )
    bank = forms.ModelChoiceField(
        label="Bank (internal)", queryset=Bank.objects.none(), required=False
    )

    def __init__(self, data=None, *, public=False, version=None, archived=False, **kwargs):
        self.public = public
        self.version = version
        if public:
            base = (
                PublishedCashflowAggregate.objects.filter(version=version)
                if version
                else PublishedCashflowAggregate.objects.none()
            )
            range_data = base.aggregate(first=Min("date"), last=Max("date"))
            regions = list(
                base.order_by("region_name").values_list("region_code", "region_name").distinct()
            )
            dimension_access = bool(version and version.dimensions_included)
            money_types = (
                list(base.order_by("money_type").values_list("money_type", flat=True).distinct())
                if dimension_access
                else []
            )
        else:
            base = CashflowTransaction.objects.filter(
                status="VALID", soft_deleted_at__isnull=not archived
            )
            range_data = base.aggregate(first=Min("transaction_date"), last=Max("transaction_date"))
            regions = list(ServiceRegion.objects.order_by("name").values_list("code", "name"))
            money_types = list(
                base.order_by("money_type").values_list("money_type", flat=True).distinct()
            )
            dimension_access = True
        first = range_data["first"] or timezone.localdate()
        last = range_data["last"] or first
        self.first_date = first
        self.last_date = last
        supplied = data.copy() if data is not None else {}
        defaults = {
            "period": "all" if public else "custom",
            "day": supplied.get("date") or last.isoformat(),
            "month": last.strftime("%Y-%m"),
            "year": last.year,
            "start": first.isoformat(),
            "end": last.isoformat(),
        }
        for key, value in defaults.items():
            if key not in supplied:
                supplied[key] = value
        super().__init__(supplied, **kwargs)
        self.fields["region"].choices = [("", "Semua wilayah")] + regions
        self.fields["money_type"].choices = [("", "Semua jenis uang")] + [
            (value, value) for value in money_types if value
        ]
        if public:
            self.fields.pop("bank")
        else:
            self.fields["bank"].queryset = Bank.objects.order_by("name")
        if not dimension_access:
            self.fields.pop("money_type")
            self.fields.pop("denomination")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")

    def clean(self):
        cleaned = super().clean()
        if self.public:
            if any(self.data.get(key) for key in ("bank", "account", "bank_account")):
                raise ValidationError("Filter identitas internal tidak tersedia untuk public.")
            if not (self.version and self.version.dimensions_included) and any(
                self.data.get(key) for key in ("money_type", "denomination")
            ):
                raise ValidationError(
                    "Rincian pecahan/jenis uang belum termasuk dalam versi publikasi ini."
                )
        period = cleaned.get("period")
        try:
            if period == "all":
                start, end = self.first_date, self.last_date
            elif period == "daily":
                start = end = cleaned.get("day") or cleaned.get("date")
            elif period == "monthly":
                value = cleaned.get("month", "")
                if not re.fullmatch(r"\d{4}-\d{2}", value):
                    raise ValueError("Bulan harus memakai format YYYY-MM.")
                year, month = map(int, value.split("-"))
                start = date(year, month, 1)
                end = date(year, month, calendar.monthrange(year, month)[1])
            elif period == "yearly":
                year = cleaned.get("year")
                if not year:
                    raise ValueError("Tahun harus diisi.")
                start, end = date(year, 1, 1), date(year, 12, 31)
            else:
                start, end = cleaned.get("start"), cleaned.get("end")
            if not start or not end:
                raise ValueError("Lengkapi tanggal periode yang dipilih.")
            if start > end:
                raise ValueError("Tanggal mulai tidak boleh melebihi tanggal akhir.")
            if start.year < 1900 or end.year > 9998:
                raise ValueError("Tahun periode harus antara 1900 dan 9998.")
            if (end - start).days > 36600:
                raise ValueError("Rentang filter maksimal 100 tahun.")
            cleaned["bounds"] = (start, end)
        except (ValueError, TypeError) as exc:
            raise ValidationError(str(exc)) from exc
        return cleaned

    def bounds(self):
        if not self.is_valid():
            raise ValidationError("Filter tidak valid; query tidak dijalankan.")
        return self.cleaned_data["bounds"]


def _internal_base(form, *, archived=False):
    form.bounds()
    values = form.cleaned_data
    queryset = CashflowTransaction.objects.filter(
        status="VALID", soft_deleted_at__isnull=not archived
    )
    for field, lookup in (
        ("region", "region__code"),
        ("bank", "bank"),
        ("money_type", "money_type"),
        ("denomination", "denomination__value"),
    ):
        if values.get(field):
            queryset = queryset.filter(**{lookup: values[field]})
    return queryset


def internal_queryset(form):
    return transaction_queryset(form)


def transaction_queryset(form, *, archived=False):
    if form.public:
        raise ValidationError("Filter public tidak boleh membaca transaksi internal.")
    start, end = form.bounds()
    return _internal_base(form, archived=archived).filter(transaction_date__range=(start, end))


def _totals(queryset, public=False):
    result = queryset.aggregate(
        inflow=Sum("inflow_amount"),
        outflow=Sum("outflow_amount"),
        count=Sum("transaction_count") if public else Count("pk"),
    )
    result["count"] = result["count"] or 0
    result["netflow"] = result["inflow"] - result["outflow"] if result["count"] else None
    return result


def _shift(value, *, months=0, years=0):
    month_index = value.year * 12 + value.month - 1 + months + years * 12
    year, month = divmod(month_index, 12)
    month += 1
    return date(year, month, min(value.day, calendar.monthrange(year, month)[1]))


def _comparison(queryset, current, start, end, date_field, public, period, *, months=0, years=0):
    previous_start = _shift(start, months=months, years=years)
    previous_end = _shift(end, months=months, years=years)
    # Calendar months/years remain complete calendar units; custom boundaries clamp.
    if period == "monthly":
        previous_end = previous_end.replace(
            day=calendar.monthrange(previous_end.year, previous_end.month)[1]
        )
    previous = _totals(
        queryset.filter(**{f"{date_field}__range": (previous_start, previous_end)}), public
    )
    info = {
        "start": previous_start.isoformat(),
        "end": previous_end.isoformat(),
        "baseline": previous["netflow"],
        "baseline_count": previous["count"],
        "completeness": "Kelengkapan periode belum dikonfirmasi.",
    }
    if not current["count"] or not previous["count"]:
        return "N/A", {**info, "reason": "Data periode saat ini atau pembanding tidak tersedia."}
    if previous["netflow"] == ZERO:
        return "N/A", {**info, "reason": "Baseline netflow nol."}
    percentage = (
        (current["netflow"] - previous["netflow"]) / abs(previous["netflow"]) * 100
    ).quantize(Decimal("0.01"))
    return f"{percentage:+.2f}% (netflow)", {
        **info,
        "percentage": percentage,
        "reason": "Perubahan relatif terhadap nilai absolut baseline netflow.",
    }


def _analytics(form, base, *, public=False, dimensions=True):
    start, end = form.bounds()
    date_field = "date" if public else "transaction_date"
    selected = base.filter(**{f"{date_field}__range": (start, end)})
    totals = _totals(selected, public)
    count = Sum("transaction_count") if public else Count("pk")
    amounts = {"inflow": Sum("inflow_amount"), "outflow": Sum("outflow_amount"), "count": count}
    period = form.cleaned_data["period"]
    truncation = {
        "all": TruncDay if (end - start).days <= 90 else TruncMonth,
        "daily": TruncDay,
        "monthly": TruncDay,
        "yearly": TruncMonth,
        "custom": TruncDay,
    }[period]
    series = []
    for row in (
        selected.order_by()
        .annotate(bucket=truncation(date_field))
        .values("bucket")
        .annotate(**amounts)
        .order_by("bucket")
    ):
        series.append(
            {
                "period": row["bucket"].isoformat(),
                "inflow": row["inflow"],
                "outflow": row["outflow"],
                "netflow": row["inflow"] - row["outflow"],
                "count": row["count"],
            }
        )
    region_field = "region_name" if public else "region__name"
    code_field = "region_code" if public else "region__code"
    regions = []
    for row in (
        selected.order_by()
        .values(region_field, code_field)
        .annotate(**amounts)
        .order_by(region_field)
    ):
        regions.append(
            {
                "region": row[region_field],
                "region_code": row[code_field],
                "inflow": row["inflow"],
                "outflow": row["outflow"],
                "netflow": row["inflow"] - row["outflow"],
                "count": row["count"],
            }
        )
    denominations = []
    if dimensions:
        denomination_field = "denomination_value" if public else "denomination__value"
        for row in (
            selected.order_by()
            .exclude(**{f"{denomination_field}__isnull": True})
            .values(denomination_field)
            .annotate(inflow=Sum("inflow_amount"), outflow=Sum("outflow_amount"))
            .order_by(denomination_field)
        ):
            denominations.append(
                {
                    "denomination": row[denomination_field],
                    "inflow": row["inflow"],
                    "outflow": row["outflow"],
                }
            )
    notes = [
        "Kelengkapan periode belum dikonfirmasi; tanggal terakhir bukan bukti seluruh transaksi telah tercakup.",
        "Tanggal tanpa observasi tidak diisi nol. MoM/YoY membandingkan netflow; baseline nol/tidak ada data ditampilkan N/A.",
    ]
    if not totals["count"]:
        notes.append(
            "Tidak ada observasi pada filter ini. Nilai ringkasan kosong tidak membuktikan arus kas nol."
        )
    if not dimensions:
        notes.append("Rincian pecahan dan jenis uang belum disertakan dalam versi publikasi ini.")
    historical = base.filter(**{f"{date_field}__year__lt": end.year})
    years = (
        historical.order_by()
        .annotate(observation_year=ExtractYear(date_field))
        .values("observation_year")
        .distinct()
        .count()
    )
    seasonality = []
    if years >= 2:
        for row in (
            historical.order_by()
            .annotate(month=ExtractMonth(date_field))
            .values("month")
            .annotate(
                inflow=Sum("inflow_amount"),
                outflow=Sum("outflow_amount"),
                observations=Count(ExtractYear(date_field), distinct=True),
            )
            .order_by("month")
        ):
            seasonality.append(row)
        notes.append(
            "Pola musiman adalah total bulanan deskriptif dari tahun historis sebelum tahun akhir filter; observasi berarti jumlah tahun dengan data, bukan prediksi atau bukti tahun lengkap."
        )
    else:
        notes.append(
            "Pola musiman memerlukan observasi dari sedikitnya dua tahun historis sebelum tahun akhir filter."
        )
    mom, mom_info = _comparison(base, totals, start, end, date_field, public, period, months=-1)
    yoy, yoy_info = _comparison(base, totals, start, end, date_field, public, period, years=-1)
    return {
        "totals": totals,
        "series": series,
        "regions": regions,
        "denominations": denominations,
        "seasonality": seasonality,
        "has_data": bool(totals["count"]),
        "notes": notes,
        "mom": mom,
        "yoy": yoy,
        "comparisons": {"mom": mom_info, "yoy": yoy_info},
        "mom_info": mom_info,
        "yoy_info": yoy_info,
        "start": start,
        "end": end,
        "period": period,
        "period_label": f"{start.isoformat()} – {end.isoformat()}",
    }


def internal_analytics(form):
    if form.public:
        raise ValidationError("Filter public tidak boleh membaca data internal.")
    return _analytics(form, _internal_base(form))


def public_analytics(form, version):
    if not form.public or form.version != version:
        raise ValidationError("Filter public harus terikat pada versi publikasi yang dibaca.")
    form.bounds()
    base = (
        PublishedCashflowAggregate.objects.filter(version=version)
        if version
        else PublishedCashflowAggregate.objects.none()
    )
    values = form.cleaned_data
    for field, lookup in (
        ("region", "region_code"),
        ("money_type", "money_type"),
        ("denomination", "denomination_value"),
    ):
        if values.get(field):
            base = base.filter(**{lookup: values[field]})
    return _analytics(
        form, base, public=True, dimensions=bool(version and version.dimensions_included)
    )
