# Runbook operator

Dokumen ini menjelaskan perilaku yang diharapkan. Gunakan laporan implementasi/pengujian untuk mengetahui fitur yang sudah terverifikasi. Operasikan data dummy di development/staging sampai penggunaan data asli disetujui.

## Akun dan permission

SUPER_ADMIN mengelola akun/permission/master/settings/publikasi/rollback. ADMIN_STAFF mempunyai izin per pengguna melalui Django permission; grant tidak otomatis berasal dari label staf. Jangan berbagi password. Nonaktifkan akun yang tidak lagi digunakan dan audit perubahan akses.

| Permission staf | Operasi |
| --- | --- |
| `import_data` | Upload/staging/commit import sesuai mode |
| `add_transaction` | Tambah transaksi manual |
| `edit_transaction` | Ubah transaksi yang dipilih |
| `verify_ambiguous` | SKIP/CREATE/UPDATE/DEFER row antrean dengan alasan |
| `publish_manual` | Membuat versi publikasi manual yang lolos policy |
| `soft_delete` | Arsipkan satu transaksi dengan alasan |
| `restore` | Pulihkan satu transaksi |
| `bulk_soft_delete` | Arsipkan pilihan terkonfirmasi |
| `bulk_restore` | Pulihkan pilihan terkonfirmasi |
| `export_internal` | Ekspor data internal sesuai filter |

Permission nama pendek berada dalam app codename yang dicatat implementasi (`cashflow.<codename>`). UI tersembunyi tidak cukup: endpoint server harus menolak user tanpa izin. Berikan hak paling kecil yang dibutuhkan. MFA/SSO belum boleh dinyatakan aktif tanpa implementasi/konfigurasi nyata.

## Import harian/historis

1. Verifikasi sumber, klasifikasi dan scope; simpan file asli privat. Jangan menganggap nama file atau tanggal update sebagai bukti periode lengkap.
2. Pilih tambah, update terpilih, atau replace scope. Replace hanya untuk snapshot lengkap yang dinyatakan eksplisit; jangan memilih replace untuk file yang sifatnya belum jelas.
3. Tinjau preview jumlah baru/sudah ada/ambigu/invalid, jumlah inflow/outflow/netflow dan report kualitas. Alias source diterima, konflik sumber tidak diperbaiki diam-diam.
4. Commit hanya baris valid yang identitasnya cukup pasti. Baris ambigu tetap antre, invalid tidak masuk KPI. Partial success bukan kegagalan seluruh batch; jangan membuat batch baru untuk memaksa konflik masuk.
5. Periksa riwayat batch dan audit. Reupload file identik harus idempotent. File yang berubah memerlukan rekonsiliasi historis; signature sama tidak selalu duplikat.

Pada fixture aktual terdapat 8 kandidat: enam konsisten dengan total Rp8.200.000.000 dan dua konflik. KX16/KT16 tidak boleh ditebak pecahannya dari pembagian nominal/lembar. Withdrawal pada fixture tes sintetis belum menjadi bukti pola file operasional.

## Verifikasi dan koreksi

Pilih SKIP_AS_EXISTING jika terbukti sudah ada, CREATE_NEW jika benar kejadian baru, UPDATE_SELECTED_EXISTING setelah memilih UUID target benar, atau DEFER bila bukti belum cukup. Tulis alasan. Tinjau diff sebelum/sesudah. Record soft-deleted tetap dipertimbangkan; import tidak otomatis memulihkannya. Jika format sumber/pecahan belum jelas, koreksi master atau minta file sah sesuai workflow, jangan memasukkan angka tebakan.

Edit/manual/soft-delete/restore membuat revision/audit. Bulk action memerlukan permission independen dan konfirmasi scope/jumlah. Tidak ada hard-delete transaksi dalam UI umum. Replace yang benar hanya menonaktifkan record dalam scope terkonfirmasi dan menyimpan before/after.

## Publikasi dan rollback

Default MANUAL: perubahan internal tidak terlihat public. Tinjau cutoff, periode, data tertahan dan preview agregat; pastikan approval policy tersedia. Publikasi operasional tanpa approval harus ditolak. AUTOMATIC tetap hanya menerbitkan valid active eligible rows sesuai policy, bukan semua raw data.

Public membaca versi aktif. Rollback memilih versi sebelumnya dan mencatat alasan; transaksi internal tidak ikut mundur. Sesudah rollback, cocokkan nomor versi/checksum/sumber pada public dan export. Filter bank, rekening, data raw, audit serta detail transaksi tidak boleh public. Persetujuan perlu diperbarui jika ingin membuka grain tambahan.

## Estimasi dan pengaturan

Tanpa format estimasi asli, halaman menampilkan status belum dikonfigurasi. Mengaktifkan visibilitas automatic estimation sebelum metode ada hanya menampilkan informasi, tidak mengeksekusi prediksi. Perubahan publication mode/menu/permission/approval reference harus tercatat audit. Jangan memberi status integrasi estimasi selesai hanya karena halaman render.

## Monitoring dan pemulihan

Periksa health, import gagal/tertahan, pertumbuhan private storage, koneksi DB, latency/error, publication stale dan umur backup. Log tidak boleh memuat password/token/full rekening. Batas rate-limit dan ukuran file bukan alasan menonaktifkan validasi untuk menyelesaikan upload.

Jika import gagal, periksa status batch dan transaksi tersimpan sebelum retry; gunakan sumber checksum dan audit untuk menghindari ganda. Jika publication gagal, pointer sebelumnya harus tetap aktif. Jika ada indikasi kebocoran, tutup akses sesuai prosedur TI, pertahankan audit, rotasi credential yang terdampak, dan evaluasi versi publikasi/backup; jangan menghapus bukti secara spontan.

Restore database/file mengikuti [backup-restore.md](backup-restore.md), pertama pada environment terpisah. Retensi, rotasi backup dan penghapusan data harus menunggu kebijakan resmi. Pengelolaan server dan review akses berkala memerlukan penanggung jawab yang ditetapkan lembaga.


## Hapus dan mulai ulang data

Di Verifikasi Data, pilih baris lalu **Hapus pilihan** untuk mengeluarkannya dari antrean tanpa membuat transaksi. Keputusan tetap tercatat pada audit. Baris snapshot REPLACE harus ditinjau melalui detail agar cakupan penggantian tidak berubah tanpa pemeriksaan.

Di Data Cashflow, tindakan **Hapus pilihan (pindahkan ke arsip)** mempertahankan kemampuan pemulihan melalui Data Terhapus / Arsip.

Super Admin dapat membuka **Kosongkan Data** dan mengetik `KOSONGKAN DATA`. Reset menghapus seluruh transaksi/arsip, staging dan riwayat impor, keputusan verifikasi, revision transaksi, estimasi, serta snapshot publikasi. Pengguna, master referensi, pengaturan, dan audit dipertahankan. Sebelum reset, snapshot JSON dibuat dengan permission 0600 di `.private/reset-backups/`; file sumber tetap di penyimpanan privat. Reset menggunakan satu transaksi PostgreSQL dan daftar tabel eksplisit tanpa CASCADE. Kegagalan membuat cadangan membatalkan reset. Pointer publikasi dikosongkan dan revisi data dinaikkan. Checksum batch dihapus sehingga file yang sama dapat diimpor ulang. Snapshot cadangan berisi data internal dan hanya untuk pemulihan oleh pengelola.
