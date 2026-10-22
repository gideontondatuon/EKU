"""Ekspor hanya DTO agregat; tidak pernah mengambil data transaksi internal."""

import csv
from decimal import Decimal
from io import BytesIO, StringIO
from xml.sax.saxutils import escape

from django.http import HttpResponse
from django.utils import timezone
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def safe_spreadsheet_text(value):
    text = str(value)
    if text.lstrip(" \t\r\n\v\f").startswith(("=", "+", "-", "@")) or text.startswith(
        ("\t", "\r", "\n")
    ):
        return "'" + text
    return text


def _cell(value):
    if isinstance(value, (int, Decimal)):
        return str(value)
    return safe_spreadsheet_text(value if value is not None else "")


def _rows(analytics, metadata):
    source = metadata.get("source", "Agregat cashflow")
    version = metadata.get("version", metadata.get("version_id", "internal"))
    period = metadata.get("period", analytics.get("period_label", "—"))
    exported = metadata.get("exported_at", timezone.localtime().isoformat())
    rows = [
        ["Dashboard Cashflow EKU"],
        ["Periode", period],
        ["Satuan", "Rupiah utuh (Rp)"],
        ["Sumber", source],
        ["Versi", version],
        ["Waktu ekspor (WITA)", exported],
    ]
    if metadata.get("is_demo") or metadata.get("demo"):
        rows.insert(1, ["DATA DUMMY — bukan data operasional"])
    if not analytics["has_data"]:
        rows.append(["Status", "Tidak ada observasi; tidak menyatakan arus kas nol."])
    rows += [[], ["Wilayah", "Inflow (Rp)", "Outflow (Rp)", "Netflow (Rp)", "Transaksi"]]
    for row in analytics["regions"]:
        rows.append([row["region"], row["inflow"], row["outflow"], row["netflow"], row["count"]])
    rows += [[], ["Periode grafik", "Inflow (Rp)", "Outflow (Rp)", "Netflow (Rp)", "Transaksi"]]
    for row in analytics["series"]:
        rows.append([row["period"], row["inflow"], row["outflow"], row["netflow"], row["count"]])
    rows += [[], ["Catatan"]] + [[note] for note in analytics.get("notes", [])]
    return rows


def build_export(analytics, fmt, metadata):
    fmt = fmt.lower()
    rows = _rows(analytics, metadata)
    if fmt == "csv":
        stream = StringIO()
        writer = csv.writer(stream)
        writer.writerows([[_cell(value) for value in row] for row in rows])
        response = HttpResponse(
            "\ufeff" + stream.getvalue(), content_type="text/csv; charset=utf-8"
        )
    elif fmt in {"xlsx", "excel"}:
        fmt = "xlsx"
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "Cashflow agregat"
        for row in rows:
            # Nominal disimpan sebagai teks exact: Excel membulatkan angka >15 digit.
            sheet.append([_cell(value) for value in row])
        sheet.column_dimensions["A"].width = 55
        for column in "BCDE":
            sheet.column_dimensions[column].width = 25
        sheet.freeze_panes = "B10"
        stream = BytesIO()
        workbook.save(stream)
        response = HttpResponse(
            stream.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    elif fmt == "pdf":
        stream = BytesIO()
        document = SimpleDocTemplate(
            stream,
            pagesize=landscape(A4),
            rightMargin=28,
            leftMargin=28,
            topMargin=28,
            bottomMargin=28,
        )
        styles = getSampleStyleSheet()
        story = [Paragraph("Dashboard Cashflow EKU", styles["Title"])]
        metadata_end = next(index for index, row in enumerate(rows) if not row)
        for row in rows[1:metadata_end]:
            story.append(
                Paragraph(escape(" · ".join(str(value) for value in row)), styles["Normal"])
            )
        story.append(Spacer(1, 12))
        for label, key, dimension in (
            ("Ringkasan wilayah", "regions", "region"),
            ("Tren periode", "series", "period"),
        ):
            story.append(Paragraph(label, styles["Heading2"]))
            table_rows = [
                [
                    "Wilayah" if key == "regions" else "Periode",
                    "Inflow (Rp)",
                    "Outflow (Rp)",
                    "Netflow (Rp)",
                    "Transaksi",
                ]
            ]
            for row in analytics[key]:
                table_rows.append(
                    [
                        Paragraph(escape(str(row[dimension])), styles["Normal"]),
                        str(row["inflow"]),
                        str(row["outflow"]),
                        str(row["netflow"]),
                        str(row["count"]),
                    ]
                )
            table = Table(table_rows, colWidths=[205, 145, 145, 145, 90], repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EAF2FC")),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("FONTSIZE", (0, 0), (-1, -1), 8),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
                        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#CBD5E1")),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
                    ]
                )
            )
            story += [table, Spacer(1, 12)]
        for note in analytics.get("notes", []):
            story.append(Paragraph(escape(note), styles["Normal"]))
        document.build(story)
        response = HttpResponse(stream.getvalue(), content_type="application/pdf")
    else:
        raise ValueError("Format ekspor harus CSV, XLSX, atau PDF.")
    response["Content-Disposition"] = f'attachment; filename="cashflow-eku.{fmt}"'
    response["Cache-Control"] = "no-store"
    response["X-Content-Type-Options"] = "nosniff"
    return response
