"""Bounded OOXML reader: retain source values and never evaluate a workbook formula."""

import hashlib
import io
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as XML
from openpyxl.utils.datetime import CALENDAR_MAC_1904, CALENDAR_WINDOWS_1900, from_excel

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
DUMMY_CHECKSUM = "cdf1d28975f46f3df1cd6ad5a04e3ddd0e16da547762bf753ffb171c8fee2954"
SCHEMA_VERSION = "setbay-v2"
MAX_BYTES = 10 * 1024 * 1024
MAX_UNCOMPRESSED = 100 * 1024 * 1024
MAX_ROWS = 50000


class WorkbookError(ValueError):
    """An upload is not a supported, safely readable workbook."""


@dataclass
class ParsedRow:
    sheet: str
    row_number: int
    raw: dict
    normalized: dict
    fingerprint: str = ""
    status: str = "NEW_VALID"
    issues: list = field(default_factory=list)


@dataclass
class ParsedWorkbook:
    metadata: dict
    denomination_references: dict
    region_references: dict
    rows: list


COMMON = {
    "transaction_date": ("COTC_TRAN_DATE",),
    "transaction_type": ("TRANSACTION_TYPE",),
    "money_type": ("MONEY_TYPE",),
    "bank_name": ("BANK_NAME",),
    "account": ("BANK_ACCOUNT",),
    "branch_code": ("COTC_BRN_CODE",),
    "branch_name": ("MBRN_NAME",),
    "denomination_value": ("Denom",),
    "denomination_order": ("Urutan Denom",),
}
ADAPTERS = {
    "SETBAY MANADO": {
        **COMMON,
        "denomination_code": ("COTCP_NOTE_COIN_TYPE", "COTCR_NOTE_COIN_TYPE"),
        "source_amount": ("COTCP_AMOUNT", "COTCR_AMOUNT"),
        "pieces": ("COTCP_PIECES", "COTCR_PIECES"),
        "inflow_amount": ("Inflow",),
        "outflow_amount": ("Outflow",),
        "source_netflow": ("Neflow", "Netflow"),
    },
    "SETBAY KASTIP": {
        **COMMON,
        "denomination_code": ("COTCR_NOTE_COIN_TYPE", "COTCP_NOTE_COIN_TYPE"),
        "source_amount": ("COTCR_AMOUNT", "COTCP_AMOUNT"),
        "pieces": ("COTCR_PIECES", "COTCP_PIECES"),
        "region_code": ("COTC_CLIENT_BRNCODE",),
        "region_label": ("Nama Kastip",),
        "inflow_amount": ("Inflow Kastip", "Inflow"),
        "outflow_amount": ("Outflow Kasti", "Outflow Kastip", "Outflow"),
        "source_netflow": ("Netflow Kastip", "Netflow", "Neflow"),
    },
}


def integer_decimal(value, *, formatted=False):
    """XML numbers retain exact Decimal; Indonesian thousands text is explicit."""
    text = str(value or "").strip()
    if formatted and re.fullmatch(r"[+-]?\d{1,3}(?:\.\d{3})+(?:,0+)?", text):
        text = text.replace(".", "").replace(",", ".")
    elif formatted and re.fullmatch(r"[+-]?\d+,0+", text):
        text = text.replace(",", ".")
    try:
        number = Decimal(text)
    except InvalidOperation as exc:
        raise ValueError("Nilai bukan angka Rupiah/lembar yang valid.") from exc
    if not number.is_finite() or number != number.to_integral_value():
        raise ValueError("Nilai harus bilangan bulat hingga Rupiah utuh.")
    if abs(number) >= Decimal(10) ** 20:
        raise ValueError("Nilai melebihi kapasitas 20 digit.")
    return format(number, "f").split(".")[0]


def denomination_decimal(value, *, formatted=False):
    """SETBAY labels UK (kertas) and UL (logam) retain their source code."""
    text = str(value or "").strip()
    if formatted:
        text = re.sub(r"\s+(?:UK|UL)$", "", text, flags=re.I)
    return integer_decimal(text, formatted=formatted)


def fingerprint(data):
    fields = (
        "transaction_date",
        "bank_name",
        "account",
        "region_code",
        "region_kind",
        "transaction_type",
        "money_type",
        "denomination_code",
        "denomination_value",
        "pieces",
        "inflow_amount",
        "outflow_amount",
    )
    content = {key: str(data.get(key, "")).strip() for key in fields}
    content["bank_name"] = content["bank_name"].casefold()
    content["transaction_type"] = content["transaction_type"].upper()
    for key in ("denomination_value", "pieces", "inflow_amount", "outflow_amount"):
        try:
            content[key] = integer_decimal(content[key])
        except ValueError:
            pass
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def _sheet_rows(archive, path, shared_strings, row_limit):
    root = XML.fromstring(archive.read(path))
    result = []
    for row in root.findall("m:sheetData/m:row", NS):
        row_number = int(row.attrib.get("r", 0))
        if row_number > row_limit + 10 or len(result) > row_limit + 10:
            raise WorkbookError("Jumlah baris workbook melebihi batas.")
        cells = {}
        for cell in row.findall("m:c", NS):
            if len(cells) >= 128:
                raise WorkbookError("Worksheet melebihi batas 128 kolom terisi per baris.")
            address = cell.attrib.get("r", "")
            match = re.fullmatch(r"([A-Z]{1,3})([1-9][0-9]*)", address)
            if not match:
                raise WorkbookError("Alamat sel tidak valid.")
            raw_value = cell.find("m:v", NS)
            value = raw_value.text if raw_value is not None else None
            cell_type = cell.attrib.get("t", "n")
            if cell_type == "s" and value is not None:
                try:
                    index = int(value)
                    if index < 0:
                        raise ValueError
                    value = shared_strings[index]
                except (ValueError, IndexError) as exc:
                    raise WorkbookError("Shared string tidak valid.") from exc
            elif cell_type == "inlineStr":
                value = "".join(cell.itertext())
            formula = cell.find("m:f", NS)
            if value is not None and len(value) > 32767:
                raise WorkbookError("Isi sel melebihi batas teks Excel yang didukung.")
            if value is not None or formula is not None:
                cells[match.group(1)] = {
                    "value": value,
                    "type": cell_type,
                    "formula": None
                    if formula is None
                    else {
                        "text": formula.text or "",
                        "attributes": formula.attrib,
                    },
                }
        if cells:
            result.append((row_number, cells))
    return result


def _cell_value(cells, column):
    return str(cells.get(column, {}).get("value") or "").strip()


def _parse_date(cell, epoch):
    value = str(cell.get("value") or "").strip()
    if cell.get("type") == "n":
        serial = Decimal(value)
        if not serial.is_finite() or serial < 1 or serial > 2958465:
            raise ValueError("Serial tanggal di luar rentang.")
        if serial != serial.to_integral_value():
            raise ValueError("Tanggal transaksi mengandung waktu; perlu normalisasi sumber.")
        if epoch == CALENDAR_WINDOWS_1900 and serial == 60:
            raise ValueError("Tanggal fiktif Excel 1900-02-29 tidak diterima.")
        result = from_excel(int(serial), epoch)
        return result.date().isoformat()
    for pattern in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(value, pattern).date().isoformat()
        except ValueError:
            pass
    raise ValueError("Tanggal harus serial Excel atau YYYY-MM-DD / DD-MM-YYYY / DD/MM/YYYY.")


def validate_normalized(data, denominations=None):
    """Validation shared by parser and explicit review corrections; never infer denomination."""
    issues = []
    invalid = False

    def issue(code, message, severe=False):
        nonlocal invalid
        issues.append({"code": code, "message": message})
        invalid = invalid or severe

    for key in (
        "transaction_date",
        "bank_name",
        "region_code",
        "region_name",
        "money_type",
        "denomination_code",
        "account",
    ):
        if not str(data.get(key, "")).strip():
            issue("missing_" + key, f"Kolom {key} wajib terisi.", True)
    try:
        date.fromisoformat(data.get("transaction_date", ""))
    except ValueError:
        issue("invalid_date", "Tanggal tidak valid.", True)
    nums = {}
    for key in ("denomination_value", "pieces", "source_amount", "inflow_amount", "outflow_amount"):
        try:
            nums[key] = Decimal(integer_decimal(data.get(key)))
            if nums[key] < 0 or (
                key in {"denomination_value", "pieces", "source_amount"} and nums[key] == 0
            ):
                issue("invalid_" + key, f"Nilai {key} di luar rentang.", True)
        except ValueError:
            issue("invalid_" + key, f"Nilai {key} harus bilangan bulat valid.", True)
    direction = data.get("transaction_type")
    if direction not in {"DEPOSIT", "WITHDRAWAL"}:
        issue("unknown_transaction_type", "Jenis transaksi belum memiliki aturan yang disetujui.")
    if len(nums) == 5:
        if nums["denomination_value"] * nums["pieces"] != nums["source_amount"]:
            issue("denomination_amount_conflict", "Pecahan × lembar berbeda dari nominal sumber.")
        expected = (
            (nums["source_amount"], Decimal(0))
            if direction == "DEPOSIT"
            else (Decimal(0), nums["source_amount"])
        )
        if (
            direction in {"DEPOSIT", "WITHDRAWAL"}
            and (nums["inflow_amount"], nums["outflow_amount"]) != expected
        ):
            issue("direction_conflict", "Inflow/outflow berbeda dari jenis dan nominal transaksi.")
        if not (nums["inflow_amount"] > 0) ^ (nums["outflow_amount"] > 0):
            issue("flow_conflict", "Tepat satu inflow atau outflow harus positif.")
    if denominations is not None:
        ref = denominations.get(data.get("denomination_code"))
        if not ref:
            issue("unmapped_denomination", "Kode pecahan belum terdaftar dalam referensi.")
        elif str(ref["value"]) != str(data.get("denomination_value")):
            issue("denomination_reference_conflict", "Nilai pecahan berbeda dari referensi.")
    return ("INVALID" if invalid else "NEEDS_REVIEW" if issues else "NEW_VALID"), issues


def _normalize_row(sheet, row_number, cells, columns, denominations, regions, epoch):
    raw = {
        key: cells.get(column, {"value": None, "type": "missing", "formula": None})
        for key, column in columns.items()
    }
    data = {key: str(cell.get("value") or "").strip() for key, cell in raw.items()}
    data["transaction_type"] = data["transaction_type"].upper()
    notes, issues, warnings = [], [], []
    invalid = False
    for key, cell in raw.items():
        formula = cell.get("formula")
        if cell.get("type") == "e" or (formula is not None and cell.get("value") is None):
            invalid = True
            issues.append(
                {"code": "formula_cache_invalid", "message": f"{key}: cached value kosong/error."}
            )
        if formula and re.search(
            r"\[|https?://|WEBSERVICE\s*\(|HYPERLINK\s*\(|DDE\s*\(|\|", formula["text"], re.I
        ):
            invalid = True
            issues.append(
                {"code": "unsafe_formula", "message": "Formula eksternal tidak diizinkan."}
            )
    try:
        data["transaction_date"] = _parse_date(raw["transaction_date"], epoch)
        for key in (
            "denomination_value",
            "pieces",
            "source_amount",
            "inflow_amount",
            "outflow_amount",
            "source_netflow",
        ):
            parse_number = denomination_decimal if key == "denomination_value" else integer_decimal
            data[key] = parse_number(data[key], formatted=raw[key]["type"] != "n")
        data["branch_code"] = (
            integer_decimal(data["branch_code"])
            if raw["branch_code"]["type"] == "n"
            else data["branch_code"]
        )
    except (ValueError, InvalidOperation, OverflowError) as exc:
        invalid = True
        issues.append({"code": "invalid_format", "message": str(exc)})
    if raw["account"]["type"] == "n":
        try:
            data["account"] = integer_decimal(data["account"])
        except ValueError:
            invalid = True
            issues.append(
                {"code": "invalid_account", "message": "Rekening numeric harus bilangan bulat."}
            )
        if (
            data["account"].isdigit()
            and 0 < len(data["account"]) <= 15
            and int(data["account"]) > 0
        ):
            warnings.append(
                {
                    "code": "numeric_account",
                    "message": "Rekening disimpan sesuai angka Excel; nol di depan tidak direkonstruksi. Periksa sumber bila perlu.",
                }
            )
        else:
            issues.append(
                {
                    "code": "numeric_account_precision",
                    "message": "Rekening numeric berisiko kehilangan presisi; periksa rekening dari sumber teks yang tepercaya.",
                }
            )
    if sheet == "SETBAY MANADO":
        data.update(region_code="MANADO", region_name="Manado KPwBI", region_kind="MANADO")
    else:
        data["region_kind"] = "SKM"
        if raw["region_code"]["type"] == "n":
            try:
                data["region_code"] = integer_decimal(data["region_code"])
            except ValueError:
                invalid = True
                issues.append(
                    {"code": "invalid_region", "message": "Kode Kastip harus bilangan bulat."}
                )
            if data["region_code"] not in regions:
                issues.append(
                    {
                        "code": "numeric_region",
                        "message": "Kode Kastip numeric tidak cocok dengan referensi DENOM; perlu verifikasi.",
                    }
                )
        data["region_name"] = regions.get(data.get("region_code"), "")
        if data.get("region_label") not in {data.get("region_code"), data["region_name"]}:
            issues.append(
                {
                    "code": "region_conflict",
                    "message": "Nama/kode Kastip berbeda dari master referensi.",
                }
            )
    if not invalid:
        inflow, outflow = Decimal(data["inflow_amount"]), Decimal(data["outflow_amount"])
        if outflow < 0:
            if (
                data.get("transaction_type") == "WITHDRAWAL"
                and inflow == 0
                and -outflow == Decimal(data["source_amount"])
            ):
                data["outflow_amount"] = str(-outflow)
                notes.append(
                    {
                        "field": "outflow_amount",
                        "from": str(outflow),
                        "to": str(-outflow),
                        "reason": "Magnitudo domain dari outflow sumber bertanda negatif; Withdrawal dan amount sesuai.",
                    }
                )
            else:
                issues.append(
                    {
                        "code": "negative_outflow_conflict",
                        "message": "Outflow negatif tidak cocok dengan jenis/nominal.",
                    }
                )
        expected_net = Decimal(data["inflow_amount"]) - Decimal(data["outflow_amount"])
        if Decimal(data["source_netflow"]) != expected_net:
            issues.append(
                {
                    "code": "netflow_conflict",
                    "message": "Netflow cached berbeda dari inflow dikurangi magnitudo outflow.",
                }
            )
    status, validation = validate_normalized(data, denominations)
    issues.extend(validation)
    if invalid or status == "INVALID":
        status = "INVALID"
    elif issues:
        status = "NEEDS_REVIEW"
    data["warnings"] = warnings
    data["normalization_notes"] = notes
    raw["_cells"] = cells
    return ParsedRow(sheet, row_number, raw, data, fingerprint(data), status, issues)


def parse_workbook(file_bytes, filename, *, production=False, row_limit=MAX_ROWS):
    if not isinstance(file_bytes, bytes) or len(file_bytes) > MAX_BYTES:
        raise WorkbookError("Ukuran upload melebihi 10 MB.")
    if not str(filename).lower().endswith(".xlsx") or "\x00" in str(filename):
        raise WorkbookError("Hanya file .xlsx yang diterima.")
    checksum = hashlib.sha256(file_bytes).hexdigest()
    if production and checksum == DUMMY_CHECKSUM:
        raise WorkbookError("Workbook DATA DUMMY tidak boleh diimpor pada production.")
    try:
        archive = zipfile.ZipFile(io.BytesIO(file_bytes))
    except (zipfile.BadZipFile, OSError) as exc:
        raise WorkbookError("Konten upload bukan workbook XLSX valid.") from exc
    with archive:
        infos = archive.infolist()
        names = [x.filename for x in infos]
        if (
            len(infos) > 2000
            or len(set(names)) != len(names)
            or sum(x.file_size for x in infos) > MAX_UNCOMPRESSED
        ):
            raise WorkbookError("Arsip workbook melebihi batas atau memiliki nama entry ganda.")
        for entry in infos:
            if (
                entry.flag_bits & 1
                or ".." in entry.filename.split("/")
                or entry.filename.startswith("/")
            ):
                raise WorkbookError("Arsip terenkripsi atau path tidak aman.")
            if (
                entry.file_size > MAX_UNCOMPRESSED
                or entry.file_size / max(1, entry.compress_size) > 1000
            ):
                raise WorkbookError("Rasio kompresi workbook tidak aman.")
            if "vbaproject" in entry.filename.lower() or "externallink" in entry.filename.lower():
                raise WorkbookError("Macro dan referensi eksternal tidak diizinkan.")
        try:
            for entry in infos:
                if entry.filename.endswith(".rels"):
                    rel_root = XML.fromstring(archive.read(entry))
                    if any(r.attrib.get("TargetMode") == "External" for r in rel_root):
                        raise WorkbookError("Relasi eksternal workbook tidak diizinkan.")
            content_types = archive.read("[Content_Types].xml")
            if b"macroEnabled" in content_types:
                raise WorkbookError("Workbook macro tidak diizinkan.")
            workbook = XML.fromstring(archive.read("xl/workbook.xml"))
            rels = XML.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
            paths = {r.attrib["Id"]: r.attrib["Target"] for r in rels}
            properties = workbook.find("m:workbookPr", NS)
            epoch = (
                CALENDAR_MAC_1904
                if properties is not None and properties.get("date1904") in {"1", "true"}
                else CALENDAR_WINDOWS_1900
            )
            shared_strings = []
            if "xl/sharedStrings.xml" in names:
                root = XML.fromstring(archive.read("xl/sharedStrings.xml"))
                shared_strings = ["".join(n.itertext()) for n in root.findall("m:si", NS)]
            sheets = {}
            for sheet in workbook.findall("m:sheets/m:sheet", NS):
                if len(sheets) >= 32:
                    raise WorkbookError("Workbook melebihi batas 32 worksheet.")
                name = sheet.attrib["name"].strip()
                supported_names = {n.casefold(): n for n in (*ADAPTERS, "DENOM", "Tanggal Update")}
                name = supported_names.get(" ".join(name.split()).casefold(), name)
                if name in sheets:
                    raise WorkbookError("Nama sheet duplikat setelah normalisasi.")
                target = paths[sheet.attrib[REL]]
                path = (
                    target.lstrip("/")
                    if target.startswith("/")
                    else posixpath.normpath("xl/" + target)
                )
                if not path.startswith("xl/worksheets/"):
                    raise WorkbookError("Path worksheet tidak didukung.")
                sheets[name] = (
                    _sheet_rows(archive, path, shared_strings, row_limit)
                    if name in supported_names.values()
                    else []
                )
        except WorkbookError:
            raise
        except Exception as exc:
            raise WorkbookError("Struktur XML workbook tidak valid atau tidak didukung.") from exc
    denominations, regions = {}, {}
    reference_rows = sheets.get("DENOM", [])
    reference_columns = {}
    if reference_rows:
        reference_columns = {
            " ".join(str(cell["value"] or "").split()).casefold(): column
            for column, cell in reference_rows[0][1].items()
        }
        for required in ("pecahan", "denom", "urutan denom", "kode kastip", "nama kastip"):
            if required not in reference_columns:
                raise WorkbookError(f"Sheet DENOM: kolom {required} tidak ditemukan.")
    for number, source_cells in reference_rows[1:]:
        cells = {
            target: source_cells.get(reference_columns[label], {})
            for target, label in {
                "A": "pecahan",
                "B": "denom",
                "C": "urutan denom",
                "E": "kode kastip",
                "F": "nama kastip",
            }.items()
        }
        code, value = _cell_value(cells, "A"), _cell_value(cells, "B")
        if code and value:
            try:
                reference = {
                    "value": denomination_decimal(value, formatted=cells["B"]["type"] != "n"),
                    "order": _cell_value(cells, "C"),
                }
                if code in denominations and denominations[code]["value"] != reference["value"]:
                    raise WorkbookError("Kode pecahan duplikat memiliki nominal berbeda.")
                denominations[code] = reference
            except ValueError:
                raise WorkbookError("Referensi DENOM memiliki angka tidak valid.") from None
        region_code, region_name = _cell_value(cells, "E"), _cell_value(cells, "F")
        if region_code and region_name:
            if cells["E"]["type"] == "n":
                try:
                    region_code = integer_decimal(region_code)
                except ValueError:
                    raise WorkbookError("Referensi kode Kastip harus bilangan bulat.") from None
            if region_code in regions and regions[region_code] != region_name:
                raise WorkbookError("Kode wilayah duplikat memiliki nama berbeda.")
            regions[region_code] = region_name
    result = []
    supported = False
    for name, adapter in ADAPTERS.items():
        if name not in sheets or not sheets[name]:
            continue
        supported = True
        _, header_cells = sheets[name][0]
        headers = {}
        for column, cell in header_cells.items():
            label = " ".join(str(cell["value"] or "").split()).casefold()
            if label in headers:
                raise WorkbookError("Kolom header duplikat tidak didukung.")
            headers[label] = column
        columns = {}
        for key, aliases in adapter.items():
            matches = [headers[a.casefold()] for a in aliases if a.casefold() in headers]
            if len(matches) > 1:
                raise WorkbookError(f"Sheet {name}: lebih dari satu kolom untuk {aliases[0]}.")
            match = matches[0] if matches else None
            if not match:
                raise WorkbookError(f"Sheet {name}: kolom {aliases[0]} tidak ditemukan.")
            columns[key] = match
        for row_number, cells in sheets[name][1:]:
            first = _cell_value(cells, columns["transaction_date"])
            if first.casefold() in {"total", "grand total", "subtotal", "jumlah"}:
                continue
            result.append(
                _normalize_row(name, row_number, cells, columns, denominations, regions, epoch)
            )
            if len(result) > row_limit:
                raise WorkbookError("Jumlah transaksi melebihi batas.")
    if not supported:
        raise WorkbookError("Tidak ditemukan sheet transaksi SETBAY yang didukung.")
    update = None
    for number, cells in sheets.get("Tanggal Update", []):
        if number == 2 and "A" in cells:
            try:
                update = _parse_date(cells["A"], epoch)
            except (ValueError, InvalidOperation):
                pass
    return ParsedWorkbook(
        {
            "checksum": checksum,
            "is_demo": checksum == DUMMY_CHECKSUM,
            "schema_version": SCHEMA_VERSION,
            "source_update_date": update,
            "sheets": list(sheets),
            "transaction_rows": len(result),
        },
        denominations,
        regions,
        result,
    )
