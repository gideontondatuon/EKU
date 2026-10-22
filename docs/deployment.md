# Deployment portable untuk evaluasi

Hosting/provider/domain/data residency belum ditetapkan. Dokumen dan Compose adalah rancangan yang dapat dievaluasi TI; tidak memberi persetujuan membuka data operasional ke publik. Target Python3.12, PostgreSQL17, Django5.2; deployment Linux menggunakan Gunicorn dan Nginx. Mac digunakan untuk development.

## Prasyarat dan environment

1. Selesaikan review `security-checklist.md`, klasifikasi data, backup/restore, domain/TLS dan approval publikasi.
2. Gunakan host container yang kompatibel dan terpelihara. Docker Compose v2 diperlukan untuk health dependency dan migration job. Host audit awal belum mempunyai Docker; smoke deployment container masih perlu dilakukan.
3. Tetapkan image release/tag/digest setelah build dan vulnerability review. Contoh image tags di Compose bukan jaminan immutable supply chain; pin digest saat release disetujui.
4. Buat `.env.production` di host dengan mode0600 atau inject dari secret manager yang disetujui. File tidak masuk Git/image. `DJANGO_SECRET_KEY` acak ≥50 karakter; `DATABASE_URL` memakai credential production terbatas; `DJANGO_ENV=production` atau `staging`; `DJANGO_DEBUG=0`.
5. Set `DJANGO_ALLOWED_HOSTS` ke domain nyata plus `localhost` untuk health probe. Set `DJANGO_CSRF_TRUSTED_ORIGINS` ke origin HTTPS lengkap, termasuk port bila memakai8443. Tidak memakai wildcard domain.
6. `PRIVATE_ROOT=/app/.private` pada volume privat. Backup harus mencakup volume ini dan DB. Public media route tidak boleh diarahkan ke volume tersebut.

## Staging sebelum production

Staging memakai database dan credential terpisah, data sintetis atau sanitasi berizin, dan banner DATA DUMMY bila memakai seed. Gunakan `DJANGO_ENV=staging`; secure cookies/HTTPS tetap aktif. Tidak ada auto-bootstrap akun atau auto-seed saat startup.

`compose.production.yaml` adalah file **standalone**, bukan overlay dev. Service DB tidak dipublikasikan; web hanya reachable di network container. Nginx memetakan default loopback8080/8443 dengan TLS. Isi `TLS_CERT_PATH` dan `TLS_KEY_PATH` sebagai path absolut host menuju chain/key; key permission dibatasi. Untuk akses dari jaringan lembaga, TI menyesuaikan bind/port/firewall dan redirect Nginx secara konsisten. Default redirect mengarah8443; bila memakai443 standar ubah `deploy/nginx.conf` ke URL tanpa`:8443` dan mapping port menjadi443.

```sh
docker compose --env-file .env.production -f compose.production.yaml build
docker compose --env-file .env.production -f compose.production.yaml up -d
docker compose --env-file .env.production -f compose.production.yaml ps
docker compose --env-file .env.production -f compose.production.yaml exec web python manage.py check --deploy
docker compose --env-file .env.production -f compose.production.yaml exec web python manage.py showmigrations
```

File env default untuk service adalah `.env.production`; apabila namanya berbeda, set `EKU_ENV_FILE` juga. Nilai `DATABASE_URL` harus menunjuk `db:5432` untuk DB container. Gunakan password URL-safe atau URL-encode karakter khusus. Hindari menampilkan hasil `docker compose config` lengkap ke log/chat karena interpolasi dapat memuat secret.

Bootstrap akun dilakukan dengan `bootstrap_admin` dan environment `EKU_ADMIN_USERNAME`, `EKU_ADMIN_EMAIL`, `EKU_ADMIN_PASSWORD`. Lakukan sekali secara eksplisit; hapus secret bootstrap dari environment/file setelah berhasil. Tidak ada default credential. Seed dilarang di production.

Smoke staging wajib memeriksa public kosong/versi, login/logout/CSRF, import dummy parsial, unauthorized endpoints, publish demo, export, rollback, health, browser asset requests dan private path rejection. Test automated yang lulus tidak menggantikan pengujian container/TLS/firewall.

## Pilihan database eksternal yang disetujui

Kode aplikasi hanya bergantung pada `DATABASE_URL` dan `DATABASE_SSLMODE`, sehingga dapat memakai PostgreSQL17 eksternal tanpa perubahan domain. Untuk opsi tersebut TI membuat varian Compose yang menghapus service/dependency `db`, memberikan web/migrate route ke host DB, mengatur firewall private network dan TLS verify-full, serta menambahkan CA trust sesuai penyedia yang disetujui. Default `backend.internal: true` sengaja membatasi egress; varian eksternal harus mengatur network yang sesuai, bukan menganggap contoh default dapat langsung menjangkau internet.

Pisahkan credential migrator (DDL) dan runtime (DML) bila kebijakan TI memerlukannya. Tidak memberi runtime hak superuser/CREATE DATABASE. CI/development membutuhkan CREATE DATABASE untuk test DB; itu bukan izin runtime production.

## Update dan rollback deployment

- Simpan image release sebelumnya dan backup DB+private uploads dengan timestamp/cutoff yang sama sebelum migration. Uji migration/rollback schema pada salinan staging terlebih dahulu.
- Tinjau migration apakah backward-compatible. Stop proses import/mutasi selama maintenance bila perubahan tidak kompatibel. Jangan menjalankan reverse migration destruktif secara otomatis.
- Deploy image baru, jalankan migration job, cek kesehatan/log tersanitasi dan smoke. Pointer publikasi tetap versi terakhir sampai ada publication baru yang eligible/disetujui.
- Rollback aplikasi ke image sebelumnya hanya jika schema kompatibel. Bila tidak, lakukan restore terencana dari backup ke environment terpisah, verifikasi, lalu cutover sesuai persetujuan. Publication rollback bukan database restore.

## Checklist infrastruktur

DNS dan TLS renewal; allowed hosts/CSRF origin; firewall ingress/egress; DB private network; least privilege; secret rotation; encrypted backup dan restore drill; monitoring health/disk/latency/error; log rotation tanpa query/credential; retensi sumber/audit; sizing CPU/RAM/storage berdasarkan load test; clock synchronization; patch/image review; prosedur incident dan update; lokasi penyimpanan disetujui. Nilai RPO/RTO, retensi dan ukuran server belum diada-adakan.
