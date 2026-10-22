"""Deprecated rewrite tool: inspect SETBAY without modifying workbook/cache/identities."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from imports.parser import parse_workbook  # noqa: E402


def fix_file(file_path):
    path = Path(file_path).expanduser().resolve()
    parsed = parse_workbook(path.read_bytes(), path.name)
    print(
        f"Inspeksi selesai: {len(parsed.rows)} transaksi; {len(parsed.region_references)} wilayah."
    )
    print("File tidak diubah. Import otomatis membaca identitas sumber tanpa menebak nol depan.")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Penggunaan: python scripts/fix_denom.py <workbook.xlsx>")
    raise SystemExit(fix_file(sys.argv[1]))
