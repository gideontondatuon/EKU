# MASTER PROMPT — CODEX GPT-6 ULTRA
## Dashboard Cashflow EKU — Estimasi Kebutuhan Uang | Unit PUR, KPw Bank Indonesia Provinsi Sulawesi Utara

> SALIN SELURUH DOKUMEN INI KE CODEX. Jadikan ini spesifikasi produk dan instruksi implementasi full-stack. Gunakan bahasa Indonesia untuk komunikasi, antarmuka, dan dokumentasi pengguna. Kode, nama variabel, dan struktur internal boleh memakai bahasa Inggris yang konsisten.

## 0. PERAN, SASARAN, DAN CARA BEKERJA

Kamu bertindak sebagai **Principal Software Architect, Senior Django Engineer, PostgreSQL Database Engineer, Security Engineer, QA Engineer, DevOps Engineer, dan Senior UI/UX Designer**. Bangun aplikasi web yang nyata dan berfungsi bernama **Dashboard Cashflow EKU**, subjudul **Estimasi Kebutuhan Uang**, untuk **Unit Pengelolaan Uang Rupiah (PUR), Kantor Perwakilan Bank Indonesia Provinsi Sulawesi Utara**.

Tujuan: memonitor inflow, outflow, netflow uang kartal; menganalisis tren/wilayah/pecahan; menampilkan hasil estimasi yang diimpor; memberi Admin PUR pengelolaan data Excel/manual yang aman; dan menyediakan dashboard public read-only tanpa login. Jangan hanya membuat mockup, prototipe statis, atau pseudo-code. Implementasikan backend, database, UI, tes, Docker, dan dokumentasi hingga siap **dievaluasi** untuk deployment, bukan mengklaim telah disetujui production.

**Cara kerja wajib:**
1. Periksa isi repository dan berkas yang benar-benar tersedia, termasuk workbook dummy dan screenshot UI bila telah dilampirkan. Jangan mengarang hasil inspeksi file atau keberadaan logo/format estimasi. Bila repository kosong, buat struktur proyek baru yang rapi. Jika suatu lampiran belum tersedia pada lingkungan Codex, minta berkasnya atau sediakan fixture sintetis berlabel jelas; jangan mengklaim mengolahnya.
2. Mulai dengan `docs/requirements.md`, `docs/architecture.md`, `docs/erd.md`, `docs/decisions.md`, `docs/security-and-assumptions.md`, dan rencana milestone singkat. Bandingkan hasil inspeksi workbook dengan asumsi mapping di spesifikasi ini.
3. **Implementasikan bertahap**, namun jangan berhenti pada dokumen: jalankan setiap tahap berikutnya sampai ruang lingkup yang terdefinisi selesai, selama tools/izin memungkinkan. Di tiap milestone, jalankan migrasi, tes, lint/format, lalu laporkan hasil nyata, blocker, keputusan, dan file yang diubah.
4. Buat pilihan engineering wajar ketika detail minor tidak diketahui; catat di decision log. **Jangan mengarang** metode estimasi otomatis, format Excel estimasi yang belum diberikan, identitas transaksi unik dari sumber, persetujuan Bank Indonesia, infrastruktur hosting, maupun aset branding resmi.
5. Untuk keputusan berisiko tinggi yang belum dapat diverifikasi (izin cloud eksternal, data yang boleh dipublikasikan, metode prediksi, logo resmi, integrasi SSO, retensi), bangun fitur yang aman dengan default tertutup/nonaktif dan dokumentasikan persetujuan yang diperlukan. Jangan melewati gate keamanan.
6. Dilarang menampilkan data dummy sebagai data produksi, mengunduh logo palsu untuk mengesankan logo resmi, menyimpan secret di Git, atau menampilkan bank/account/transaksi internal di endpoint public.

## 1. KEPUTUSAN FUNGSIONAL FINAL

### 1.1 Pengguna
- **Public / perbankan**: tanpa login, hanya dapat melihat data yang secara eksplisit telah dipublikasikan; tidak bisa mengubah/import data. Siapa pun yang memiliki akses URL berpotensi melihat isi; anggap semua endpoint public sepenuhnya terbuka. Default: **agregat per wilayah saja, TIDAK menampilkan identitas/rincian bank**.
- **Super Admin**: login pribadi, kendali akun/role/permission, master data, seluruh operasi transaksi, fitur, publikasi, rollback dan audit.
- **Admin Staf**: akun login pribadi, operasi yang sesuai izin. Izin granular **per pengguna** dapat diberikan dan dicabut oleh Super Admin, setidaknya: `import_data`, `add_transaction`, `edit_transaction`, `verify_ambiguous`, `publish_manual`, `soft_delete`, `restore`, `bulk_soft_delete`, `bulk_restore`, `export_internal`. Tidak cukup hanya menyembunyikan tombol—otorisasi wajib diuji dan ditegakkan di server pada setiap endpoint/action.
- Hanya ada dua role awal: `SUPER_ADMIN`, `ADMIN_STAFF`. Sistem extensible, tetapi jangan menambahkan role ketiga sekarang.
- Login melalui username/email dan password; hashing Django standar, kebijakan password aman, session cookie secure, CSRF, rate-limit login, proteksi brute force; desain arsitektur siap MFA tetapi **jangan mengklaim MFA aktif** jika belum diimplementasikan/dikonfigurasi.

### 1.2 Pengelolaan data
- Admin dapat **import Excel** dan **menambah/mengedit transaksi melalui formulir UI**.
- Import fleksibel dengan 3 mode: (a) **Tambah data baru**; (b) **Perbarui transaksi terpilih** setelah pencocokan/konfirmasi; (c) **Perbarui berdasarkan periode/wilayah** hanya apabila Admin secara eksplisit menyatakan sumber Excel sebagai snapshot lengkap lingkup yang dipilih; perlihatkan diff dan konfirmasi dampak. Jangan pernah menjadikan hilangnya baris dalam file yang belum diverifikasi sebagai alasan untuk otomatis menghapus data periode.
- Workbook terbaru pada umumnya **memuat data historis + data baru**, struktur tabel relatif sama. Sistem membaca data lama untuk rekonsiliasi terlebih dahulu. Transaksi ambigu diverifikasi Admin.
- **Import parsial final**: baris valid dan cukup yakin baru dapat disimpan; baris ambigu masuk antrean verifikasi; baris invalid ditolak/ditahan; transaksi lama yang sudah dikenali dilewati. Import tidak wajib menunggu seluruh verifikasi selesai. Jangan pernah memublikasikan baris `PENDING_REVIEW` atau `INVALID`.
- **Tidak ada ID transaksi unik pada sumber Excel**. UUID dibuat oleh aplikasi. Fingerprint/hash transaksi berguna untuk pencocokan, tetapi **bukan UNIQUE global**. Dua transaksi identik secara atribut bisa tetap sah. File re-upload dan pencocokan harus idempotent sejauh dapat diverifikasi; untuk ambiguitas wajib intervensi Admin. Catat asal file, sheet, nomor baris, normalisasi, fingerprint, calon matching, tindakan, alasan, user, waktu.
- **Soft delete saja** untuk workflow normal: hapus dari daftar/perhitungan aktif, simpan record dan audit, dapat dipulihkan pengguna berizin. Izin `soft_delete` dan `restore` independen untuk tiap staf. Bulk action boleh bagi akun berizin dengan konfirmasi rinci dan audit. Jangan sediakan hard delete transaksi lewat UI umum.
- **Import file**: pratinjau dan statistik `baru`, `sudah ada`, `ambigu`, `invalid`; validasi tanggal, bank, lokasi, nominal, jenis transaksi, pecahan, jumlah lembar, dan potensi ganda. Pada update transaksi tampilkan nilai sebelum/sesudah. Untuk replace periode, tampilkan ditambah/diubah/dinonaktifkan dan total inflow/outflow/netflow sebelum-sesudah.
- Simpan file sumber secara privat, metadata, checksum, batch log, row raw `JSONB`, keputusan verifikasi, histori revisi, dan backup sesuai kebijakan lembaga. Terapkan pembatasan ukuran, ekstensi `.xlsx`, validasi konten sesungguhnya, parser aman, batas sumber daya, cegah formula injection saat ekspor CSV/Excel, dan pastikan file yang diunggah tak pernah dapat dieksekusi/diakses secara public.

### 1.3 Cashflow, indikator, dan filter
- **Inflow dan Outflow utama berasal dari kolom Excel** (`Inflow`/`Outflow` dan padanan sheet), dengan validasi silang ke `TRANSACTION_TYPE`, nominal, dan pecahan. Jangan diam-diam menimpa sumber saat terjadi konflik: klasifikasikan/beri flag untuk verifikasi.
- **Netflow = Inflow − Outflow**. Positif: net inflow. Negatif: net outflow. Nilai Rupiah pakai `NUMERIC/Decimal`, tidak menggunakan floating-point sebagai sumber kebenaran.
- Total transaksi menghitung transaksi valid aktif; jangan menghitung jumlah baris yang tertahan. Hindari double-counting antara baris transaksi dan agregasi.
- Filter periode: **harian, bulanan, tahunan, rentang tanggal custom**; dapat digunakan untuk KPI, grafik, tabel, dan ekspor. Filter tambahan: wilayah layanan, jenis uang, pecahan. **Filter bank hanya di admin** sampai ada persetujuan eksplisit mengubah kebijakan public; jangan menampilkannya secara tersirat melalui API/export public.
- Analisis **MoM** dan **YoY** dengan periode pembanding sepadan, menyatakan `N/A` apabila baseline nol/tidak ada data dan memberi catatan bila data periode belum lengkap. Jangan mengartikan data kosong sebagai nol tanpa penjelasan.
- Wilayah didasarkan pada master dinamis, dimulai dari Manado KPwBI dan seluruh SKM/Kas Titipan yang dikenali pada Excel (termasuk referensi Tahuna, Siau, Melonguane, Kotamobagu bila benar-benar ada pada sumber). Jangan mengarang nominal wilayah.
- Menu public yang dirancang: **Ringkasan**, **Tren**, **Pecahan**, **Pola Musiman**, **Estimasi**. Super Admin bisa mengubah visibilitas menu public. Pola Musiman adalah **analisis deskriptif historis**, bukan prediksi otomatis. Bila data tidak memadai, tampilkan empty state/penjelasan.
- Ekspor **Excel, CSV, PDF** mengikuti filter dan scope izin: public hanya agregat yang sudah dipublikasikan; internal sesuai RBAC. Ekspor PDF ringkas dan terbaca, berisi periode, satuan, sumber/versi publikasi, dan waktu ekspor.

### 1.4 Estimasi kebutuhan uang
- Estimasi utama **berasal dari file Excel** dan ditampilkan/divisualisasikan. **FILE/FORMAT ESTIMASI ASLI BELUM ADA**, cakupan agregat/per bank/both belum diputuskan. Buat domain model, izin, adapter import dan halaman/empty state yang bisa menerima format nanti, namun **jangan mengarang mapping final atau data estimasi**. Modul boleh dibangun sebagai scaffold fungsional teruji dengan kontrak import yang bisa dikonfigurasi; jangan klaim integrasi lengkap sebelum ada file asli.
- **Estimasi Otomatis** berdasarkan historis adalah **fitur opsional terpisah, default OFF**, metode belum diputuskan/pimpinan belum memberi arahan. Super Admin dapat mengaktifkan/nonaktifkan visibilitas modul admin; jika ON sebelum metode tersedia, tampilkan status "Belum dikonfigurasi" dan **jangan menjalankan atau mempublikasikan ramalan hasil karangan**. Publikasi hasil otomatis (kelak) perlu persetujuan metode dan kontrol publikasi terpisah.

### 1.5 Publikasi public
- Global setting `publication_mode`: `MANUAL` (default yang aman) / `AUTOMATIC`, dapat diganti oleh Super Admin.
- Mode manual: perubahan internal tidak tampil di public sampai dipublikasikan oleh Super Admin atau Admin Staf dengan izin `publish_manual`.
- Mode otomatis: setelah validasi/import/perubahan yang memenuhi aturan eligible, sistem membuat **versi publikasi baru** dari hanya data yang boleh dibuka ke public. Validasi gagal/pending/ambigu tidak pernah tampil, dan perubahan ambigu tidak menyebabkan snapshot publish rusak. Perjelas kepada admin adanya data menunggu review.
- Simpan **immutable publication snapshot/version**, audit siapa/apa/kapan, pointer `current_publication_version`, dan **rollback publikasi** oleh pengguna berwenang. Rollback mengganti versi yang ditampilkan, **tidak merusak atau me-rollback transaksi internal**. Uji atomicity pointer; endpoint public hanya membaca projection/versi public yang disetujui, bukan query bebas dari tabel transaksi internal.
- Default public **hanya total agregat per wilayah** (bukan per bank atau rekening). Tidak boleh ada kebocoran data melalui JSON, HTML, chart metadata, cache, export, autocomplete, logs, atau error response. Kebijakan publikasi nyata memerlukan persetujuan berwenang.

## 2. REFERENSI EXCEL DUMMY — WAJIB INSPEKSI

Nama attachment sebelumnya: `_dummy - DATA SETBAY MANADO DAN SKM 2022 - 2026 (1).xlsx`. Dalam lingkungan Codex berkas mungkin belum terpasang; **cek dahulu**, minta upload bila diperlukan.

Berdasarkan inspeksi struktur sampel yang dilakukan dalam diskusi:
- Sheets: `Tanggal Update`, `DENOM`, `SETBAY KASTIP`, `SETBAY MANADO`, `Sheet2` (kosong).
- `SETBAY MANADO` (kolom A:P): `COTC_TRAN_DATE`, `COTC_BRN_CODE`, `MBRN_NAME`, `TRANSACTION_TYPE`, `MONEY_TYPE`, `BANK_NAME`, `BANK_ACCOUNT`, `COTC_BRN_CODE2`, `COTCP_NOTE_COIN_TYPE`, `COTCP_AMOUNT`, `COTCP_PIECES`, `Denom`, `Urutan Denom`, `Inflow`, `Outflow`, `Neflow` (penulisan `Neflow` pada contoh memang demikian).
- `SETBAY KASTIP` (kolom A:Q): `COTC_TRAN_DATE`, `TRANSACTION_TYPE`, `MONEY_TYPE`, `BANK_NAME`, `BANK_ACCOUNT`, `COTC_BRN_CODE`, `MBRN_NAME`, `COTC_CLIENT_BRNCODE`, `COTCR_NOTE_COIN_TYPE`, `COTCR_AMOUNT`, `COTCR_PIECES`, `Denom`, `Urutan Denom`, `Nama Kastip`, `Inflow Kastip`, `Outflow Kasti`, `Netflow Kastip`. Perhatikan **`Outflow Kasti`** dalam file dummy (bukan sekadar `Outflow Kastip`).
- `DENOM`: `Pecahan`, `Denom`, `Urutan Denom`; dan pada kolom terpisah `Kode Kastip`, `Nama Kastip`. Contoh kode dengan nol di depan: `000000`, `000001`, `000002`, `000003`; nama lokasi referensi Tahuna, Siau, Kotamobagu, Melonguane.
- `Tanggal Update`: sel tanggal update; contoh Excel serial datetime. Tanggal transaksi contoh juga merupakan Excel serial dates; **konversikan menjadi date yang benar**, jangan gunakan angka serial sebagai tanggal mentah. Nama file menyebut 2022–2026, tetapi contoh baris transaksi bertanggal 2021; **jangan mengasumsikan rentang tahun dari nama file**.
- Rekening dan kode dapat berawalan nol, misalnya `0000000000` dan `000001`. Simpan sebagai string, jangan integer; waspadai Excel numeric coercion.
- Nilai `Denom` dapat berisi spasi, titik sebagai pemisah ribuan, dan kode pecahan yang tidak konsisten dengan perkalian nominal × jumlah lembar. Contoh referensi `DENOM` tidak boleh dipercaya tanpa validasi silang. Kode pecahan seperti `KY14`, `KY16`, `KX16`, `KT16` perlu mapping/validasi yang dapat dikelola, bukan hard-code bahwa semuanya Rp100.000.
- Pada sampel, kedua sheet transaksi hanya berisi beberapa baris `Deposit` dan inflow positif; **jangan berasumsi bentuk outflow dari contoh saja**. Siapkan test fixture untuk Withdrawal/outflow dengan data sintetis dan verifikasi aturan terhadap file operasional bila tersedia.
- Tidak ada contoh workbook estimasi yang definitif. Jangan menganggap cashflow historis otomatis merupakan hasil estimasi.

**Implementasi parser:** gunakan registry per-sheet schema adapter / column aliases / normalisasi / validasi; file dan schema version dapat berkembang. Tampilkan report data quality yang dapat diunduh. Abaikan sheet kosong. Jangan mengimpor totals/rumus agregat sebagai transaksi bila ada baris ringkasan. Validasi formula cells dan nilai cached dengan aman. Pertahankan raw data untuk audit tanpa mengandalkannya sebagai representasi terstandardisasi.

## 3. ALGORITMA REKONSILIASI TANPA ID SUMBER

Desain dua lapisan: (A) **identitas internal UUID** transaksi; (B) **identitas kejadian dari import** seperti `(batch_id, sheet_name, source_row_number)` unik dalam batch, plus fingerprint ter-normalisasi sebagai kandidat pencocokan. TIDAK ada `UNIQUE(fingerprint)` global.

Tahapan:
1. Simpan metadata import batch dan checksum sumber; re-upload file identik tidak boleh menggandakan transaksi.
2. Staging semua raw rows dan nilai dinormalisasi; bandingkan dengan transaksi existing menggunakan scope dataset, waktu, bank, lokasi, jenis, rekening (jika valid), uang/denom, inflow/outflow, nilai, lembar, plus fingerprint.
3. Untuk snapshot historis yang berulang, lakukan rekonsiliasi **multiset/occurrence count** per signature pada scope yang terverifikasi, bukan sekadar `set(signature)`, sebab transaksi identik boleh muncul lebih dari sekali. Jangan menyimpulkan suatu kejadian baru hanya dari urutan baris atau tanggal paling akhir.
4. Jika match pasti menurut provenance dan aturan yang terdokumentasi => `ALREADY_IMPORTED`/skip; jika baru dan tidak ambigu => `NEW_VALID` lalu commit; jika kandidat lebih dari satu/identitas tidak pasti/field berubah => `NEEDS_REVIEW`; jika format tidak valid => `INVALID`.
5. Pada `NEEDS_REVIEW`, Admin berizin dapat `SKIP_AS_EXISTING`, `CREATE_NEW`, `UPDATE_SELECTED_EXISTING`, `DEFER`, dengan alasan dan diff visual. Untuk `UPDATE`, wajib memilih UUID transaksi target yang benar.
6. Bila sumber tidak jelas apakah snapshot lengkap atau incremental, **jangan** melakukan replace periode otomatis. Penggantian periode hanya dengan pilihan scope eksplisit, konfirmasi kelengkapan sumber, diff, backup logical/versi, dan audit.
7. Simpan transaksi baris valid secara atomik per unit batch/chunk yang dipilih; allow partial success dengan status jelas. Pakai constraint DB, transaksi dan penguncian yang cukup untuk mencegah double import saat dua admin bekerja bersamaan.
8. Soft deleted records tetap dipertimbangkan dalam rekonsiliasi agar data yang pernah dihapus tidak diam-diam dibuat aktif kembali. Pulihkan hanya lewat workflow yang berizin.
9. Bila status berubah sesudah verifikasi, hitung ulang agregasi internal dan terapkan kebijakan publikasi; jangan publish pending/invalid.

Dokumentasikan **apa yang pasti dan apa yang heuristik**. Jangan tampilkan algoritma sebagai mampu mengidentifikasi transaksi secara sempurna ketika sumber tidak memiliki ID unik.

## 4. DATABASE POSTGRESQL — RANCANGAN DAN CONSTRAINT

Pakai migrasi Django, default UUID primary key untuk record transaksi/batch/verifikasi/publication, foreign key nyata, index, check constraint, timezone-aware timestamps, dan `DecimalField(max_digits=20, decimal_places=0)` atau lebih besar bila dibuktikan perlu. Semua nominal dalam **Rupiah utuh**, tanpa float; format juta/miliar hanya pada view.

Minimal entitas/tabel (boleh pecah/gabung bila ada alasan kuat dan dokumentasikan di ERD):
- `users`/custom Django user; `roles` dan `permissions` via Django auth/groups plus permission assignments per-user, jangan membuat mekanisme RBAC ganda yang bertentangan.
- `banks` (kode/nama/alias), `service_regions` (tipe MANADO/SKM, source code, canonical name), `denominations` (kode/nominal/validity jika perlu), `money_types` bila benar perlu master terpisah.
- `cashflow_transactions` (UUID, transaction_date, bank, region, source business fields, source transaction type, money type, denomination, account as **masked/restricted string**, inflow_amount, outflow_amount, pieces, raw/source provenance, fingerprint, status, soft_deleted_at/by/reason, created/updated metadata). Pilih model inflow/outflow terpisah atau amount+direction **secara konsisten**, jangan dua representasi mutable yang bisa bertentangan. Jika menyimpan keduanya, constraint/check pastikan valid. Netflow derived, bukan nilai baris utama yang diedit manual.
- `import_batches` (file checksum, uploaded_by, scope, mode, status counts, processing timestamps, errors, private path); `import_rows` (batch FK, sheet, row number, raw JSONB, normalized JSONB, fingerprints, stage/match/validation status, linked transaction FK optional; unique [batch,sheet,row]); `duplicate_matches` (candidate transaction + evidence/score/reason); `verification_decisions` (decision, reason, by, at, target FK). Bisa menambahkan `import_batch_events`.
- `transaction_revisions`/audit snapshots old/new, `audit_logs` append-only untuk operasi security-sensitive; jangan simpan password, token atau full account number dalam log.
- `cashflow_estimates` dan `estimate_import_batches` dengan status `UNCONFIGURED` sampai template disetujui; masa berlaku, sumber, scope, dan schema mapping version.
- `feature_flags`/`system_settings` dengan default `automatic_estimation_enabled=false`, `publication_mode=MANUAL`, public filter bank disabled, public menu visibility; audit semua perubahan.
- `publication_versions` (id, status, published_at/by, source cutoff, version metadata, checksum, parent version), `published_cashflow_aggregates` (version FK, period, region, denomination/money type hanya jika aman, inflow, outflow, count), `published_estimates` hanya bila ada data/approval. `current_publication_version` pointer atomik dengan rollback audit.

Rancang SQL indexes untuk tanggal, bank, wilayah, status deletion, scope import, dan versi publikasi. Tulis dan uji migrations serta rollback/forward. Di halaman internal sediakan pagination server-side, sort/filter dan query yang tidak N+1. Database production tidak diekspos langsung ke internet.

## 5. UI/UX — DESIGN COMMUNICATES INFORMATION

**Bahasa UI Indonesia, zona Asia/Makassar (WITA) untuk presentasi**; simpan timestamp UTC timezone-aware. Tanggal Rupiah/angka locale `id-ID`, angka negatif jelas, tooltip singkat menjelaskan istilah. Gunakan **Plus Jakarta Sans**, fallback font sans-serif, **light mode**, dominan biru untuk Admin, desktop-first tetapi responsif mobile. Ikuti WCAG praktik dasar: warna bukan satu-satunya pembeda, kontras cukup, keyboard focus, semantic headings, ARIA jika perlu, grafik punya ringkasan teks/tabel yang setara.

**Branding wajib** pada Public: header putih/minimalis, **logo BI di kiri** (gunakan hanya aset resmi yang diberikan/diizinkan; sementara tampilkan placeholder netral, jangan membuat logo imitasi), di kanan logo teks:
- `Dashboard Cashflow EKU` — **bold**, visual utama.
- `Estimasi Kebutuhan Uang` — **light** sebagai subjudul.
Di **pojok kanan atas** tombol/link `Masuk Admin` ke `/admin/login/` (atau path konsisten pilihanmu). Jangan menampilkan username/akun internal pada Public.

**Public**: jauh lebih sederhana daripada Admin, tanpa sidebar. Gunakan hierarki visual dan prinsip visual communication: urutan Header → penjelasan periode/data terakhir diperbarui → filter → 4 KPI (Inflow, Outflow, Netflow, Transaksi) → grafik utama → tren/pecahan/pola musiman → tabel wilayah → estimasi (jika tersedia) → sumber/definisi data. Navigasi tab `Ringkasan`, `Tren`, `Pecahan`, `Pola Musiman`, `Estimasi` dengan feature flag per menu. Perlihatkan informasi paling penting pada layar awal; konten detil progressive disclosure. Hindari dekorasi berlebihan, ilustrasi tidak relevan, atau pie chart yang tidak informatif.

**Admin**: mengikuti referensi dashboard biru yang dikirim user, dengan **sidebar** dan header/summary cards biru: Dashboard, Data Cashflow, Import Excel, Verifikasi Data, Estimasi Excel, Publikasi, Arsip/Soft Delete, Manajemen Pengguna, Audit Log, Pengaturan. Sembunyikan menu tanpa izin, tetapi otorisasi sesungguhnya di backend. Gunakan cards statistik dan ECharts (grouped bars inflow vs outflow; time series; distribusi denominasi; seasonality heatmap jika datanya cukup), tabel profesional, skeleton/loading/error/empty states, breadcrumbs, konfirmasi operasi berbahaya, akses keyboard. Status penting (pending verifikasi, stale publish, import parsial) lebih terlihat daripada sekadar ornamen.

**Referensi screenshot user**:
1. Dashboard cashflow contoh: KPI Rp, grafik inflow/outflow bulanan, tabel per wilayah, tabs Ringkasan/Tren/Pecahan/Pola Musiman.
2. Referensi biru "Analyca": inspirasi palet dan UI Admin sidebar/cards, **bukan** konten/metrik sales.
3. Screenshot "Presensi Magang": inspirasi **header BI** (logo kiri, nama sistem + subjudul, akses akun kanan), **bukan** teks Presensi Magang, nama pengguna, atau data magang.

Warna sementara (bukan warna resmi BI): `#1976E9` primary, `#1054AB` deep blue, `#78B6F5` light blue, `#EAF2FC` subtle background, `#FFFFFF` surface, `#1E293B` heading. Bisa sesuaikan kontras/accessibility tanpa mengubah prinsip dominan biru.

## 6. LOGIKA ANALITIK DAN KONSISTENSI

- Agregasi pada data aktif tervalidasi internal dan pada **publication version yang aktif** untuk public; sumber harus dipisahkan secara eksplisit.
- Inflow/Outflow/Netflow = nilai exact `Decimal` di backend; YoY/MoM sebanding waktu, tanpa division-by-zero; `N/A` jika tidak ada baseline. Grafik jangan menampilkan 0 palsu saat sebenarnya missing.
- Grup tanggal harian/bulanan/tahunan/custom, wilayah, pecahan, jenis uang; tampilkan cakupan filter yang sedang aktif dan satuan (Rp/Juta/Miliar).
- Pola musiman **deskriptif** dari tahun-tahun sebelumnya dan disertai catatan jumlah observasi/keterbatasan, jangan disebut proyeksi.
- Jika export public diaktifkan, query dan isi export berasal dari tabel publikasi, bukan database internal langsung. Rate limit endpoint export/API public dengan wajar.

## 7. KEAMANAN DAN TATA KELOLA

- Anggap project berhubungan dengan data operasional keuangan; terapkan least privilege, audit trail, CSRF protection, XSS-safe template, SQL parameterization/ORM, secure file uploads, HTTPS, secure cookies, `DEBUG=False` pada prod, allowed hosts dan CORS ketat, secure headers, cache-control untuk data privat, rate limiting, log redaction.
- Jangan mengekspos raw Excel, rekening, data bank, metadata audit, file storage, atau endpoint Admin dalam public API. Gunakan server-side DTO/projection allowlist.
- Cegah CSV formula injection untuk nilai seperti `=`, `+`, `-`, `@` dari sel teks yang diekspor; tes.
- Audit perubahan permission, import, verifikasi, edit, soft delete/restore, bulk, publikasi, rollback, fitur dan login sensitif. Sertakan siapa, kapan, apa dan before/after minimal. Jangan menyimpan password/token.
- Implementasi autentikasi production yang kuat; dukungan MFA disiapkan dengan desain extensible, tetapi jelaskan jika belum aktif. Jangan hardcode user/password admin. Sediakan management command untuk inisialisasi superadmin dari environment dengan prosedur aman.
- `publication_mode=AUTO` tetap tunduk pada kebijakan allowlist data, validasi dan kelayakan; apabila status belum jelas, jangan terbitkan.
- Penggunaan logo, hosting eksternal, data asli, aturan retensi, scope publikasi, serta persetujuan akhir harus disahkan oleh pemilik sistem/otoritas TI lembaga. Build boleh diuji dengan data dummy, **jangan deploy publik dengan data riil tanpa persetujuan**.

## 8. PROJECT STRUCTURE DAN KUALITAS ENGINEERING

Gunakan satu Django modular monolith dengan contoh apps: `accounts`, `masterdata`, `cashflow`, `imports`, `verification`, `estimates`, `publications`, `dashboard`, `audit`, `core`. Gunakan template/component partial untuk pemakaian ulang; HTMX untuk interaksi dinamis dan ECharts untuk grafik. Sediakan `pyproject.toml` atau dependency lock yang jelas, formatting/lint, `.env.example` tanpa secrets, `.gitignore`, serta pipeline tes.

Tulis test fixtures dan automated tests untuk:
- import workbook dummy bila file tersedia; serial Excel date, leading zeros, nama kolom alias, nilai pecahan tidak konsisten, data yang hanya inflow;
- import ulang file identik tidak menambah ganda; data historis+baru ditambah dengan benar; dua kejadian identik yang benar-benar berbeda tidak dibuang; uncertain matching masuk antrean;
- partial import menyimpan valid tetapi menahan ambiguous/invalid; hanya Admin Staf berizin dapat memverifikasi; update existing memerlukan selected UUID;
- replace periode butuh konfirmasi scope dan kelengkapan, tidak menghapus data lain; soft delete/restore dan bulk permission;
- seluruh kombinasi RBAC wajib server-side; tidak ada unauthorized publish/verify/delete/restore;
- manual publication tidak auto-refresh; automatic hanya eligible data; immutable version, rollback atomik; public API/export tidak membocorkan nama bank/account/raw data;
- perhitungan cashflow, netflow negatif, MoM/YoY saat baseline nol, filter range, tanggal, empty states;
- estimasi Excel tanpa format tidak menghasilkan angka palsu; automatic estimation OFF tidak tampil; ON tanpa metode hanya UI informational;
- upload Excel bermasalah, ukuran besar, keamanan nama file, formula injection, concurrency dan recoverable failures;
- halaman Public/Admin responsif dan keyboard accessible; smoke test endpoint, API dan render minimal.

Gunakan pytest/pytest-django atau Django TestCase yang konsisten. Buat seed dataset **sintetis** untuk demo, beri label conspicuous "DATA DUMMY" hanya pada dev/staging, tidak membuat angka palsu di production.

## 9. DEVELOPMENT, DOCKER, STAGING, PRODUCTION

**Development host: macOS**. Aplikasi harus berjalan lokal dengan Docker Compose (Django web + PostgreSQL; reverse proxy Nginx untuk konfigurasi prod/staging bila sesuai). Pisahkan environment dev/staging/prod, gunakan variables/config, non-root container jika praktis, volumes untuk database/private uploads, health checks, named volumes, migration job, static assets, dan instruksi reproducible.

Hosting **akan ditentukan/disediakan lembaga**, mungkin eksternal tetapi belum ada penyedia, OS/server specs, domain, persetujuan lokasi data atau kebijakan firewall. Maka:
- jangan spesifik mengunci provider cloud;
- buat `compose.yaml`, `compose.override` atau profile dev, contoh prod compose, Dockerfile, konfigurasi `gunicorn` dan Nginx; dokumentasikan opsi database managed eksternal vs postgres container tanpa mengubah kode inti;
- ada checklist DNS, HTTPS/TLS, allowed hosts, domain/cookie, credential & secret manager, backup encrypted, restore drill, monitoring, log rotation, retention, firewall, object storage privat (jika dibolehkan), indexing, resource sizing, dan prosedur update/rollback deployment;
- backup database dan arsip Excel disesuaikan kebijakan lembaga, tes restore;
- **staging** dengan data sintetis/sanitized sebelum production;
- dokumentasi `docs/deployment.md`, `docs/operations.md`, `docs/backup-restore.md`, `docs/security-checklist.md`, `README.md` (macOS quickstart).
- jangan membuat klaim "production secure" atau "siap digunakan BI secara resmi" hanya karena test lulus. Tegaskan review IT/pentest/approval gate.

## 10. URUTAN IMPLEMENTASI DAN DELIVERABLE MANDATORI

Laksanakan milestone berikut. Di akhir setiap milestone: kode bekerja, migrasi jalan, tes terkait dijalankan, ringkasan status, risiko dan next steps. Jika memungkinkan, lanjut otomatis sampai seluruh milestone selesai.

**M0 — Repo audit + specifications**: baca bahan tersedia; requirements traceability matrix yang memisahkan `FINAL`, `DEFAULT AMAN`, `PENDING APPROVAL`, `PENDING INPUT`, `DEFERRED`; arsitektur dan ERD; inspect workbook; definisikan acceptance criteria dan risiko.

**M1 — Scaffold + local environment**: project Django, Docker Compose PostgreSQL, UI Tailwind, ECharts, settings per environment, auth/login/logout, root Public dan Admin shell, seed synthetic terpisah.

**M2 — Database & permission**: custom user/roles/permissions granular, master banks/regions/denoms, cashflow transaction model, constraints/index, audit, soft delete/restore, tests.

**M3 — Excel import & reconciliation**: parser adapters untuk 2 sheet transaksi + DENOM, staging raw, mapping, normalized data, checksums, validasi, row matching, partial import, verifikasi admin, update individual/period, audit, tests dengan file nyata jika tersedia.

**M4 — Admin operating UI**: dashboard, input/edit manual, daftar cashflow filter/search/pagination, import preview, queue verification, arsip/restore, permission editor, import history, audit.

**M5 — Public publication layer**: data projection agregat per wilayah, atomic immutable snapshots, manual/auto switching, staff publish permission, rollback, feature flags menu, export scoped, tests keamanan.

**M6 — Analytics & visual UI**: KPI, ECharts time series/bar, denom breakdown, seasonality descriptive, YoY/MoM, filter harian/bulanan/tahunan/custom, visual hierarchy Admin/Public, responsive/accessibility, export Excel CSV PDF.

**M7 — Estimasi + settings**: modul estimasi Excel berkontrak fleksibel/empty state menunggu file riil; toggle automatic estimation OFF; pengaturan visibilitas/approval yang tidak mengarang hasil forecasting.

**M8 — Production readiness**: tes integrasi/end-to-end dan security negative tests, lint, performance basic, backup/restore instructions, env templates, deployment docs, final operator runbook, checklist persetujuan TI.

**Output akhir yang wajib diberikan:** project files dan perintah yang dapat dieksekusi, ERD/skema + migrasi, dokumentasi peran & permission, mapping Excel, laporan pengujian real (pass/fail/skip dengan alasan), screenshot atau deskripsi verifiable dari halaman jadi, daftar fitur selesai vs scaffold vs blocked, langkah macOS run lokal, langkah staging/prod, security review checklist, keputusan yang memerlukan persetujuan pimpinan/TI. Lakukan self-review sebelum menyatakan selesai.

## 11. ACCEPTANCE CRITERIA (DEFINITION OF DONE)

1. Aplikasi berjalan dengan Docker Compose di macOS, setup terdokumentasi, database migrate berhasil, login dan 2 UI berbeda berfungsi.
2. Dashboard Public tidak membutuhkan login dan tidak memiliki endpoint untuk mengakses data identitas bank/rekening/transaksi mentah. Semua data public berasal dari published version yang aktif.
3. Admin bisa import dummy Excel sesuai kolom aktual, memfilter bad data, mencegah reupload duplicate, menambahkan data baru, menahan ambigu, dan memverifikasi dengan izin.
4. Admin bisa menambah/edit manual, soft delete/restore, bulk dengan izin, histori audit lengkap; mode update transaksi/replace periode aman.
5. KPI benar: inflow, outflow, netflow, transaksi, wilayah, period filter; MoM/YoY dan grafis valid; tidak ada estimasi palsu.
6. Publikasi manual/otomatis, kontrol per-user `publish_manual`, immutable snapshot dan rollback bekerja; audit tersedia.
7. Tampilan Public minimalis dengan header logo BI **bila aset resmi telah tersedia**, teks bold `Dashboard Cashflow EKU`, subteks light `Estimasi Kebutuhan Uang`, tombol kanan atas `Masuk Admin`, menu sesuai spesifikasi. Admin biru dan sidebar; font Plus Jakarta Sans; responsive.
8. Estimasi Excel belum memerlukan asumsi format yang palsu; auto-estimation OFF dan tidak menghitung ramalan tanpa metode disetujui.
9. Tes termasuk RBAC security dan partial import lulus; dokumentasi deploy portable, backup/restore dan persetujuan TI jelas.
10. Hindari menandai keseluruhan fitur sebagai COMPLETE jika dependensi data/file/approval belum ada. Laporkan `IMPLEMENTED`, `SCAFFOLDED`, `PENDING INPUT`, atau `BLOCKED BY APPROVAL` secara jujur.

## 12. HAL YANG DITUNDA / TIDAK BOLEH DIANGGAP FINAL

- Format, kolom, rumus, periode dan cakupan **Excel estimasi kebutuhan uang yang asli** belum diberikan; jangan membuat hasil estimasi pengganti.
- Rumus/model **Estimasi Otomatis** belum disahkan; OFF dan non-executable untuk prediksi nyata.
- Kebijakan publikasi/klasifikasi data, logo resmi, domain, jenis server cloud, wilayah penyimpanan, SSO, MFA mandatory, retensi dan backup final harus dikonfirmasi oleh pihak berwenang.
- Data public per bank **tidak diizinkan secara default**; bila ingin ekspansi nanti, perlu persetujuan terpisah dan tes kebocoran data ulang.
- Sampel Excel dummy bukan sumber kebenaran operasional; data quality issues harus ditangani, bukan dihaluskan.

**MULAI SEKARANG**: (1) inspeksi repo dan berkas Excel/screenshot yang tersedia, (2) tuliskan ringkasan pemahaman serta daftar asumsi/gate, (3) buat rencana milestone dan file spesifikasi, lalu (4) bangun M1 dan teruskan sesuai urutan sampai selesai. Jangan berhenti hanya dengan memberi saran atau menuliskan kode contoh. Pada tiap milestone, laporkan status tes dengan bukti nyata. Jika file wajib tidak tersedia, minta input tersebut dan kerjakan komponen lain yang tidak bergantung padanya tanpa mengarang data.
