# Persyaratan dan kriteria penerimaan

Baseline: master prompt dalam proyek, inspeksi 21 Oktober 2026 WITA. Dokumen ini mencatat **persyaratan dan rencana verifikasi**, bukan menyatakan bahwa seluruh fitur atau tes sudah selesai. Bukti eksekusi dicatat terpisah dalam laporan pengujian milestone.

## Sumber dan cakupan

- [Master prompt](../MASTER_PROMPT_CODEX_GPT6_ULTRA_DASHBOARD_CASHFLOW_EKU.md) menjadi spesifikasi implementasi; pilihan Django di dokumen tersebut menggantikan diskusi Next.js sebelumnya.
- [Inspeksi workbook](excel-inspection.md) membaca seluruh sheet `references/SETBAY_DUMMY.xlsx`; [artefak terstruktur](excel-inspection.json) menyensor rekening.
- [Inspeksi visual](visual-inspection.md) mencakup seluruh lima gambar, serta tinjauan legacy Streamlit. Aplikasi baru berada di folder ini. Kode dan data `../eku_dashboard` tidak dimigrasi atau diubah.
- Tujuan hasil adalah aplikasi full-stack yang dapat **dievaluasi** untuk deployment. Persetujuan resmi, pentest, dan kelayakan operasional merupakan gate terpisah.

Status kebutuhan: **FINAL** sudah ditentukan; **DEFAULT AMAN** adalah perilaku sementara yang dapat ditinjau; **PENDING APPROVAL** menunggu keputusan berwenang; **PENDING INPUT** menunggu berkas/informasi; **DEFERRED** tidak dikerjakan sebagai fitur aktif. Status implementasi terpisah: `IMPLEMENTED`, `SCAFFOLDED`, `PENDING INPUT`, atau `BLOCKED BY APPROVAL`.

## Matriks ketertelusuran

ID AT di bawah adalah acceptance test/check yang harus dikaitkan dengan hasil eksekusi nyata. Check manual/infrastruktur tidak berubah menjadi PASS hanya karena unit test lulus.

| ID | Status | Persyaratan | Milestone | Kriteria penerimaan / ID pemeriksaan |
| --- | --- | --- | --- | --- |
| R01 | FINAL | Django modular monolith, PostgreSQL, template HTMX/Tailwind/ECharts | M1 | AT01: migrate, system check, halaman public/admin dan login dapat dijalankan |
| R02 | FINAL | Custom user; hanya SUPER_ADMIN dan ADMIN_STAFF awal; username/email dan password | M1–M2 | AT02: login valid/invalid, logout, user inactive, password hashing; tidak ada credential bawaan |
| R03 | FINAL | Permission granular per pengguna ditegakkan server | M2–M4 | AT03: tiap aksi mutasi/export diuji allow/deny dan HTTP direct request |
| R04 | FINAL | UUID transaksi; Rupiah utuh Decimal; inflow/outflow konsisten; netflow derived | M2 | AT04: constraint negatif/pecahan/amount dan hasil netflow positif/negatif |
| R05 | FINAL | Master bank, wilayah, pecahan; rekening/kode string restricted | M2–M3 | AT05: leading zero terjaga dan rekening tidak masuk audit generik/public |
| R06 | FINAL | Soft delete, restore, bulk independen; audit dan revision | M2–M4 | AT06: data terhapus tidak masuk agregasi; unauthorized restore/bulk ditolak |
| R07 | FINAL | Adapter kedua sheet aktual + DENOM; tanggal Excel, alias, cached formula | M3 | AT07: 8 kandidat sampel; 6 konsisten Rp8.200.000.000; 2 konflik ditahan; tanggal 2021; file tidak berubah |
| R08 | FINAL | Metadata file/checksum, raw JSONB, provenance baris unik | M3 | AT08: metadata/private file tersimpan; unique batch/sheet/row; checksum reupload tidak mengganda |
| R09 | FINAL | Rekonsiliasi multiset, fingerprint tidak globally unique | M3 | AT09: historical+new, identical occurrences, ambiguous match, soft-deleted match, concurrency |
| R10 | FINAL | Partial import: valid commit, ambiguous review, invalid tertahan | M3 | AT10: jumlah dan nominal aktif hanya baris eligible; status batch sesuai hasil nyata |
| R11 | FINAL | Verifikasi SKIP/CREATE/UPDATE/DEFER; alasan dan UUID target update | M3–M4 | AT11: permission verify, UUID wajib, old/new diff, keputusan diaudit |
| R12 | FINAL | Replace periode memerlukan scope dan deklarasi snapshot lengkap | M3–M4 | AT12: preview dampak + konfirmasi; tidak mengubah di luar scope; tanpa deklarasi ditolak |
| R13 | FINAL | Input/edit manual, filter/search/pagination, preview/history/queue/arsip | M4 | AT13: alur form valid/invalid, pagination, revision, permission, stale edit |
| R14 | FINAL | Statistik utama sumber kolom cashflow, conflict tidak ditimpa | M3/M6 | AT14: outflow positif/negatif sintetis, konflik type/amount/denom/netflow ditahan; sign normalization tercatat |
| R15 | FINAL | Harian/bulanan/tahunan/custom; internal bank/region/money/denom | M6 | AT15: filter konsisten KPI/chart/tabel/export; missing tidak menjadi nol palsu |
| R16 | FINAL | MoM/YoY sepadan, N/A baseline nol/tidak tersedia | M6 | AT16: nol, kosong, periode parsial, rentang lintas tahun dan leap year |
| R17 | FINAL | Pola musiman deskriptif, observasi dan keterbatasan jelas | M6 | AT17: empty state data tidak cukup; tidak ada label prediksi |
| R18 | DEFAULT AMAN | MANUAL; hanya agregat wilayah per tanggal; approval reference kosong | M5 | AT18: perubahan internal tidak mengubah public; operasional tanpa approval ditolak |
| R19 | FINAL | Immutable publication snapshot; pointer atomik; rollback terpisah | M5 | AT19: snapshot lama tidak berubah; rollback mengganti pointer tanpa mutasi internal; atomic failure/concurrency |
| R20 | FINAL | Automatic publication hanya eligible dan tetap tunduk policy | M5 | AT20: valid saja, pending/invalid/terhapus tersaring; approval tetap wajib |
| R21 | FINAL | Public hanya projection aktif; tanpa bank/account/raw/audit | M5–M6 | AT21: negative tests HTML/JSON/CSV/XLSX/PDF/error/cache; tidak query bebas transaksi |
| R22 | FINAL | Export CSV/Excel/PDF sesuai filter/scope dan formula-safe | M5–M6 | AT22: format dapat dibuka, total benar, formula injection dicegah, metadata versi dan waktu |
| R23 | FINAL | Public tanpa sidebar, header/tabs/4 KPI; Admin biru dengan sidebar | M1/M6 | AT23: render mobile/desktop, keyboard focus, label, kontras, tabel alternatif chart |
| R24 | DEFAULT AMAN | Logo placeholder PUR; font fallback jika aset font belum tersedia | M1/M6 | AT24: tidak ada logo BI hasil crop/tiruan atau request eksternal tanpa kebijakan |
| R25 | FINAL | Estimasi Excel model/adapter contract/empty state | M7 | AT25: format belum dikonfigurasi menolak import final dan tidak membuat angka |
| R26 | DEFAULT AMAN | Automatic estimation OFF; ON hanya informasi belum dikonfigurasi | M7 | AT26: tidak ada metode/prediksi executable, tanpa publikasi forecast |
| R27 | FINAL | Upload xlsx privat, limit ZIP/parser/size, formula tidak dieksekusi | M3/M8 | AT27: malicious filename, macro/external link, ZIP bomb, oversized, missing cache, recoverable failure |
| R28 | FINAL | CSRF, secure sessions, login rate-limit, private no-store, audit redaction | M1/M8 | AT28: negative auth/security tests; deploy check dengan settings production |
| R29 | FINAL | Docker Compose portable, PostgreSQL17, migrations, gunicorn/Nginx | M1/M8 | AT29: build/up/health/migrate/smoke pada host Docker; unavailable dicatat SKIP/BLOCKED |
| R30 | FINAL | Backup DB+private files; restore drill; CI/lint/test/runbook | M8 | AT30: restore ke database terpisah dan verifikasi jumlah/checksum; lint dan CI tests nyata |
| R31 | DEFAULT AMAN | Demo sintetis hanya nonproduction, label DATA DUMMY jelas | M1–M8 | AT31: seed ditolak production; dummy tidak diklaim operasional; tidak auto-import legacy |
| R32 | PENDING INPUT | Workbook estimasi asli, mapping final dan scope | M7 | Gate G01: pemilik data memberikan template dan definisi; AT25 tetap berlaku |
| R33 | PENDING APPROVAL | Publikasi operasional, grain waktu/wilayah, ekspansi pecahan/jenis uang | M5 | Gate G02: persetujuan tercatat sebelum real publish; granularitas tambahan tetap tertutup |
| R34 | PENDING APPROVAL | Logo/aset resmi, hosting/domain/lokasi data/retensi/backup | M8 | Gate G03: review TI dan pemilik sistem; deployment publik riil belum diotorisasi |
| R35 | DEFERRED | Model forecasting otomatis dan publikasi hasilnya | M7 | Gate G04: metode/validasi/approval terpisah; tidak ada estimasi buatan |
| R36 | PENDING APPROVAL | SSO/MFA wajib dan mekanisme integrasi | M8 | Gate G05: arsitektur extensible; tidak mengklaim MFA aktif |
| R37 | DEFERRED | Data bank/rekening/transaksi individual public | — | Default tetap dilarang; perubahan memerlukan approval baru dan ulang AT21 |

## Temuan workbook yang mengubah desain

Workbook hanya mempunyai delapan transaksi Deposit pada 10 dan 15 September 2021, sedangkan metadata update adalah 26 Maret 2026. Tidak ada bukti kelengkapan historis. Total literal delapan baris Rp8.254.000.000 tidak sama dengan total enam baris aritmetika konsisten Rp8.200.000.000. KX16 dan KT16 tidak ada dalam DENOM serta nominal tidak cocok dengan pecahan × lembar; keduanya **ditahan**, bukan diperbaiki lewat tebakan pembagian.

`Nama Kastip` berisi kode enam digit. Alias `Outflow Kasti` dan `Neflow` harus diterima. Parser tidak membatasi baca pada named filter/dimension Excel. Terdapat 36 formula dengan cached values, termasuk shared formulas. Rumus outflow Withdrawal menghasilkan nilai negatif; domain menyimpan magnitudo nonnegatif, sehingga aturan normalisasi harus eksplisit, tercatat, dan divalidasi. Bentuk Withdrawal aktual belum tersedia; pengujian bentuk tersebut harus berlabel sintetis.

## Syarat pelaporan akhir

Setiap milestone melaporkan perintah, pass/fail/skip, berkas hasil, risiko dan scope. M0 tidak membutuhkan migrasi karena belum ada model. Docker yang tidak tersedia, file estimasi yang belum ada, serta approval yang belum diberikan tetap disebut terbuka. Passing unit tests tidak menggantikan browser accessibility check, Docker smoke, production restore drill, pentest, atau persetujuan lembaga.
