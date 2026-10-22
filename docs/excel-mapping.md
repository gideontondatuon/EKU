# Kontrak import Excel SETBAY — M3

Adapter saat ini: `setbay-v2`, dengan registri sheet/alias di `imports/parser.py`. Referensi faktual ada pada [inspeksi workbook](excel-inspection.md). Format estimasi **belum tersedia** dan tidak diproses adapter cashflow.

## Mapping

| Field domain | MANADO | KASTIP | Aturan |
|---|---|---|---|
| transaction_date | COTC_TRAN_DATE | COTC_TRAN_DATE | Serial Excel epoch 1900/1904 atau tanggal eksplisit; bukan angka mentah |
| bank_name | BANK_NAME | BANK_NAME | Nama internal; bukan dimensi public |
| account | BANK_ACCOUNT | BANK_ACCOUNT | String restricted; nol pada sumber teks dipertahankan. Integer numeric positif ≤15 digit menjadi peringatan non-kritis, tanpa rekonstruksi nol. Risiko presisi ditahan |
| region_code/name/kind | Scope sheet MANADO | COTC_CLIENT_BRNCODE / Nama Kastip | KASTIP lookup DENOM E:F; kode numeric tidak dipadding otomatis |
| transaction_type | TRANSACTION_TYPE | TRANSACTION_TYPE | Deposit → DEPOSIT; Withdrawal → WITHDRAWAL; lainnya review |
| money_type | MONEY_TYPE | MONEY_TYPE | Kode sumber, tanpa menebak kategori |
| denomination_code | COTCP_NOTE_COIN_TYPE | COTCR_NOTE_COIN_TYPE | Master pecahan terverifikasi; tidak hardcode berdasarkan prefix |
| denomination_value | Denom | Denom | String Indonesia `  100.000 ` → Decimal 100000; `1.000 UK` / `1.000 UL` → 1000 (kode pecahan tetap terpisah) |
| source_amount | COTCP_AMOUNT | COTCR_AMOUNT | Decimal integral exact, scientific notation diterima |
| pieces | COTCP_PIECES | COTCR_PIECES | Bilangan bulat positif |
| inflow_amount | Inflow | Inflow Kastip / Inflow | Nilai sumber utama; harus sesuai tipe/amount |
| outflow_amount | Outflow | Outflow Kasti / Outflow Kastip / Outflow | Magnitudo domain nonnegatif; sign sumber divalidasi |
| source_netflow | Neflow / Netflow | Netflow Kastip / Netflow / Neflow | Cross-check; domain netflow selalu derived |

`COTC_BRN_CODE`, `MBRN_NAME`, urutan pecahan dan seluruh sel asli disimpan pada raw staging privat untuk provenance. Kode bank resmi tidak diberikan file; master bank baru mendapat identifier lokal `SRC-<hash nama>`, yang bukan kode bank resmi. Rekening tidak ditampilkan penuh pada audit generik atau endpoint public.

## Validasi dan master data

Parser membaca ZIP dan XML menggunakan `defusedxml`, **tanpa menjalankan formula**. Formula termasuk shared formulas harus memiliki cached value yang valid. Formula dengan referensi eksternal ditolak. Nilai sumber, tipe sel, formula/cached metadata, dan catatan normalisasi dipertahankan. Kesalahan format, tanggal, angka nonintegral/NaN, cached error/kosong masuk `INVALID`; konflik aritmetika/jenis/netflow, mapping belum pasti dan identitas berisiko kehilangan presisi masuk `NEEDS_REVIEW`. Rekening numeric ≤15 digit tidak menghambat nominal cashflow; peringatan disimpan di normalized.warnings dan provenance.

Formula sumber memakai outflow negatif. Adapter hanya menormalisasi menjadi magnitudo positif bila tipe WITHDRAWAL, inflow nol, dan magnitudo sesuai nominal. Catatan sebelum/sesudah/alasan disimpan. Netflow sumber harus sama dengan inflow dikurangi magnitudo tersebut. Konflik ditahan; server tidak menghitung ulang workbook untuk menutup konflik.

Enam baris workbook dummy konsisten; dua baris KASTIP dengan KX16/KT16 ditahan. Tidak ada inferensi otomatis Rp50.000 atau Rp2.000 dari pembagian nominal/lembar. Resolusi memerlukan master pecahan terverifikasi dan koreksi eksplisit beserta alasan.

Untuk workbook **operasional**, master pecahan baru dapat dibuat otomatis hanya dari referensi DENOM yang konsisten, nominal positif, dan aritmetika transaksi yang valid. Pembuatan master mencatat batch/sumber dan audit `IMPORT_DENOMINATION_CREATE`. Master existing yang belum diverifikasi, konflik nilai, atau berlabel DATA DUMMY untuk impor operasional tetap ditahan; tidak ada overwrite atau promosi master diam-diam. Referensi dibaca berdasarkan nama kolom, bukan posisi kolom. Pecahan tidak dihitung dengan menebak pembagian nominal/lembar.

Checksum dummy asli selalu memaksa `is_demo=True`; data dummy ditolak pada production. File contoh pengguna yang belum berchecksum dummy harus ditandai oleh pengunggah bila memang sintetis.

## Batas upload

- Ekstensi `.xlsx`; konten harus OOXML ZIP valid. File tidak pernah dieksekusi.
- Maksimum upload 10 MiB, 100 MiB uncompressed, 2.000 ZIP entries, rasio kompresi per-entry 1.000, 32 worksheet, 50.000 transaksi, 128 kolom terisi per baris, 32.767 karakter per sel.
- Path traversal, duplicate ZIP entries, archive terenkripsi, macro payload/content type, external links dan external relationships ditolak.
- Hanya sheet adapter SETBAY, DENOM, dan Tanggal Update dibaca sebagai data; sheet lain diabaikan. Batas ukuran ZIP/XML, jumlah worksheet, macro dan external relationship tetap diperiksa pada seluruh arsip. Sheet kosong diabaikan. Total/subtotal dengan label eksplisit pada kolom tanggal tidak menjadi transaksi.
- Upload disimpan dengan nama UUID pada storage privat (`MEDIA_ROOT`), permission file 0600/directory 0700 dan tanpa route publik. Metadata nama asli hanya basename; nama asli tidak menentukan path penyimpanan. Kegagalan transaksi staging membersihkan file yang baru tersimpan.

## Rekonsiliasi tanpa ID sumber

Identitas transaksi adalah UUID aplikasi. Identitas occurrence import adalah `(batch, sheet, row_number)`. Fingerprint bisnis **bukan UNIQUE**; field nominal dalam fingerprint memakai Decimal canonical. Checksum workbook + dataset adalah unique untuk idempotensi upload file yang persis sama, termasuk ketika nama file diubah.

1. File identik mengembalikan batch lama dan menulis audit re-upload. Tidak menciptakan transaksi maupun copy file tambahan.
2. Signature baru yang lolos validasi, tanpa kandidat konteks serupa, menjadi `NEW_VALID`.
3. Kesamaan fingerprint dengan data existing membutuhkan review jika identitas tidak cukup pasti. Candidate evidence disimpan pada `DuplicateMatch`, termasuk soft-deleted candidate.
4. Multiset/count hanya dipakai jika **kedua provenance** berasal dari snapshot lengkap yang dikonfirmasi, dataset sama, dan baris berada dalam scope tanggal/wilayah terverifikasi. Satu occurrence existing dipakai paling banyak satu kali. Count berlebih masuk review.
5. Duplikasi atribut dalam file pertama menahan occurrence tambahan untuk review, bukan membuangnya. `CREATE_NEW` yang dikonfirmasi dapat menyimpan dua transaksi sah dengan fingerprint sama.
6. Kandidat tanggal/bank/rekening/wilayah/jenis uang sama tetapi atribut lainnya berubah masuk review; tidak otomatis dianggap transaksi terbaru maupun revision target.
7. Soft-deleted candidate tetap diperhitungkan dan tidak diaktifkan kembali oleh import. Restore memakai workflow dan izin terpisah.
8. Commit mengevaluasi ulang kandidat di bawah row lock `SystemSettings`. Dua batch yang sebelumnya sama-sama `NEW_VALID` tidak boleh lolos menjadi duplicate hanya karena diproses bersamaan.

Kesamaan atribut dan deklarasi kelengkapan snapshot merupakan bukti yang dapat diaudit, **bukan identitas unik dari sumber**. Algoritma tidak mengklaim pencocokan sempurna. Scope dataset default `SETBAY`; ekspansi/cross-dataset matching memerlukan kebijakan eksplisit.

## Partial import dan keputusan

`commit_batch` memproses `NEW_VALID` saja. Batch menjadi `PARTIAL` bila masih ada ambigu/invalid. Commit adalah transaksi database atomic; gangguan tidak meninggalkan separuh transaksi dalam commit unit. File sumber dan staging tetap tersedia untuk retry. Perubahan data memanggil `changed()` sekali per commit agar revisi data dan policy publikasi konsisten.

Keputusan verifikasi memerlukan izin `verify_ambiguous` dan alasan:

- `DEFER`: tetap menunggu, decision dicatat.
- `SKIP_AS_EXISTING`: pilih UUID target secara eksplisit; tidak memodifikasi target.
- `CREATE_NEW`: validasi lengkap dan master terverifikasi tetap wajib; konflik tidak dapat diabaikan hanya dengan konfirmasi.
- `UPDATE_SELECTED_EXISTING`: UUID target aktif dan izin tambahan `edit_transaction` wajib; old/new revision dicatat.

Baris `INVALID` harus diperbaiki dalam sumber lalu diunggah ulang; tidak ada tombol bypass. Koreksi review menggunakan allowlist field, divalidasi kembali, disimpan pada decision yang append-only dan raw sumber tetap utuh.

## Snapshot replace

`REPLACE` memerlukan scope eksplisit `{start, end, region_codes}` dan `full_snapshot_confirmed=True`. Baris di luar scope invalid. Baris ambigu/invalid harus diselesaikan sebelum preview; review update/create hanya menyusun keputusan, tanpa mengubah transaksi sebelum konfirmasi replace.

Preview menampilkan ditambah, target before/after, dinonaktifkan, dan total inflow/outflow/netflow/count sebelum/sesudah. Token bertanda tangan mengikat digest rencana, revisi data, batch dan actor; berlaku 15 menit. Perubahan transaksi atau keputusan baris setelah preview membatalkan token. Commit memeriksa ulang scope/eligibility/izin dalam satu transaksi atomic; `edit_transaction` diperlukan untuk update dan `bulk_soft_delete` untuk penonaktifan. Logical before-image dan setiap revision disimpan. Baris yang hilang hanya diarsipkan di scope yang dinyatakan lengkap; transaksi luar scope tidak disentuh.

## API service internal

```python
stage_import(actor, uploaded_file, mode="ADD", scope=None,
             full_snapshot_confirmed=False, is_demo=False)  # -> ImportBatch
commit_batch(actor, batch_id)                              # -> ImportBatch
decide_row(actor, row_id, decision, reason,
           target_id=None, corrections=None)               # -> ImportRow
preview_replace(actor, batch_id)                          # -> dict + confirmation_token
commit_replace(actor, batch_id, confirmation_token, reason) # -> ImportBatch
```

Semua mutation service menegakkan izin server-side, lock database, audit dan transaction revision. UI tidak boleh langsung memodifikasi model untuk melewati service. Status row: `NEW_VALID`, `NEEDS_REVIEW`, `INVALID`, `ALREADY_IMPORTED`, `READY_UPDATE` (khusus rencana replace), `IMPORTED`.

## Bukti pengujian

`tests/test_imports.py` menggunakan workbook lampiran secara read-only dan fixture sintetis berlabel. Run parser pertama: **12 passed**, 13 DB tests belum dijalankan pada saat dokumen ini ditulis. Tes DB mencakup partial commit, checksum idempotent, master approval, correction/RBAC, occurrence multiset, soft-delete, selected update, replace scope/token, failure rollback dan dua commit paralel. Hasil DB final dicatat pada laporan milestone setelah run PostgreSQL selesai.

## Penyesuaian format SETBAY 22 Oktober 2026

Label pecahan dengan akhiran UK/UL diterima pada kolom Denom di referensi dan transaksi; akhiran tidak diizinkan pada nominal/lembar. Nilai dan kode sumber tetap disimpan sehingga uang kertas/logam tidak digabung berdasarkan nominal saja. Kode Kastip numeric dinormalisasi ke integer tanpa menebak nol depan dan harus cocok dengan referensi DENOM. Rekening numeric integer positif ≤15 digit dinormalisasi tanpa desimal dengan peringatan; tidak ada nol depan yang ditebak. Nilai di luar batas presisi atau format invalid tetap ditahan.

Verifikasi baca-saja terhadap workbook contoh pengguna: 18 transaksi (9 MANADO, 9 KASTIP), 35 referensi pecahan, 4 referensi Kastip. Hasil parser v2: 18 NEW_VALID dengan 9 peringatan rekening numeric; tidak ada INVALID. Status staging operasional tetap mengikuti validasi master dan duplikasi. File contoh tidak dimasukkan ke database maupun dipublikasikan.


## Alur smart import v2

`smart_import` menjalankan stage_import lalu commit_batch untuk baris valid pada ADD/UPDATE. UPDATE masih memerlukan pilihan target eksplisit; REPLACE tetap menunggu preview dan konfirmasi. Kegagalan commit mempertahankan staging untuk dicoba ulang. Unggahan identik mengembalikan batch yang sama. Peringatan dihitung terpisah dari status karena baris dapat tersimpan sekaligus memiliki peringatan.

Pencocokan konteks saat commit tidak memakai transaksi yang baru dibuat dari batch yang sama; pengaman fingerprint berulang tetap aktif. Saat salah satu rekening historis/sumber berasal dari angka Excel, konteks pencocokan diperluas tanpa menebak persamaan rekening. Kesamaan fingerprint saja tidak membuat data historis dilewati: bukti snapshot lengkap beserta scope dan hitungan occurrence masih wajib. Konflik master wilayah ditahan per baris agar baris lain dapat disimpan.

Peringatan dan nilai sumber tetap disimpan privat. Upload tidak mengubah mode publikasi; `changed()` tetap mengikuti kebijakan publikasi yang sudah dipilih pengelola.
