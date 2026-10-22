# Backup dan restore

RPO/RTO, jadwal, retensi, enkripsi dan lokasi penyimpanan harus disahkan TI/pemilik data. Jangan mengarang nilai final. DB dan arsip Excel privat adalah satu himpunan pemulihan; backup DB saja tidak cukup untuk provenance import. Secret key/credential disimpan melalui mekanisme terpisah yang disetujui, bukan dimasukkan ke dump/log.

## Backup konsisten

1. Catat release aplikasi/schema, waktu UTC+WITA, scope, source cutoff dan current publication version. Hentikan sementara mutasi/import bila tidak ada mekanisme consistent snapshot DB+file.
2. Buat PostgreSQL custom-format dump dengan pg_dump17. Gunakan credential backup terbatas melalui `.pgpass` mode0600 atau secret environment; jangan menulis password literal di command/history.
3. Arsipkan `.private/uploads`/volume private yang dirujuk DB, tanpa `pgdata`, file password atau seluruh `.env`. Catat checksum setiap arsip dan manifest file sumber.
4. Enkripsi backup menggunakan sarana lembaga, verifikasi checksum, simpan pada lokasi yang disetujui dan terpisah dari host aktif. Catat sukses/gagal dan uji restore berkala.

Contoh backup lokal **untuk evaluasi** setelah environment PGHOST/PGPORT/PGUSER/PGDATABASE disetel ke cluster proyek dan credential tersedia aman:

```sh
umask 077
mkdir -p artifacts/backup
pg_dump --format=custom --no-owner --file=artifacts/backup/eku-evaluation.dump
tar -czf artifacts/backup/eku-uploads.tar.gz -C .private uploads
shasum -a 256 artifacts/backup/eku-evaluation.dump artifacts/backup/eku-uploads.tar.gz
```

Pastikan direktori uploads sudah ada. Command tersebut belum mengenkripsi backup; jangan memindahkan dump data riil sebelum enkripsi/kebijakan disetujui. Native project memakai host127.0.0.1/port55432/databaseeku. Credential berada privat; tidak perlu dicetak untuk backup.

Contoh DB container development (command berjalan di container yang sudah mempunyai credential DB):

```sh
docker compose --env-file .env.docker exec -T db sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" --format=custom --no-owner' > artifacts/backup/eku-evaluation.dump
```

Dump ditulis ke host dengan umask077. Gunakan backup job resmi untuk volume privat: mount read-only, arsipkan uploads, dan jangan publikasikan volume melalui web. Jangan menyalin direktori live PostgreSQL sebagai pengganti pg_dump tanpa prosedur physical backup yang benar.

## Restore drill terpisah

Jangan restore langsung menimpa database aktif. Buat database baru misalnya `eku_restore_drill` pada cluster evaluasi dan direktori upload terpisah. Test drill menggunakan data sintetis/sanitized. Pastikan nama target bukan database operasional.

```sh
createdb eku_restore_drill
pg_restore --no-owner --no-privileges --exit-on-error --dbname=eku_restore_drill artifacts/backup/eku-evaluation.dump
mkdir -p artifacts/restore-private
tar -xzf artifacts/backup/eku-uploads.tar.gz -C artifacts/restore-private
```

Hanya ekstrak arsip yang dibuat sendiri dan diverifikasi; periksa daftar entry sebelum ekstraksi agar tidak ada path traversal. Jalankan aplikasi salinan dengan DATABASE_URL ke target drill dan PRIVATE_ROOT ke direktori hasil restore. Jangan mengganti `.env` aktif untuk drill. Jalankan check/migration status, bandingkan counts/status/Decimal totals/UUID versi/checksum sumber, lalu smoke public/login/import history/permission/private-file rejection. Verifikasi rollback publikasi tetap tidak mengubah transaksi internal.

Catat command, waktu, hasil, jumlah record, checksum dan limitasi. Bila Docker belum tersedia, drill native PostgreSQL dapat membuktikan pemulihan logis DB; itu tidak membuktikan pemulihan volume/container/TLS production. Test restore yang belum dijalankan harus tetap tercatat pending.

## Recovery production

Pemulihan produksi memerlukan keputusan penanggung jawab insiden, point-in-time/cutoff yang disetujui, validasi backup, restore ke host/database terpisah, pemeriksaan integritas dan smoke, lalu cutover dan monitoring. Rencana kehilangan data sejak backup harus dinyatakan, bukan diasumsikan nol. Simpan bukti sebelum cleanup; purge backup hanya mengikuti retensi resmi.
