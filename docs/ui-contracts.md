# Kontrak template dan aset UI

Semua template berada di `templates/`, stylesheet dan script disajikan lokal. Tidak ada sumber angka dashboard yang ditanam pada template. Placeholder `PUR` bukan logo BI. Istilah dan tampilan mengikuti hasil inspeksi lima screenshot di `docs/visual-inspection.md`.

## Context umum

- `request` (context processor Django), `messages`, `page_title`, `is_demo` (badge DATA DUMMY), `permissions` (daftar codename tanpa app label), `settings` (SystemSettings).
- `request.user.is_superuser` boleh menampilkan seluruh menu admin; backend wajib tetap memeriksa izin semua action. Tidak ada identitas akun di template public.
- Library `eku_tags`: filter `rupiah`, `int_id`. Context `None`/tanpa data ditampilkan `—`, bukan nol palsu.
- `filter_form` opsional; form GET; `filter_query` query string yang sudah disanitasi, tanpa `page`, digunakan pagination/ekspor. `page_obj` Django Paginator opsional, koleksi `rows`/`batches`/`events` diberikan terpisah sebagai isi page.
- `export_base` opsional, contoh `/admin/export/` atau `/export/`; suffix `csv/`, `xlsx/`, `pdf/` + query filter. Jangan mengirim export_base jika user tidak berizin.

## Dashboard

- `public.html`: `public_tabs=[{key,label}]`, `active_tab` bernilai summary/trend/denominations/seasonality/estimates, `version` PublicationVersion atau None.
- `analytics`: `has_data`, `totals={inflow,outflow,netflow,count}`, `series=[{period,inflow,outflow,netflow,count}]`, `regions=[{region,inflow,outflow,netflow,count}]`, `denominations=[{denomination,inflow,outflow}]`, `seasonality=[{month,inflow,outflow,observations}]`, `notes=[]`, `mom`/`yoy` string presentasi persen atau None.
- `admin_dashboard.html` menambahkan `pending_count`, `stale_publication` bool. Tidak pernah menanam label bank pada grafik public.
- Semua JSON grafik melalui Django `json_script`; ECharts tooltip memakai `richText`, tanpa evaluasi HTML. Nilai Number hanya untuk visual chart; tabel memakai Decimal backend.

## Login dan form umum

- `login.html`: `form` optional, `error`, `next`; POST current URL. Fallback username/password hanya bila form tidak diberikan. Logout selalu POST `/admin/logout/` + CSRF.
- `form.html`: Django `form`, `description`, `warning`, `cancel_url`, `submit_label`; POST current URL; mendukung multipart.
- `confirmation.html`: `items` CashflowTransaction, `diff` optional, `confirmation_token`, `action`, `reason` atau `form`, `back_url`, `post_url` optional (default current URL), `title`/`page_title`, `warning`. POST token + reason + confirm.

## Operasional

| Template | Context | POST dan navigasi |
| --- | --- | --- |
| `transactions.html` | `rows` CashflowTransaction, `is_archive` | checkbox `ids`; `action=archive_preview/restore_preview`, `reason`. Tombol pratinjau menuju konfirmasi server. Edit `/admin/transactions/<uuid>/edit/`. |
| `imports.html` | `form`, `batches` ImportBatch | Upload multipart current URL. Detail `/admin/imports/<uuid>/`. |
| `import_detail.html` | `batch`, `rows` ImportRow, `stats` uppercase NEW_VALID/ALREADY_IMPORTED/NEEDS_REVIEW/INVALID/IMPORTED, `can_commit`, `commit_form`, `diff`, `quality_report_url` | action=commit, atau replace_preview jika mode REPLACE. replace_commit melalui confirmation.html. |
| `review.html` | `rows` ImportRow | Link ke `/admin/review/<uuid>/`. |
| `review_detail.html` | `row`, `form` (decision/target_id/reason/correction fields), `candidates` DuplicateMatch, `normalized_display` teredaksi, `diff` | POST Django form current URL. Kandidat menggunakan relasi `.candidate`. |
| `publications.html` | `version`, `versions`, `form`, `publication_gate_message`, `publication_blocked` | action=publish; form bisa menyediakan reason/is_demo. Rollback Super Admin: action=rollback, version_id, reason. |
| `users.html` | `users`, `form`, `selected_user`, `form_title` | action=create (atau update jika selected_user); editor `/admin/users/<id>/`. |
| `audit.html` | `events` AuditLog | Read-only; detail reason/before/after. |
| `settings.html` | `form` | action=save. |
| `estimates.html` | `adapter_status` opsional | Empty state UNCONFIGURED; tidak ada angka palsu atau tombol prediksi. |
| `masters.html` | `form`, `form_title`, `kind`, `banks`, `regions`, `denominations` | GET kind=bank/region/denomination, POST kind + form. |

## Aksesibilitas dan build

Form memiliki label dari Django, CSRF dan pesan error; template menyediakan skip link, heading semantik, focus keyboard, aria-current, tabel setara untuk grafik, empty state eksplisit. Menu mobile dapat ditutup dengan Escape atau klik luar. Bulk preview dan semua tindakan backend tetap bekerja tanpa JavaScript; JS hanya menambah select-all/konfirmasi tambahan/grafik. Tabel dapat digulir pada layar kecil.

`static/css/app.css` adalah hasil build Tailwind v3.4.17 dari `input.css`; `scripts/build_css.sh` menerima `TAILWIND_BIN`. Aset ECharts 5.6.0, HTMX 2.0.4, Plus Jakarta Sans variable 5.1.1 disimpan bersama lisensi. Runtime tidak membutuhkan CDN. Font sudah disimpan sebagai WOFF2 lokal.

Pemeriksaan visual berbasis browser dan smoke render Django harus dicatat terpisah setelah route/context backend tersambung; keberadaan template bukan bukti browser test lulus.

### Pemeriksaan yang sudah dijalankan

- Tailwind v3.4.17 standalone macos-x64 berhasil mengompilasi `app.css`. Peringatan nonfatal: metadata caniuse-lite bawaan compiler sudah lama; tidak ada kegagalan build.
- Seluruh 24 template awal berhasil dimuat dan dirender oleh engine Django memakai RequestFactory dan objek model tanpa penyimpanan. Pemeriksaan ini menemukan lalu memperbaiki fallback atribut model yang tidak tersedia. Partial `form_fields.html` kemudian ditambahkan untuk memisahkan hidden fields dari label visual.
- Tidak ada angka KPI dummy yang tertanam di template, tidak ada CDN runtime, dan `normalized_display` wajib teredaksi pada tampilan review; data raw/nomor rekening tidak menjadi fallback visual.
- Browser end-to-end belum dibuktikan pada tahap serah template; menunggu route/view backend tersambung. Playwright dan Google Chrome tersedia di host untuk tahap tersebut.
