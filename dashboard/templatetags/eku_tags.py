from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()


@register.filter
def rupiah(value):
    if value is None or value == "":
        return "—"
    try:
        return "Rp " + format(Decimal(str(value)), ",.0f").replace(",", ".")
    except (InvalidOperation, ValueError):
        return "—"


@register.filter
def int_id(value):
    if value is None:
        return "—"
    try:
        return format(int(value), ",").replace(",", ".")
    except (ValueError, TypeError):
        return "—"


@register.filter
def import_status(value):
    return {
        "STAGED": "Siap diproses",
        "COMMITTED": "Selesai",
        "PARTIAL": "Sebagian tersimpan",
        "NEW_VALID": "Valid, siap disimpan",
        "IMPORTED": "Tersimpan",
        "ALREADY_IMPORTED": "Sudah ada, dilewati",
        "NEEDS_REVIEW": "Perlu diperiksa",
        "INVALID": "Perlu diperbaiki di Excel",
        "SKIPPED": "Dihapus dari antrean",
        "READY_UPDATE": "Siap diperbarui",
    }.get(value, "Menunggu proses")
