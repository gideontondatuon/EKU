# Inspeksi referensi visual

Tanggal inspeksi: 21 Oktober 2026 (WITA). Kelima berkas di bawah dibuka dengan alat `view_image`; tidak ada logo atau angka yang diekstrak menjadi aset/data aplikasi.

| Berkas | Temuan faktual | Penerapan desain |
| --- | --- | --- |
| `cashflow_structure_1.png` | Judul besar, ringkasan periode, empat tab, empat kartu Inflow/Outflow/Netflow/Transaksi, judul grafik bulanan. Screenshot juga memuat peringatan deprecated Plotly. | Hierarki informasi dan empat KPI dipertahankan; angka screenshot dan peringatan library tidak dibawa ke aplikasi. Istilah satuan ditulis jelas, bukan hanya huruf M yang ambigu. |
| `cashflow_structure_2.png` | Batang berkelompok Januari–Maret, inflow biru kehijauan, outflow jingga, legenda dan garis grid tipis. | Batang inflow/outflow dengan legenda, label nilai, tabel alternatif aksesibel. Grafik memakai data server terpilih, bukan nominal gambar. |
| `cashflow_structure_3.png` | Tabel wilayah (total Sulawesi Utara, Manado, SKM), empat kolom angka, unduh CSV, definisi inflow/outflow/netflow di footer. Ada netflow negatif. | Tabel agregat wilayah, format negatif eksplisit, sumber versi publikasi, ekspor scoped. Wilayah berasal dari master yang diverifikasi, bukan daftar/angka hasil gambar. |
| `admin_blue_style.webp` | Layout Analyca: sidebar vertikal, header biru cerah, empat kartu biru, konten putih di atas latar kebiruan, chart luas. Konten sales, avatar, ilustrasi dan pola dekoratif. | Warna dan pembagian ruang diadaptasi untuk Admin PUR. Sidebar memakai label teks, status verifikasi/publikasi lebih dominan daripada dekorasi. Metrik sales, avatar orang, logo Analyca, ilustrasi dan ornamen tidak dipakai. |
| `header_bi_style.png` | Header putih, logo BI di kiri, nama sistem dan subjudul di sebelahnya, identitas akun di kanan. Konten merupakan presensi magang. | Public memakai susunan header tersebut dengan judul `Dashboard Cashflow EKU`, subjudul `Estimasi Kebutuhan Uang`, tombol `Masuk Admin` di kanan. Identitas pengguna dan konten presensi tidak ditampilkan. |

## Branding dan aksesibilitas

Logo pada screenshot **bukan aset resmi yang diberikan untuk dipakai** dan tidak membuktikan izin penggunaan. Header menggunakan placeholder netral bertuliskan `PUR` sampai aset/izin resmi tersedia. Logo tidak digambar ulang, dipotong dari screenshot, atau diunduh dari sumber tak terverifikasi.

UI bahasa Indonesia, tanggal WITA, nominal Rupiah dan format angka Indonesia. Font Plus Jakarta Sans dengan fallback sans-serif. Public tidak memiliki sidebar; Admin memiliki sidebar responsif. Palet sementara mengikuti master: primary `#1976E9`, deep blue `#1054AB`, light blue `#78B6F5`, latar `#EAF2FC`, surface putih, heading `#1E293B`. Kontras, focus keyboard, label form, semantic headings, dan tabel alternatif grafik harus diverifikasi pada implementasi.

## Inspeksi aplikasi legacy

`eku_dashboard/` adalah aplikasi Streamlit/Plotly dengan penyimpanan Parquet, login password bersama, sidebar filter, dan halaman publik/internal dalam kode yang sama. Pembacaan dilakukan terhadap README, requirements, `eku/processing.py`, `eku/charts.py`, `eku/fmt.py`, dan `app.py`. Aplikasi legacy berguna sebagai referensi penamaan metrik, grafik, definisi footer, dan filter wilayah.

Perilaku legacy yang **tidak layak diteruskan** dalam implementasi baru:

- Parser mengambil inflow/outflow dari tipe transaksi dan nominal, mengabaikan kolom inflow/outflow sumber.
- Nominal/lembar dikonversi numerik lalu `abs()` dan nilai invalid diubah nol, berpotensi menyamarkan masalah data.
- Mapping pecahan berdasarkan prefiks hardcoded; tidak cukup untuk konflik pada workbook dummy.
- Tanggal dikonversi generik dengan `pandas.to_datetime`, tanpa aturan eksplisit serial Excel.
- Bulan yang hilang diisi nol, padahal tidak membuktikan tidak ada arus kas.
- Status tahun penuh ditaksir dari tanggal awal/akhir, bukan bukti kelengkapan sumber.
- Workflow replace periode/seluruh data, password bersama, arsip sepuluh versi dan data Parquet bukan dasar RBAC, audit, immutable publication snapshot atau kebijakan retensi baru.

Data pada `eku_dashboard/data/` tidak dipindahkan atau dianggap dummy/layak publik karena klasifikasi dan otorisasi tidak tersedia. Aplikasi Django baru harus mulai tanpa data operasional, dengan seed sintetis terpisah dan berlabel.
