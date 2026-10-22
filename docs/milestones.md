# Milestone dan pencatatan hasil

Baseline rencana 21 Oktober 2026 WITA. Dokumen ini membedakan **rencana** dari **bukti eksekusi**. Hasil tes dicatat di `docs/test-results.md` bila tersedia; jangan menyimpulkan PASS dari keberadaan source/migration.

| Milestone | Deliverable / acceptance | Gerbang lanjut | Status saat penyusunan M0 |
| --- | --- | --- | --- |
| M0 | Audit repo, seluruh references, requirements/architecture/ERD/decisions/security, acceptance IDs | Temuan workbook/risiko terdokumentasi sebelum parser/schema | Inspeksi dan dokumen tersedia; tidak ada migration/test runtime pada M0 |
| M1 | Scaffold Django/env/auth/UI shell/assets/Docker/seed | Migrate + check + auth/render tests | Menunggu hasil implementasi/eksekusi |
| M2 | Models/constraints/master/RBAC/audit/delete/restore | Migrations forward/reverse + domain/RBAC tests | Menunggu hasil implementasi/eksekusi |
| M3 | Excel adapters/staging/reconcile/partial/review/replace | Workbook nyata + synthesized edge/concurrency/security tests | Menunggu hasil implementasi/eksekusi |
| M4 | Admin operations UI/filter/pagination/permissions/history | Authenticated endpoint/form/workflow smoke tests | Menunggu hasil implementasi/eksekusi |
| M5 | Projection/policy/manual-auto/version/rollback/export | Public leakage + atomicity + permission tests | Publication operasional tetap BLOCKED BY APPROVAL |
| M6 | KPI/analytics/charts/filters/CSV-XLSX-PDF/accessibility | Calculation/filter/export tests + browser checks | Menunggu hasil implementasi/eksekusi |
| M7 | Estimates scaffold/contract/flags/empty state | Unconfigured/OFF/no fabricated estimate tests | Format asli PENDING INPUT; forecasting DEFERRED |
| M8 | Integration/security/performance/lint/CI/deploy/runbook/restore | Test/lint/check/restore real output; Docker smoke di host mampu | Docker runtime belum tersedia; production approval pending |

## Format laporan per milestone

Untuk tiap milestone, catat tanggal WITA, commit/berkas terkait, command dan environment, jumlah pass/fail/skip (beserta alasan), migrasi yang benar-benar dijalankan, temuan dan keputusan, serta pekerjaan berikutnya. Bila M1 belum mempunyai model app tambahan, laporkan migration Django yang dijalankan, bukan mengarang migration domain.

Contoh **format**, bukan hasil:

```text
M<n>: IMPLEMENTED / SCAFFOLDED / PENDING INPUT / BLOCKED BY APPROVAL
Runtime/DB: <versi aktual>
Migrate: <command, exit code, ringkasan>
Tests: <command, pass/fail/skip, test report path>
Lint/check: <command, exit code>
Manual checks: <apa yang benar-benar diperiksa>
Risiko/pending: <gate yang tersisa>
```

## Bukti M0 yang tersedia

- Workbook `SETBAY_DUMMY.xlsx`: lima sheet dibaca; delapan candidate rows; 36 formula/cached pairs; enam konsisten dan dua konflik; semua rekening dalam laporan disensor. Lihat `excel-inspection.md` dan `.json`.
- Kelima gambar dibuka dan dicatat di `visual-inspection.md`. Logo screenshot tidak dianggap aset resmi.
- Legacy Streamlit diperiksa sebagai referensi, tanpa memindahkan data/credential/asumsi parser.
- M0 berupa inspeksi dokumentasi/file, sehingga tidak mempunyai automated application test atau database migration untuk dilaporkan. Tes parser dan DB dijalankan pada milestone implementasi.

## Definisi penyelesaian yang jujur

Implementasi teknis dapat selesai untuk evaluasi sementara format estimasi, hosting, branding dan approval publikasi tetap pending. Docker Compose hanya dapat disebut berjalan setelah build/up/migrate/smoke benar-benar dieksekusi. Browser accessibility dan restore drill harus dibedakan dari unit tests. Jangan menandai seluruh M0–M8 COMPLETE apabila ada pekerjaan teknis yang belum diuji atau dependensi eksternal yang belum ada.
