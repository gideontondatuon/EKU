# Checklist evaluasi keamanan dan persetujuan TI

Checklist ini sengaja belum diberi tanda selesai. Isi hanya dengan evidence dan penanggung jawab setelah pemeriksaan nyata. Unit tests tidak menggantikan pentest, audit infrastruktur atau persetujuan lembaga.

## Aplikasi dan data

- [ ] Traceability acceptance/test report M0–M8 tersedia dengan pass/fail/skip dan scope.
- [ ] Semua mutation/export internal ditolak bagi anonymous/inactive/tanpa permission; tidak cukup menyembunyikan menu.
- [ ] CSRF, password policy, login rate-limit, session expiry/logout diuji; tidak ada akun/password default.
- [ ] Audit permission/import/review/edit/delete/restore/bulk/publish/rollback/settings/login sensitif tersedia dan tersanitasi.
- [ ] Rekening/kode leading zero tetap string; Decimal tanpa float; conflicts tidak ditimpa; soft-deleted tetap dipertimbangkan saat reconcile.
- [ ] Checksum reupload, multiset/ambiguity, partial success, explicit scope replacement dan concurrency diuji.
- [ ] Upload limit/file-content/ZIP validation/private permissions/formula cache/no-execution diuji.
- [ ] CSV/Excel formula injection ditangani; PDF/CSV/XLSX memakai filter dan scope yang sama.
- [ ] Public HTML/JSON/chart/export/cache/error tidak bocorkan bank/account/raw/audit; hanya projection versi aktif.
- [ ] Snapshot immutable, pointer atomic, rollback terpisah dari transaksi internal dan manual/auto gate diuji.
- [ ] Dummy nonproduction jelas berlabel; seed ditolak production; tidak ada auto-import legacy.
- [ ] Estimasi tanpa format/metode tidak membuat hasil; automatic estimation default OFF dan tidak executable.
- [ ] Aset HTMX/ECharts/Tailwind/font lokal dan lisensinya ditinjau; browser tidak mengirim data ke CDN eksternal.
- [ ] Responsif/keyboard/focus/label/kontras/tabel alternatif grafik diperiksa pada browser nyata.

## Infrastruktur dan operasi

- [ ] Docker build/up/migrate/health/smoke benar-benar dijalankan pada host yang disetujui; image pin/digest dan dependency review tercatat.
- [ ] `check --deploy` ditinjau dengan settings production; DEBUG false; secret kuat; hosts/CSRF origin eksplisit.
- [ ] HTTPS/TLS renewal/secure cookies/HSTS/proxy trust dikonfigurasi sesuai domain, termasuk risiko HSTS subdomain/preload.
- [ ] DB tidak terbuka internet; credential runtime least privilege; akses backup/migrator terpisah bila diperlukan.
- [ ] Private uploads tidak punya URL public/Nginx alias; volume owner/permission benar; backup terenkripsi.
- [ ] RPO/RTO, retensi, monitoring, alert, log rotation, clock sync dan kapasitas ditetapkan penanggung jawab.
- [ ] Restore drill DB+file terpisah berhasil dengan counts/totals/checksums dan smoke, bukan sekadar backup command sukses.
- [ ] Staging sintetis/sanitized lolos; rollback image/schema/publication dibedakan dan prosedur diuji.
- [ ] MFA/SSO mandatory dan lifecycle akun telah diputuskan; status aktif/tidak aktif dilaporkan jujur.

## Approval pemilik sistem

- [ ] Publikasi operasional, grain tanggal/wilayah, menu/filter/export yang diizinkan dan referensi persetujuan ditetapkan.
- [ ] Ekspansi pecahan/jenis uang public disetujui terpisah jika dibutuhkan; bank/rekening public tetap tertutup.
- [ ] Template estimasi asli dan definisi scope diberikan; mapping final ditandatangani pemilik data.
- [ ] Metode estimasi otomatis divalidasi/disetujui sebelum implementasi prediksi dan publikasi hasil.
- [ ] Logo/aset BI diberikan dan penggunaannya diizinkan; screenshot bukan sumber izin/aset final.
- [ ] Hosting/provider/domain/lokasi data/firewall/object storage (jika ada) disetujui TI.
- [ ] Pentest/review keamanan dan persetujuan deployment production tersedia.

Penanggung jawab, tanggal, referensi persetujuan dan evidence dicatat dalam sistem yang disetujui. Jangan menyalin dokumen rahasia/credential ke repository hanya untuk mengisi checklist.
