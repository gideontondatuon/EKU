# Panduan Deployment Vercel (Dashboard Cashflow EKU)

Dokumen ini memandu langkah-langkah deployment Dashboard Cashflow EKU ke **Vercel** menggunakan integrasi native zero-configuration Django.

---

## 1. Prasyarat

1. Akun **[Vercel](https://vercel.com)**.
2. Database **PostgreSQL eksternal** yang mendukung koneksi SSL (misalnya: [Neon](https://neon.tech), [Supabase](https://supabase.com), atau Railway Postgres).
3. Akun **GitHub** tempat repositori ini di-push.

---

## 2. Environment Variables yang Wajib Dikonfigurasi di Vercel

Buka **Vercel Dashboard** -> Proyek Anda -> **Settings** -> **Environment Variables**, lalu tambahkan:

| Variable | Nilai / Contoh | Keterangan |
|---|---|---|
| `DJANGO_ENV` | `production` | Mengaktifkan mode aman Django. |
| `DJANGO_SECRET_KEY` | *(String acak minimal 50 karakter)* | Kunci rahasia enkripsi Django. |
| `DATABASE_URL` | `postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require` | URL koneksi ke PostgreSQL cloud Anda. |
| `TRUST_PROXY_SSL` | `1` | Memastikan header HTTPS dari reverse proxy Vercel dikenali. |
| `DATABASE_SSLMODE` | `require` | Mode SSL koneksi PostgreSQL cloud. |

> [!NOTE]
> `DJANGO_ALLOWED_HOSTS` dan `DJANGO_CSRF_TRUSTED_ORIGINS` sudah otomatis mengenali domain `*.vercel.app` dan URL deployment Vercel Anda secara dinamis. Jika Anda menggunakan custom domain (misal: `cashflow.kantor.id`), tambahkan nama domain tersebut ke `DJANGO_ALLOWED_HOSTS` dan `DJANGO_CSRF_TRUSTED_ORIGINS`.

---

## 3. Menjalankan Migrasi Database & Akun Admin Awal

Karena Vercel adalah lingkungan serverless tanpa shell interaktif persisten, jalankan migrasi database dan pembuatan akun admin pertama kali dari komputer lokal dengan mengarahkan `DATABASE_URL` ke database cloud Anda:

```bash
# 1. Jalankan migrasi tabel ke database cloud
DATABASE_URL="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require" python manage.py migrate

# 2. Buat akun admin awal
export EKU_ADMIN_USERNAME='admin-pur'
export EKU_ADMIN_EMAIL='admin@example.com'
export EKU_ADMIN_PASSWORD='PasswordKuatMinimal12Karakter!'
DATABASE_URL="postgresql://user:pass@ep-xyz.aws.neon.tech/neondb?sslmode=require" python manage.py bootstrap_admin
```

---

## 4. Cara Rollback / Kembali ke Sistem Semula

Jika di kemudian hari Anda ingin membatalkan adaptasi Vercel dan kembali ke kondisi asli sebelumnya:

```bash
# Pindah kembali ke tag baseline pre-vercel yang sudah dibuat:
git checkout pre-vercel
```
Atau jika ingin membuat branch baru dari tag tersebut:
```bash
git checkout -b restore-baseline pre-vercel
```
