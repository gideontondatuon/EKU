# Audit refactoring Dashboard Cashflow EKU

Tanggal: 22 Oktober 2026. Sasaran: aplikasi Django yang ada, bukan pembangunan ulang.

## Inventaris dan dependensi

- Workspace berisi Django `Dashboard Cashflow EKU` dan Streamlit legacy `../eku_dashboard`. Django tidak mengimpor package legacy; legacy/data Parquet tetap dipertahankan sebagai aplikasi terpisah.
- `accounts`: user, peran, granular permission, autentikasi dan limiter; `core`: bank, wilayah, pecahan, settings singleton, audit append-only.
- `cashflow`: UUID transaksi, source row, fingerprint non-unique, arsip/pemulihan, revision append-only.
- `imports`: batch checksum+dataset unique, staging, candidate matches, verification decisions; parser OOXML bounded dengan cached formula, Decimal dan epoch Excel.
- `publications`: snapshot agregat tersegel, parent version, pointer aktif dan rollback. Trigger PostgreSQL menegakkan immutability; endpoint public menggunakan proyeksi snapshot, bukan transaksi internal.
- `estimates`: adapter belum ditetapkan; tidak ada dasar untuk mengarang estimasi.
- `dashboard`: views, forms, analytics, export; template admin/public; font Plus Jakarta Sans lokal; CSS sumber dan hasil build; ECharts lokal.
- Migrasi accounts/core/cashflow/imports/publications/estimates saling bergantung, termasuk FK melingkar transaksi–source row. Tidak ada migrasi yang akan dihapus atau tabel yang direset dalam refactoring ini.
- Reset data dari pekerjaan sebelumnya adalah tindakan terpisah; tidak dijalankan lagi. Soft delete, audit, master, riwayat dan setting publikasi dipertahankan.

## Bukti workbook

Pengguna mengonfirmasi file tanpa akhiran `(1)` sama dengan referensi instruksi. File dibaca langsung secara read-only dari Download New, tidak dimasukkan ke database aplikasi.

SHA256: `3210a116daef7324703e82efbd77eaf2012da66cd0ea775e6c9edd0ae4029dfa`.

| Sheet | Temuan langsung |
|---|---|
| SETBAY MANADO | 9 baris, COTCP_AMOUNT/PIECES/NOTE_COIN_TYPE; Inflow, Outflow, Neflow; COTC_BRN_CODE2 tambahan |
| SETBAY KASTIP | 9 baris, COTCR_AMOUNT/PIECES/NOTE_COIN_TYPE; Inflow Kastip, Outflow Kasti, Netflow Kastip; rekening dan kode Kastip numeric |
| DENOM | 35 pecahan, 4 wilayah; label 1.000 UK/UL; kode wilayah numeric; banyak baris kosong |
| Tanggal Update | 26 Maret 2026 |
| Sheet2 | kosong; tidak menjadi transaksi |

Semua 18 contoh adalah Deposit, tanggal transaksi 10/15 September 2021 (bukan menyimpulkan tahun dari nama file). Withdrawal akan diuji secara sintetis. Baseline parser: 9 valid, 9 tertahan hanya karena rekening numeric.

## Masalah dan keputusan implementasi

1. Upload hanya staging dan membutuhkan klik simpan kedua: alur default akan otomatis commit baris valid. REPLACE tetap memerlukan preview/konfirmasi; UPDATE tetap memilih target eksplisit.
2. Rekening numeric menghambat cashflow walau nominal konsisten: jadikan peringatan non-kritis bila integer positif <=15 digit; simpan nilai sumber dan teks canonical, jangan menebak nol depan. Nilai berisiko kehilangan presisi tetap ditahan. Pencocokan historis tetap konservatif, termasuk saat rekening tidak pasti.
3. Pecahan baru membutuhkan persetujuan tiap kode: master baru dapat dibentuk dari DENOM bila referensi positif dan aritmetika baris sesuai. Sumber/master creation diaudit. Master existing yang konflik, belum diverifikasi, atau demo untuk operasional tidak ditimpa.
4. Commit melakukan pencocokan konteks terhadap baris baru dalam batch sendiri: dapat menahan pecahan berbeda dari kejadian yang valid. Kecualikan batch sendiri dari kandidat konteks (bukan dari pengaman repeated fingerprint).
5. Raw dictionary, status Inggris, UUID dan detail teknis mendominasi impor. Gunakan ringkasan enam metrik, label Indonesia, pesan per baris, dan panel lanjutan.
6. Sidebar terlalu banyak menu utama. Verifikasi menjadi antrean pada Import Excel; administrasi/master/arsip/audit/reset di panel pengaturan/submenu.
7. Dashboard public sudah read-only dan memakai snapshot. Pertahankan isolasi data; perjelas ringkasan dan sembunyikan estimasi yang belum tersedia dari navigasi public.
8. Logo yang tersedia hanya screenshot referensi; belum ditemukan aset resmi dengan izin penggunaan. Siapkan konfigurasi aset lokal; jangan mengekstrak/mengklaim logo screenshot sebagai aset resmi.
9. `scripts/fix_denom.py` tidak dipanggil aplikasi/dokumentasi; utilitas tersebut menebak leading zero dan menulis ulang workbook (menghilangkan cache formula). Ganti dengan utilitas inspeksi non-destruktif/penjelasan deprecation, bukan mengubah sumber.
10. Kode aplikasi legacy, static vendor, staticfiles dan migrasi bukan duplikasi aman untuk dihapus. Hanya redundansi template yang terbukti dipakai bersama akan digabungkan.

## Checkpoint dan verifikasi

Tidak ada repository Git pada folder proyek. Checkpoint source privat dibuat di `.private/checkpoints/before-smart-import-20261022.tar.gz` (0600), tanpa database, `.env` atau upload. Tidak ada deployment.

Rencana tes: parser kedua sheet, DENOM/alias/kolom ekstra, numeric/text identity, epoch, Deposit/Withdrawal, aritmetika/netflow, import parsial/idempotensi, snapshot historical matching, ambiguous occurrences, master conflict, granular permissions, public isolation/rollback, responsive browser desktop/mobile dengan data sintetis. Hasil akhir dicatat di `REFACTOR_RESULTS.md`.


## Penutupan audit

Refactoring selesai; lihat `REFACTOR_RESULTS.md` untuk daftar perubahan dan bukti pengujian. Seluruh migrasi identik dengan checkpoint. Hasil uji kasus unik 100 lulus, termasuk browser tiga ukuran; subset parser dan responsive diuji ulang setelah koreksi terakhir. Logo resmi dan skema estimasi masih menunggu input pemilik sistem.
