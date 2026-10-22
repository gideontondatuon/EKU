# Catatan keputusan

Tanggal baseline: 21 Oktober 2026 WITA. Keputusan ini adalah pilihan engineering untuk implementasi evaluasi; bukan persetujuan operasional lembaga.

| ID | Status | Keputusan dan alasan | Konsekuensi / bukti |
| --- | --- | --- | --- |
| D01 | FINAL | Master prompt terbaru menentukan Django, menggantikan diskusi Next.js sebelumnya. Target Django5.2 LTS/Python3.12/PostgreSQL17. | Semua pembangunan baru di `Dashboard Cashflow EKU`; target runtime dan dependency pin dicatat di requirements/Docker. |
| D02 | FINAL | Modular monolith dengan accounts/core/cashflow/imports/publications/dashboard/estimates. | Masterdata dan audit di core; verification di imports; transaksi lintas workflow tetap atomik. |
| D03 | DEFAULT AMAN | Legacy Streamlit/Parquet diperlakukan sebagai referensi tampilan saja. | Tidak mengubah source atau memigrasi data legacy karena klasifikasi/otorisasi tidak tersedia. |
| D04 | FINAL | Uang Rupiah Decimal integer, inflow/outflow magnitudo nonnegatif; netflow derived. | Jangan mengonversi sumber nominal melalui float atau `abs()` tanpa validasi/provenance. |
| D05 | FINAL | Adapter mengakui sign outflow negatif/positif hanya bila konsisten dengan type/amount/netflow. | Sampel hanya Deposit; fixture Withdrawal berlabel sintetis, validasi bentuk operasional masih pending. |
| D06 | FINAL | DENOM adalah sumber mapping kandidat yang harus cross-check, bukan kebenaran mutlak. | KX16/KT16 yang tidak terpetakan dan amount konflik ditahan. Tidak mengarang pecahan Rp50.000/Rp2.000 dari pembagian. |
| D07 | FINAL | Identitas aplikasi UUID; fingerprint nonunique; file checksum dan multiset scoped membantu idempotensi. | Kemiripan atribut bukan bukti kejadian identik; ambiguity perlu keputusan user berizin. |
| D08 | FINAL | Soft-deleted records tetap ikut matching. | Import ulang tidak otomatis memulihkan/membuat ulang transaksi yang telah diarsipkan. |
| D09 | DEFAULT AMAN | MANUAL publication; approval reference kosong; projection tanggal/wilayah saja. | Operasional tidak dipublikasikan sebelum approval. Pecahan/jenis uang/bank public tidak dibuka dengan menebak kebijakan. |
| D10 | FINAL | Immutable publication snapshot dengan current pointer atomik. | Rollback publikasi tidak me-rollback transaksi internal. Export/cache public selalu terikat versi. |
| D11 | DEFAULT AMAN | Demo sintetis hanya development/staging dan conspicuous DATA DUMMY. | Tidak auto-import workbook/legacy saat startup; seed eksplisit dan ditolak production. |
| D12 | FINAL | Native Django Groups + user permissions; hanya dua role awal. | Tidak membangun RBAC paralel; setiap endpoint/action mempunyai server-side gate. |
| D13 | DEFAULT AMAN | Automatic estimation OFF, adapter estimasi unconfigured. | ON sebelum metode tersedia hanya menampilkan status; tidak ada angka/model rekayasa. |
| D14 | PENDING INPUT | Format estimasi riil, cakupan dan definisi belum tersedia. | Domain/scaffold dapat diuji, integrasi format final belum dapat dinyatakan complete. |
| D15 | DEFAULT AMAN | Placeholder netral PUR; tanpa crop/tiruan logo BI. | Screenshot header bukan aset/izin branding. Aset resmi menunggu input/approval. |
| D16 | DEFAULT AMAN | Font fallback lokal jika Plus Jakarta Sans belum tersedia; assets tidak perlu memanggil CDN saat runtime. | Tailwind/ECharts/HTMX dipaketkan lokal bila tersedia; akses network untuk build tidak memberi izin mengirim data operasional ke layanan luar. |
| D17 | FINAL | Store timestamp UTC-aware, presentasi Asia/Makassar dan id-ID. | Tanggal transaksi adalah date; tanggal metadata update tidak menentukan cakupan transaksi. |
| D18 | DEFAULT AMAN | Upload sinkron berbatas dengan staging persisten dan commit atomik. | Worker async dapat ditambahkan bila ukuran/volume terukur memerlukannya; timeout tidak boleh menyebabkan duplicate retry. |
| D19 | PENDING APPROVAL | Hosting/domain/data residency/retensi/backup/MFA-SSO. | Infrastruktur portable; tidak memilih provider atau membuka layanan publik dengan data riil. |
| D20 | FINAL | Audit/revision append-only di workflow aplikasi; secret dan rekening penuh direduksi. | Pembatasan akses DB/backup dan kebijakan retensi tetap perlu review operasional; aplikasi tidak mengklaim administrator DB tidak bisa mengubah data. |

## Kepastian dan heuristik rekonsiliasi

**Pasti sejauh bukti tersedia:** SHA-256 yang sama menunjukkan byte file sama; occurrence `(batch,sheet,row)` mengidentifikasi baris staging dalam batch; UUID menunjuk transaksi internal yang dipilih; declared scope mengidentifikasi wilayah/periode yang user konfirmasi.

**Heuristik:** fingerprint/atribut serupa, jumlah kejadian, urutan baris, kedekatan tanggal atau satu kandidat tidak membuktikan identitas kejadian sumber. Scope historis dan occurrence count hanya dapat dipakai otomatis saat konteks sumber cukup; perubahan nilai/multipel kandidat/record soft-deleted ditahan atau memerlukan konfirmasi. Tidak ada klaim perfect deduplication tanpa source transaction ID.

## Gate terbuka

Pemilik sistem/TI perlu mengesahkan scope publikasi (termasuk tanggal/wilayah), klasifikasi sumber operasional, aset resmi, template estimasi, metode forecasting bila ingin diaktifkan, hosting/data residency, secret management, backup/retensi, SSO/MFA dan readiness setelah pentest. Gate ini tidak menghalangi pembangunan dan tes lokal dengan data sintetis.
