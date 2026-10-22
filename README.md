# Dashboard Cashflow EKU

Dashboard cashflow Unit PUR KPw Bank Indonesia Provinsi Sulawesi Utara. Stack: Django 5.2 LTS, Python 3.12, PostgreSQL 17, template/HTMX, Tailwind dan ECharts. UI/dokumentasi berbahasa Indonesia; tanggal WITA; nominal Rupiah utuh Decimal.

**Hasil pembangunan ini untuk evaluasi.** Data operasional, publikasi riil, hosting, logo dan kebijakan retensi memerlukan persetujuan lembaga. Format Excel estimasi asli belum tersedia; estimasi otomatis tetap OFF/non-executable. Logo sementara adalah placeholder netral, bukan logo resmi. Legacy `../eku_dashboard` tidak dimigrasi.

## Menjalankan lokal di macOS Intel

Jalankan semua command dari folder `Dashboard Cashflow EKU`. Diperlukan Python **3.12** dan binary PostgreSQL **17** (`initdb`, `pg_ctl`, `psql`, `createdb`) dalam PATH. Python bawaan macOS3.9 bukan runtime proyek. Docker dan Node tidak diperlukan untuk jalur native ini; CSS/JS/font lokal telah disiapkan, sedangkan perubahan CSS dapat dibangun dengan `scripts/build_css.sh` sesuai prasyaratnya.

Jika `.venv` sudah disiapkan dalam workspace, gunakan langsung. Untuk checkout baru:

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/local_database.py
.venv/bin/python manage.py migrate
.venv/bin/python manage.py check
```

`local_database.py` hanya menyiapkan cluster proyek di `.private/pgdata`, bind `127.0.0.1:55432`, database `eku` dan credential acak privat. Script membuat `.env` jika belum ada dan tidak mengganti konfigurasi yang sudah ada. **Jangan menyalin `.env.example` ke `.env` sebelum menjalankan script lokal.** Jika `.env` sudah tersedia, pastikan URL menunjuk cluster yang dimaksud; jangan mencetak isinya dalam laporan/chat. PostgreSQL yang sudah ada di sistem tidak diganti.

Buat akun pribadi dengan management command; contoh berikut untuk Terminal zsh. Password minimal mengikuti validator aplikasi dan tidak ditulis sebagai literal dalam history:

```sh
export EKU_ADMIN_USERNAME='admin-pur'
export EKU_ADMIN_EMAIL='alamat-internal-anda@example.invalid'
read -rs 'EKU_ADMIN_PASSWORD?Password admin (input disembunyikan): '
export EKU_ADMIN_PASSWORD
.venv/bin/python manage.py bootstrap_admin
unset EKU_ADMIN_PASSWORD
.venv/bin/python manage.py runserver 127.0.0.1:8000
```

Gunakan email yang sebenarnya saat menyiapkan akun; `example.invalid` di atas hanyalah placeholder. Public: `http://127.0.0.1:8000/`; Admin: `http://127.0.0.1:8000/admin/`; login: `/admin/login/`; health: `/health/`. Runserver hanya untuk development. Jangan membuka port ke internet untuk data riil.

Seed demo opsional, hanya development/staging:

```sh
.venv/bin/python manage.py seed_demo --confirm-dummy
```

Data demo wajib berlabel **DATA DUMMY**. Workbook `references/SETBAY_DUMMY.xlsx` adalah fixture cashflow, bukan template estimasi dan bukan data produksi. Jangan auto-import seluruh delapan baris sebagai valid: dua baris memiliki konflik pecahan/nominal.

Untuk menghentikan cluster lokal proyek setelah aplikasi dihentikan:

```sh
pg_ctl -D "$PWD/.private/pgdata" stop -m fast
```

Jangan menghapus `.private/pgdata` untuk sekadar memulai ulang aplikasi.

## Docker Compose development

Konfigurasi tersedia; **Docker belum tersedia di host audit awal sehingga build/up belum dapat diklaim teruji**. Instal runtime container yang kompatibel dengan macOS Anda dan disetujui TI; tidak perlu mengganti macOS atau menjalankan installer sistem tanpa keputusan sendiri.

Salin `.env.example` menjadi `.env.docker`, ubah secret Django dan password PostgreSQL menjadi nilai acak, lalu batasi akses file. Compose dev menyusun URL DB dari POSTGRES_* dan tidak membuka port database ke host. Jangan memakai credential contoh untuk deployment.

```sh
cp -n .env.example .env.docker
chmod 600 .env.docker
docker compose --env-file .env.docker build
docker compose --env-file .env.docker up -d
docker compose --env-file .env.docker ps
docker compose --env-file .env.docker exec web python manage.py check
```

Service `migrate` menunggu DB sehat; web menunggu migration berhasil. `http://127.0.0.1:8000` hanya loopback. Bootstrap account dilakukan eksplisit dengan environment `EKU_ADMIN_*` pada command, bukan default username/password. Gunakan `docker compose --env-file .env.docker down` untuk berhenti; **jangan menambahkan `-v`** kecuali sengaja menghapus database dan arsip yang sudah dibackup.

## Tes dan pemeriksaan

Gunakan database khusus proyek/tes. pytest-django membuat database test; credential CI/local perlu hak CREATE DATABASE untuk tes, sedangkan runtime production tidak harus memilikinya.

```sh
.venv/bin/python manage.py makemigrations --check --dry-run
.venv/bin/python manage.py migrate
.venv/bin/python -m pytest -q -m 'not e2e'
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
```

Bukti pass/fail/skip milestone berada pada laporan pengujian yang dibuat selama eksekusi, bukan pada rencana acceptance. CI `.github/workflows/ci.yml` harus berada di root repository GitHub saat proyek diunggah; bila seluruh workspace menjadi repository, pindahkan workflow ke `.github/workflows` root. Jangan memasukkan `.env`, `.private`, credential, dump atau data operasional ke Git.

## Dokumen

- [Persyaratan dan acceptance](docs/requirements.md), [arsitektur](docs/architecture.md), [ERD](docs/erd.md), [keputusan](docs/decisions.md), [milestone](docs/milestones.md).
- [Inspeksi Excel](docs/excel-inspection.md), [inspeksi visual](docs/visual-inspection.md), [asumsi dan gate keamanan](docs/security-and-assumptions.md).
- [Deployment staging/production](docs/deployment.md), [runbook operator](docs/operations.md), [backup/restore](docs/backup-restore.md), [checklist keamanan](docs/security-checklist.md).

Data public selalu dari snapshot publikasi aktif, bukan tabel transaksi internal. Default MANUAL; perubahan internal tidak otomatis terlihat di public. Rollback publikasi hanya mengubah versi public. Lihat laporan implementasi akhir untuk membedakan fitur `IMPLEMENTED`, `SCAFFOLDED`, `PENDING INPUT` dan `BLOCKED BY APPROVAL`.


## Alur import yang disederhanakan

Buka **Import Excel**, pilih `.xlsx`, tandai bila file merupakan DATA DUMMY, lalu klik **Unggah & simpan data valid**. Halaman hasil menampilkan jumlah baris dibaca, tersimpan, transaksi lama dilewati, peringatan ringan, perlu verifikasi, dan gagal. Peringatan rekening numeric tidak menghambat cashflow yang valid; sistem tidak menebak nol depan. Pecahan baru dapat dibentuk dari referensi DENOM dan aritmetika yang konsisten, dengan audit.

**Pengaturan lanjutan** mempertahankan mode pembaruan transaksi dan penggantian periode. Penggantian periode memerlukan cakupan lengkap dan pratinjau dampak. Antrean verifikasi berada pada halaman Import Excel. Master, pengguna, audit, pemulihan, dan reset berada di Pengaturan; pemulihan juga tersedia dari Data Cashflow.

Public memakai snapshot publikasi yang sudah disetujui. Estimasi belum tersedia dan tidak muncul pada navigasi public. Logo resmi dapat dikonfigurasi melalui `BI_LOGO_STATIC_PATH=images/nama-aset-yang-diizinkan.png` setelah aset berizin ditempatkan di `static/images/`; tanpa aset, identitas netral PUR digunakan. Jangan mengekstrak logo dari screenshot referensi.

Audit dan hasil refactoring: `REFACTOR_AUDIT.md`, `REFACTOR_RESULTS.md`. Tes lengkap (termasuk browser) menggunakan `.venv/bin/python -m pytest -q`; tes browser memerlukan Google Chrome lokal. `scripts/fix_denom.py` sekarang hanya menginspeksi, tanpa mengubah workbook atau merekonstruksi nol depan.
