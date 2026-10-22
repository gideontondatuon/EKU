# Hasil refactoring Dashboard Cashflow EKU

Selesai: 22 Oktober 2026. Implementasi pada aplikasi Django existing. Tidak ada deployment, reset database, penghapusan data historis, atau perubahan migrasi selama pekerjaan ini.

## 1. Masalah yang ditemukan

- Upload memerlukan tahap simpan manual walaupun baris sudah valid.
- Rekening numeric yang tidak mengubah nominal cashflow menahan seluruh baris KASTIP contoh.
- Master pecahan baru tidak bisa dibentuk dari referensi DENOM yang konsisten.
- Rekonsiliasi pada commit dapat menganggap transaksi berbeda dalam batch sendiri sebagai kandidat historis.
- Riwayat/hasil impor menampilkan dictionary dan kode status; sidebar serta filter periode terlalu padat.
- Public menempatkan banyak catatan metode di atas indikator utama, dan menampilkan menu estimasi yang belum tersedia.
- Utilitas fix_denom menebak leading zero dan menulis ulang workbook, berisiko menghilangkan cache formula.

Bukti struktur, dependensi, workbook dan checkpoint terdapat di [REFACTOR_AUDIT.md](REFACTOR_AUDIT.md).

## 2. File yang diperbaiki

| Area | File |
|---|---|
| Parser dan import | `imports/parser.py`, `imports/services.py` |
| UI dan integrasi | `dashboard/views.py`, `dashboard/forms.py`, `dashboard/context.py`, `dashboard/templatetags/eku_tags.py` |
| Konfigurasi aset | `config/settings.py` |
| Admin | `templates/base_admin.html`, `imports.html`, `import_detail.html`, `review_detail.html`, `confirmation.html`, `settings.html`, `transactions.html` |
| Public | `templates/base_public.html`, `public.html` |
| Komponen bersama | `templates/partials/form_field.html` (baru), `form_fields.html`, `filters.html` |
| Tampilan/interaksi | `static/css/input.css`, `static/css/app.css`, `static/js/app.js` |
| Utilitas dan dokumentasi | `scripts/fix_denom.py`, `README.md`, `docs/excel-mapping.md`, kedua laporan refactoring |
| Pengujian | `tests/test_imports.py`, `test_data_management.py`, `test_smart_import.py` (baru), `test_refactor_responsive.py` (baru) |

Migrasi, model database, autentikasi/permission, service publikasi, soft delete/pemulihan dan data legacy dipertahankan. Komponen field formulir dideduplikasi; file legacy/vendor tidak dihapus karena belum terbukti aman untuk dibuang. `fix_denom.py` dipertahankan sebagai entry point inspeksi read-only untuk kompatibilitas.

## 3. Perilaku akhir

- **Upload → validasi → simpan baris valid → ringkasan**. Ringkasan memiliki enam metrik; peringatan tidak dijumlahkan sebagai status eksklusif karena bisa melekat pada transaksi tersimpan.
- Kedua sheet SETBAY dibaca berdasarkan header dan alias fungsional; DENOM mengikuti nama kolom meski urutannya berubah. Sheet tidak relevan diabaikan, batas arsip dan larangan external links/macro tetap ditegakkan.
- Rekening numeric integer positif hingga 15 digit diterima dengan peringatan dan nilai canonical tanpa menambahkan nol. Risiko presisi, konflik aritmetika dan netflow tetap ditahan.
- Pecahan baru dapat dibuat dari referensi Excel positif yang sesuai aritmetika transaksi, disertai audit dan provenance batch. Master existing tidak ditimpa atau dipromosikan diam-diam, termasuk master demo pada data operasional.
- Pencocokan file identik tetap idempoten. Fingerprint identik saja tidak cukup untuk melewati transaksi historis: scope/snapshot lengkap dan occurrence matching tetap diperlukan. Rekening numeric yang tidak pasti menghasilkan pencocokan konteks konservatif terhadap sejarah.
- Baris berbeda dalam satu unggahan tidak ditahan hanya karena batch sendiri sudah menyimpan transaksi sebelumnya. Repeated fingerprint dalam file tetap memerlukan review.
- ADD, UPDATE, REPLACE tetap tersedia; UPDATE memilih target, REPLACE mempertahankan preview/konfirmasi bertanda tangan dan perlindungan revision.
- Enam menu utama; antrean verifikasi di Import Excel; master/pengguna/audit/pemulihan/reset melalui Pengaturan. Pengguna dengan izin verifikasi tanpa izin impor tetap dapat mencapai antreannya.
- Hasil per baris dan pratinjau perubahan memakai bahasa Indonesia/tabel, bukan raw JSON. Detail teknis audit tetap tersedia di area administrasi.
- Public tetap anonim, read-only dan berbasis snapshot. Filter tanggal mengikuti periode; KPI dan tren diprioritaskan, rincian wilayah/metode dapat dibuka sesuai kebutuhan. Tidak ada rekening/nama bank internal dalam public.

## 4. Bukti pengujian

| Pemeriksaan | Hasil |
|---|---|
| Regresi keseluruhan setelah refactor inti, termasuk 3 tes browser | **99 passed**, 120,58 detik; `artifacts/refactor-tests.xml` |
| Parser setelah tambahan pengabaian sheet tidak relevan (termasuk satu kasus baru) | **25 passed**, 26 deselected; `artifacts/refactor-parser-tests.xml` |
| Browser ulang setelah penyederhanaan filter/catatan public | **3 passed**, 36,31 detik; `artifacts/refactor-responsive-tests.xml` |
| Ruff pada seluruh file Python yang berubah | Lulus |
| Django system check | Tidak ada masalah |
| `makemigrations --check --dry-run` dengan koneksi PostgreSQL | No changes detected |
| Perbandingan migrasi dengan checkpoint | Tidak ada file migrasi berubah |

Jumlah kasus unik yang terverifikasi: **100**; hasil pengulangan subset tidak dijumlahkan sebagai tes baru.

Cakupan: kedua sheet, alias/header dan DENOM terurut ulang, UK/UL, account numeric/text/risiko presisi, tanggal/epoch, Deposit/Withdrawal negatif/positif, konflik nominal/netflow, partial import, master conflict, ambiguous duplicates, historical snapshot, file identik berganti nama, mode update/replace, rollback, izin terpisah, audit redaction, isolasi public dan kegagalan transaksi.

Browser memakai Google Chrome headless lokal pada lebar 390, 768, 1440 px. Lima halaman pada setiap lebar: dashboard admin, import, hasil import, pengaturan, public. HTML berasal dari view Django asli dengan database tes dan data sintetis; aset lokal dirutekan melalui Playwright. Memeriksa overflow, menu mobile, enam navigasi utama, panel lanjutan, kontrol periode, console errors dan public tanpa identitas bank/rekening. Ini bukan deployment atau uji autentikasi jaringan produksi.

Screenshot: [Import mobile](artifacts/refactor-ui/390-1.png), [hasil import desktop](artifacts/refactor-ui/1440-2.png), [public mobile](artifacts/refactor-ui/390-4.png), [public desktop](artifacts/refactor-ui/1440-4.png).

File referensi pengguna dibaca **read-only**, bukan diimpor ke database aplikasi: **18 baris valid dengan 9 peringatan rekening numeric**, 35 mapping pecahan, 4 wilayah. Fixture sumber hanya memiliki Deposit; Withdrawal diuji dengan data sintetis. Tahun transaksi contoh 2021 tetap dipertahankan, tidak ditebak dari nama workbook.

## 5. Keputusan manusia / keterbatasan

- **Logo resmi BI:** belum tersedia aset lokal yang disertai izin penggunaan. `BI_LOGO_STATIC_PATH` siap memakai aset static lokal berizin; identitas netral PUR tetap dipakai sampai aset diberikan. Screenshot referensi tidak diekstrak menjadi logo.
- **Estimasi:** belum tersedia skema Excel/metode dan cakupan publikasi yang disetujui. Menu admin menjelaskan kondisi ini; menu estimasi public disembunyikan. Tidak ada angka estimasi dibuat.
- **Identitas transaksi:** sumber tidak memiliki ID unik. Kasus historis ambigu dan risiko presisi rekening tetap memerlukan keputusan operator; tidak ada deduplikasi berdasarkan fingerprint saja.
- **Produksi:** izin publikasi/hosting dan kebijakan operasional tetap berlaku. Uji beban workbook mendekati batas 50.000 transaksi belum dilakukan; import masih sinkron. Master referensi yang konflik dengan sumber memerlukan penyelesaian manusia.

## 6. Kesiapan

**Siap untuk evaluasi lokal dan uji operasional terkontrol.** Refactoring, regression test, pemeriksaan browser dan dokumentasi selesai. Deployment production tidak dilakukan. Data aplikasi dan pengaturan publikasi tidak diubah oleh pengujian.

Checkpoint sebelum perubahan: `.private/checkpoints/before-smart-import-20261022.tar.gz`, permission 0600, tanpa `.env`, database atau upload pengguna.
