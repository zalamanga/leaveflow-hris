# Panduan kode

## Urutan membaca

Mulai dari `models.py`, lanjutkan `policy.py`, kemudian `main.py`. Setelah aturan API dipahami, baca `frontend/src/App.tsx` dan pengujiannya. `db.py` hanya mengatur engine serta umur sesi ORM; fungsi API mengatur batas transaksi.

| File | Isi dan alasan dipisahkan |
| --- | --- |
| `backend/app/config.py` | Environment dan validasi origin serta batas sesi/login |
| `backend/app/models.py` | Skema ORM, relasi, constraint dan konversi waktu UTC |
| `backend/app/policy.py` | Tanggal kantor serta kalkulasi hari kerja |
| `backend/app/schemas.py` | Payload Pydantic dengan field tambahan dilarang |
| `backend/app/security.py` | Hash Argon2, verifikasi password, token acak dan hash token |
| `backend/app/main.py` | Factory aplikasi, sesi, otorisasi, transaksi cuti, CSV dan kalender |
| `backend/app/cli.py` | Migrasi, akun, grant dan libur kantor dari terminal |
| `backend/app/seed.py` | Akun dan pengajuan sintetis sekali pasang |
| `backend/alembic/versions/001_leaveflow.py` | Migrasi eksplisit skema awal |
| `frontend/src/api.ts` | Fetch same-origin, CSRF, status error dan response kosong |
| `frontend/src/types.ts` | Kontrak TypeScript untuk response API |
| `frontend/src/format.ts` | Tanggal kalender tanpa perubahan zona lokal browser |
| `frontend/src/App.tsx` | Login, saldo, pengajuan, daftar, peninjauan dan kalender |
| `frontend/src/styles.css` | Layout desktop/mobile, status, fokus dan mode reduced motion |

## Fungsi inti

### `office_today(now)` dan `estimate(db, start, end, today)`

`office_today` mengubah waktu UTC menjadi tanggal Asia/Jakarta. `estimate` menolak rentang lampau, terbalik, lintas tahun dan tanpa hari kerja. Ia menghasilkan `working_days`, `excluded_days`, `units`, tahun, dan kebijakan. Endpoint preview memanggil fungsi yang sama dengan pengajuan, tetapi pengajuan selalu menghitung ulang hasilnya.

### `balance(db, employee_id, year, grant=None)`

Fungsi menjumlahkan pengajuan aktif berdasarkan status. `pending` adalah reservasi; `approved` adalah penggunaan. Status lainnya tidak masuk saldo. Saldo dikembalikan bersama versi grant agar browser bisa mengirim versi tersebut saat membuat pengajuan.

### `visibility(user)`

Hasilnya adalah ekspresi SQL pembatas akses. Semua query pengajuan menggunakan ekspresi ini, termasuk query hitungan dan ekspor. Menyaring data setelah query akan berisiko membocorkan jumlah atau data lintas tim.

### `lock_account(db, employee_id, year)`

Mengunci akun karyawan lalu grant dengan `SELECT ... FOR UPDATE`. Akun dan grant dibaca ulang menggunakan `populate_existing`, sehingga objek yang sudah ada di identity map tidak menutupi perubahan transaksi lain.

### `locked_request(db, request_id, user, expected_version)`

Mengidentifikasi pengajuan yang boleh diakses, mengunci akun/grant, lalu mengunci dan membaca ulang pengajuan. Versi lama memberi `409`. Tidak ada status atau event yang disimpan sebelum pemeriksaan ini berhasil.

### `create_leave(...)`

Pemohon berasal dari sesi. Setelah memegang lock, fungsi memeriksa versi saldo, menghitung hari kerja, memeriksa rentang tumpang tindih, lalu memeriksa kecukupan saldo. `working_days` dan kebijakan disalin ke snapshot. Pengajuan baru, event awal, dan kenaikan versi grant di-commit bersama.

### `review(...)`, `withdraw(...)` dan `finish(...)`

`review` dipakai oleh approve/reject/cancel dengan aturan transisi yang terbatas. Penolakan dan pembatalan membutuhkan alasan minimal 10 karakter. `withdraw` khusus pemilik pengajuan menunggu. `finish` menaikkan versi pengajuan dan grant, menyimpan semuanya, dan mengubah konflik versi ORM menjadi `409`.

### `consume_login_attempt(...)`

Counter per email dan peer IP memakai upsert database, bukan dictionary proses. Batasnya delapan/email dan 64/peer per window 15 menit. Percobaan valid maupun gagal tetap dihitung; restart proses aplikasi tidak mengosongkan counter yang masih ada di database.

## Kontrak API

Semua endpoint selain health/login membutuhkan sesi. Semua POST selain login juga membutuhkan `X-CSRF-Token`.

| Metode dan rute | Penggunaan |
| --- | --- |
| `GET /api/health` | Readiness database |
| `POST /api/auth/login` | `{email,password}`; membuat cookie sesi |
| `GET /api/auth/me` | User, CSRF token dan mode demo |
| `POST /api/auth/logout` | Mencabut sesi saat ini |
| `GET /api/leave/context` | Tanggal kantor, tahun dan kebijakan |
| `GET /api/leave/balance?year=2026` | Saldo dan versi grant karyawan sendiri |
| `GET /api/leave/estimate?start_date=...&end_date=...` | Preview hari kerja, karyawan saja |
| `GET /api/leave/requests?year=2026` | Daftar dengan `q`, `status`, `page`, `page_size` |
| `POST /api/leave/requests` | `{start_date,end_date,reason,expected_version}`; versi dari saldo |
| `GET /api/leave/requests/{id}` | Detail, snapshot dan event |
| `POST /api/leave/requests/{id}/withdraw` | `{expected_version}` dari pengajuan |
| `POST /api/leave/requests/{id}/approve` | `{expected_version,reason?}` |
| `POST /api/leave/requests/{id}/reject` | `{expected_version,reason}` |
| `POST /api/leave/requests/{id}/cancel` | `{expected_version,reason}` |
| `GET /api/leave/calendar?year=2026&month=11` | Hanya tanggal cuti disetujui |
| `GET /api/leave/requests/export.csv?year=2026` | Ekspor manajer dengan filter yang sama |

`page_size` maksimal 100. CSV maksimal 10.000 baris, kalender maksimal 1.000 pengajuan per bulan. Tidak ada truncation diam-diam pada ekspor dan kalender yang melebihi batas.

`401`: sesi/login tidak valid. `403`: peran, Origin atau CSRF tidak sesuai. `404`: pengajuan tidak ditemukan dalam cakupan akses. `409`: versi/status/overlap konflik. `422`: data atau kebijakan tidak memenuhi aturan. `429`: kuota percobaan login habis.

## Administrasi melalui CLI

Perintah dijalankan di service backend dengan environment database yang sama. Password akun baru dibaca dari `APP_USER_PASSWORD`, tidak dari argumen command line.

```text
python -m app.cli init-db
python -m app.cli create-user --email manager@example.test --name "Manager" --role manager
python -m app.cli create-user --email employee@example.test --name "Employee" --role employee --manager-id 1
python -m app.cli set-grant --employee-id 2 --year 2027 --days 12
python -m app.cli add-holiday --date 2027-02-03 --label "Libur kantor contoh"
```

Gunakan ID aktual hasil pemeriksaan database, bukan menyalin angka 1/2 tanpa memeriksa akun. `set-grant` tidak boleh menurunkan kuota di bawah jumlah disetujui + menunggu. Perubahan libur hanya memengaruhi preview/pengajuan berikutnya; snapshot pengajuan lama tetap sama.

`seed-demo` memerlukan `APP_DEMO_MODE=true` dan password 12-128 karakter. Seed menolak database akun yang sudah berisi data tanpa marker. Satu transaksi memasukkan akun, grant, contoh cuti, event dan marker. Menjalankan ulang setelah berhasil tidak menimpa data.

## Frontend saat konflik

Browser tidak mengubah saldo secara optimistis. Setelah mutasi berhasil, daftar, saldo, kalender dan detail dimuat ulang dari server. Jika menerima `409`, teks alasan dan catatan keputusan tetap ada, lalu data terbaru dimuat sebelum tombol perubahan kembali aktif. Jika pemuatan terbaru gagal, perubahan dinonaktifkan sampai tombol muat ulang berhasil.
