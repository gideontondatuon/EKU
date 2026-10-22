# Inspeksi workbook aktual — M0

Sumber **DATA DUMMY**: `references/SETBAY_DUMMY.xlsx`. Inspeksi membaca ZIP/XML dengan Python standard library secara read-only, tanpa mengeksekusi formula. Python sistem 3.9.6 tidak memiliki `openpyxl` saat inspeksi. Semua rekening disensor dalam laporan dan artefak JSON pendamping; source workbook tetap privat/internal.

- Ukuran: 29.939 bytes.
- SHA-256: `cdf1d28975f46f3df1cd6ad5a04e3ddd0e16da547762bf753ffb171c8fee2954`.
- ZIP: 25 entries; total isi terkompresi 26.683 bytes, total setelah dekompresi 200.561 bytes. Tidak ditemukan payload macro atau external-link entry. Ini temuan inspeksi sampel, bukan jaminan keamanan upload selanjutnya.
- Workbook memakai epoch Excel 1900 (tidak ada `date1904`). Sheet XML tidak menyediakan elemen `dimension`; parser tidak boleh menyimpulkan sheet kosong dari ketiadaan metadata dimension.
- Artefak `excel-inspection.json` memuat seluruh sel berisi, nomor baris/kolom, tipe, style, formula, cached value dan tanggal hasil decoding; nilai rekening diganti `[REDACTED]`.

## Struktur yang benar-benar ditemukan

| Sheet | Area berisi | Baris data | Peran |
|---|---|---:|---|
| Tanggal Update | A1:A2 | 1 | Metadata tanggal update sumber |
| DENOM | A1:C5 dan E1:F5 | 4 + 4 referensi | Mapping pecahan dan lokasi |
| SETBAY KASTIP | A1:Q5 | 4 | Transaksi SKM |
| SETBAY MANADO | A1:P5 | 4 | Transaksi Manado |
| Sheet2 | Kosong | 0 | Abaikan |

`Tanggal Update!A2` berisi numeric serial `46107.0` dengan format tanggal → **26 Maret 2026**. Semua transaksi MANADO berisi serial `44449.0` → **10 September 2021**. Semua transaksi KASTIP berisi `44454.0` → **15 September 2021**. Rentang transaksi aktual hanya 10–15 September 2021. Tanggal update bukan tanggal transaksi dan tidak membuktikan kelengkapan historis sampai 2026.

Kolom aktual **MANADO**: `COTC_TRAN_DATE`, `COTC_BRN_CODE`, `MBRN_NAME`, `TRANSACTION_TYPE`, `MONEY_TYPE`, `BANK_NAME`, `BANK_ACCOUNT`, `COTC_BRN_CODE2`, `COTCP_NOTE_COIN_TYPE`, `COTCP_AMOUNT`, `COTCP_PIECES`, `Denom`, `Urutan Denom`, `Inflow`, `Outflow`, **`Neflow`**.

Kolom aktual **KASTIP**: `COTC_TRAN_DATE`, `TRANSACTION_TYPE`, `MONEY_TYPE`, `BANK_NAME`, `BANK_ACCOUNT`, `COTC_BRN_CODE`, `MBRN_NAME`, `COTC_CLIENT_BRNCODE`, `COTCR_NOTE_COIN_TYPE`, `COTCR_AMOUNT`, `COTCR_PIECES`, `Denom`, `Urutan Denom`, `Nama Kastip`, `Inflow Kastip`, **`Outflow Kasti`**, `Netflow Kastip`.

Kolom di atas sesuai master prompt, termasuk dua salah eja yang harus diterima adapter. Named filter KASTIP hanya meliputi A:N, tetapi data transaksi mencapai Q; rentang filter Excel bukan batas baca tabel.

## Mapping referensi

| DENOM.Pecahan | DENOM.Denom mentah | Normalisasi numeral | Urutan |
|---|---|---:|---:|
| KY22 | `  100.000 ` | 100000 | 1 |
| KY16 | `  100.000 ` | 100000 | 1 |
| KY14 | `  100.000 ` | 100000 | 1 |
| KY04 | `  100.000 ` | 100000 | 1 |

Normalisasi tersebut hanya mengurai angka pada sumber. Tabel ini tidak membuktikan mapping semua kode pecahan dan tidak boleh menggantikan master operasional yang disetujui.

| Kode Kastip (string) | Nama Kastip |
|---|---|
| `000000` | SKM Tahuna |
| `000001` | SKM Siau |
| `000002` | SKM Kotamobagu |
| `000003` | SKM Melonguane |

Sel `Nama Kastip` pada keempat transaksi sebenarnya memuat **kode**, bukan nama; nilainya sama dengan `COTC_CLIENT_BRNCODE`. Resolusi nama harus memakai DENOM E:F. `COTC_BRN_CODE` bernilai numeric `760.0`; normalisasi representasi integral menjadi string `760` tanpa menebak padding yang tidak ada dalam file. Seluruh `MBRN_NAME` bernilai KPwBI Provinsi Sulawesi Utara. Sheet MANADO menentukan scope Manado KPwBI, bukan nama bank.

## Seluruh baris transaksi sampel

Semua delapan baris bertipe **Deposit**, outflow 0, inflow sama dengan amount, dan netflow cached sama dengan inflow. Nominal berikut adalah data dummy dari sumber, bukan angka operasional atau estimasi.

| Sheet/baris | Tanggal | Bank internal | Lokasi | Kode pecahan | Denom sumber | Pieces | Amount/Inflow Rp | Catatan |
|---|---|---|---|---|---:|---:|---:|---|
| MANADO/2 | 2021-09-10 | PT. BANK NATIONALNOBU | Manado | KY16 | 100000 | 20000 | 2000000000 | Konsisten secara aritmetika |
| MANADO/3 | 2021-09-10 | PT. BANK VICTORIA INTERNASIONAL | Manado | KY16 | 100000 | 10000 | 1000000000 | Konsisten secara aritmetika |
| MANADO/4 | 2021-09-10 | PT. BANK NEGARA INDONESIA (PERSERO), TBK. | Manado | KY16 | 100000 | 10000 | 1000000000 | Konsisten secara aritmetika |
| MANADO/5 | 2021-09-10 | PT Bank KB Indonesia Tbk | Manado | KY16 | 100000 | 40000 | 4000000000 | Konsisten secara aritmetika |
| KASTIP/2 | 2021-09-15 | PT. BANK MANDIRI (PERSERO), TBK. | SKM Tahuna | KY14 | 100000 | 1000 | 100000000 | Konsisten secara aritmetika |
| KASTIP/3 | 2021-09-15 | PT. BANK MANDIRI (PERSERO), TBK. | SKM Siau | KY16 | 100000 | 1000 | 100000000 | Konsisten secara aritmetika |
| KASTIP/4 | 2021-09-15 | PT. BANK MANDIRI (PERSERO), TBK. | SKM Kotamobagu | KX16 | 100000 | 1000 | 50000000 | Konflik nominal/pecahan; kode tidak ada pada DENOM |
| KASTIP/5 | 2021-09-15 | PT. BANK MANDIRI (PERSERO), TBK. | SKM Melonguane | KT16 | 100000 | 2000 | 4000000 | Konflik nominal/pecahan; kode tidak ada pada DENOM |

Jenis uang MANADO seluruhnya `D-SB ULE`; KASTIP seluruhnya `E-SB UTLE`. `Urutan Denom` pada dua baris KASTIP bermasalah bernilai 2, sementara master seluruhnya urutan 1. Tidak ada contoh koin atau transaksi withdrawal yang nyata.

Rekening MANADO tersimpan sebagai shared string 10 karakter, empat nilai berbeda; KASTIP sebagai shared string 11 karakter, empat nilai berbeda. Semua berawalan nol. Seluruh kode Kastip enam digit juga string. Jangan mengubah identifier ini menjadi integer. Dalam aplikasi, raw staging/private file tetap restricted; audit generik/JSON public/HTML public tidak boleh memuat rekening penuh.

Total literal seluruh sumber: MANADO Rp8.000.000.000; KASTIP Rp254.000.000; gabungan Rp8.254.000.000; outflow Rp0. Jika dua baris konflik ditahan, total enam baris konsisten Rp8.200.000.000. Total sumber mentah tidak boleh disajikan sebagai total data tervalidasi. Kesesuaian aritmetika saja belum memberi izin publikasi.

## Formula dan cached values

Ada **36 formula cells**: MANADO 20, KASTIP 16. Semua memiliki cached value. Sebagian formula cashflow adalah **shared formulas**: pada baris 3–5, elemen `<f t="shared" si="…"/>` tidak memuat text tetapi tetap merupakan formula. Parser harus membaca formula metadata dan cached value secara terpisah; `openpyxl` formula mode dan `data_only` mode dapat digunakan bersama, atau parser XML menangani shared formula secara eksplisit.

- Denom MANADO L2:L5 serta KASTIP L2:L3 memakai VLOOKUP dengan cached string ber-spasi `  100.000 `.
- Urutan pecahan M untuk baris tersebut memakai VLOOKUP dengan cached angka 1.
- MANADO N2 mendefinisikan `IF(D2="Deposit",J2,0)` dan O2 mendefinisikan `IF(D2="Withdrawal",J2*-1,0)`; P2 `N2+O2`. Baris 3–5 mengikuti shared formula.
- KASTIP O2 mendefinisikan `IF(B2="Deposit",J2,0)` dan P2 `IF(B2="Withdrawal",J2*-1,0)`; Q2 `O2+P2`. Baris 3–5 mengikuti shared formula.
- Tidak ada formula total/summary row pada sampel, tetapi parser tetap harus mengenali dan mengabaikan row ringkasan pada file lain.

**Konvensi sign penting:** formula outflow sumber menghasilkan angka negatif untuk Withdrawal, sedangkan model domain menggunakan magnitudo outflow nonnegatif dan `netflow = inflow − outflow`. Karena tidak tersedia baris Withdrawal aktual, fixture sintetis harus meliputi outflow sumber negatif dan positif. Setiap normalisasi sign harus tercatat dalam provenance, divalidasi terhadap transaction type/amount/netflow, dan konflik ditahan. Jangan menghitung `inflow − (outflow negatif)` atau mengubah sumber tanpa jejak.

Angka XML dapat memakai scientific notation (`2.0E9`, `1.0E8`). Baca sebagai `Decimal` dan pastikan integral; jangan menolak scientific notation yang valid atau melewatkannya melalui float sebagai sumber kebenaran nominal. Formula tidak dieksekusi di server. Cached value yang hilang, error, atau tidak konsisten harus ditahan untuk review/invalid sesuai penyebab.

## Implikasi acceptance dan default aman

1. Fixture workbook aktual perlu menguji 8 kandidat, 6 aritmetika konsisten, dan 2 konflik pecahan yang ditahan; tidak diam-diam memperbaiki KX16 menjadi 50000 atau KT16 menjadi 2000 hanya dari hasil pembagian.
2. Validasi format, leading zeros, serial dates, alias salah eja, scientific notation, shared/cached formulas dan lookup wilayah adalah wajib.
3. Tidak ada ID unik transaksi sumber. Checksum mencegah re-upload identik; fingerprint bukan UNIQUE global. Data ini tidak cukup untuk membuktikan matching historis sempurna atau aturan occurrence tanpa review.
4. Semua data adalah dummy. Tidak ada izin mengimpor sebagai data produksi atau publikasi nyata. Policy public, retensi, logo resmi, hosting dan metode prediksi tetap pending approval.
5. File ini bukan template estimasi. Mapping estimasi asli dan metode otomatis tetap pending input; tidak ada nilai estimasi yang disimpulkan dari file cashflow.

## Verifikasi inspeksi

Inspeksi berhasil membaca seluruh lima sheet, seluruh 8 row transaksi, 36 formula/cached pairs, dan dua tabel referensi. Rekening disensor sebelum output. Tidak ada mutasi workbook, database, atau import transaksi dalam tahap inspeksi ini. Keamanan runtime parser dan rekonsiliasi perlu automated tests pada M3.
