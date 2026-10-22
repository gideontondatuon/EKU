# Keamanan, asumsi dan persetujuan

## Batas kepercayaan

Semua endpoint public dianggap sepenuhnya terbuka. Login Admin tidak menjadikan browser atau file upload terpercaya. Workbook merupakan input tidak tepercaya, termasuk nama file, shared string, cached formula, ZIP metadata dan XML. Source dummy hanya membuktikan struktur sampel, bukan kebenaran/kecukupan data operasional.

Public memperoleh DTO/projection allowlist dari immutable snapshot aktif. Nama bank, rekening, transaksi individual, raw staging, audit, candidate matching, path storage dan stack trace tidak boleh muncul melalui HTML/JSON/chart/export/error/cache. Filter bank hanya internal. Projection awal tanggal/wilayah; ekspansi grain menunggu persetujuan.

## Kontrol yang harus diterapkan dan diuji

| Risiko | Kontrol implementasi | Bukti yang diperlukan |
| --- | --- | --- |
| Akses/mutasi tanpa izin | Django auth/groups/user permission; pemeriksaan server pada setiap action; CSRF POST; inactive users ditolak | Negative tests setiap permission dan HTTP direct request |
| Brute-force/session theft | Rate-limit login, password validators/hash Django, secure HttpOnly SameSite cookies di prod, HTTPS, logout | Login/session tests; konfigurasi reverse proxy dipercaya hanya dari edge |
| Kebocoran public | Projection terpisah; approval gate; allowlist; cache berdasarkan version; private no-store | Scan isi HTML/JSON/CSV/XLSX/PDF termasuk secret marker fixture |
| Upload berbahaya | XLSX content/ZIP validation, limit file/rows/cells/decompression, reject macro/external link, no formula execution | Tests oversized/ZIP bomb/missing cache/filename traversal/failure recovery |
| Salah nominal atau duplicate | Decimal, constraints, staged review, checksum, provenance, multiset scoped, locks | Konflik sampel, duplicates/occurrences/concurrency tests |
| Penghapusan/replace keliru | Soft delete, independent restore/bulk perms, explicit complete snapshot scope+preview | Scope negative tests dan before/after revision |
| Publikasi tidak sah | MANUAL default, policy/approval gate, immutable snapshots, atomic pointer | Unauthorized publish/rollback, pending exclusion, atomic failure tests |
| Formula injection | Escaping teks awal `=`, `+`, `-`, `@` pada export; numeric domain tetap numeric | CSV/XLSX attack fixture; tanda netflow negatif numeric tetap benar |
| Secret/rekening dalam log | Redaction di audit/error/report, no environment dump, private source access | Audit/error assertions; jangan mencatat full account/token/password |
| Supply chain / external runtime calls | Dependency pin, CI checks, self-hosted assets, build network terpisah | Audit dependency/asset manifest dan browser request check |
| Data hilang | DB + private-file backup konsisten, encrypted storage, restore drill | Verifikasi restore database terpisah dan checksum arsip |

## Defaults dan asumsi yang terlihat

- Approval publication kosong menutup publikasi data operasional. `AUTOMATIC` tetap memerlukan eligibility dan approval. Data dummy dapat dipakai hanya nonproduction dengan label yang terlihat.
- Enam baris sampel aritmetika konsisten bukan otomatis data berizin publik. Dua baris pecahan konflik tidak otomatis dikoreksi. Tanggal update 2026 bukan bukti data lengkap sampai 2026.
- Rekening dan kode berawalan nol disimpan string. Jika Excel sudah menghilangkan nol, jangan merekonstruksi tanpa referensi sah. Rekening ditampilkan masked dan hanya tersimpan restricted bila dibutuhkan provenance.
- Migrations, tests dan backup drill harus dijalankan pada database yang dibuat untuk proyek/tes. Jangan menghapus, mengganti, atau melakukan rollback database milik sistem lain.
- Host audit memiliki Python sistem3.9.6 dan binary PostgreSQL17; Docker/Node tidak tersedia pada pemeriksaan awal. Runtime target tetap Python3.12. Keterbatasan ini wajib muncul pada laporan eksekusi, bukan disembunyikan dengan klaim container berhasil.
- Retensi belum ditetapkan: tidak menjalankan auto-purge raw files/audit/backup. Retensi sementara tanpa purge bukan kebijakan lembaga final.
- MFA/SSO belum aktif. Kerangka autentikasi harus bisa diperluas, tetapi akun password-only tidak boleh diberi label MFA-protected.

## Persetujuan dan input yang belum ada

| Gate | Pemilik keputusan | Perilaku sementara |
| --- | --- | --- |
| Data yang boleh public, grain/filter/menu/export | Pemilik data dan pejabat berwenang | Publication real tertutup; demo sintetis nonproduction saja |
| Format Excel estimasi dan cakupannya | Pemilik proses EKU | Scaffold/empty state; tidak ada mapping/data estimasi palsu |
| Metode forecasting otomatis | Pimpinan/pemilik metodologi | OFF, non-executable; toggle hanya status |
| Logo/aset font/brand resmi | Pemilik aset lembaga | Placeholder netral; fallback font |
| Provider/server/domain/lokasi penyimpanan/firewall | TI dan pemilik sistem | Konfigurasi portable; tidak deploy publik riil |
| Retensi, enkripsi, RPO/RTO, backup/restore | TI/pemilik data | Tidak purge otomatis; dokumen prosedur dan drill sintetis |
| SSO/MFA mandatory dan account lifecycle | TI/keamanan | Django auth pribadi, akses least privilege, status transparan |
| Pentest dan persetujuan production | TI/keamanan/pemilik sistem | Hasil build untuk evaluasi, tidak mengklaim resmi/production secure |

Tidak adanya jawaban approval bukan persetujuan. Pending input tidak menghalangi modul lain yang dapat dibangun dan diuji dengan aman. Semua perubahan gate/settings/permission harus diaudit dengan actor, waktu, alasan dan before/after tersanitasi.
