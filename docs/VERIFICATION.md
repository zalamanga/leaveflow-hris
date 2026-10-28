# Verifikasi 28 Oktober 2026

| Pemeriksaan | Hasil aktual |
| --- | --- |
| `scripts/Test.ps1`, PostgreSQL 17 terisolasi | **49 lulus**, tanpa skip |
| Vitest 4.1.12 | **4 lulus** |
| TypeScript dan Vite production build | Lulus pada host dan image Linux |
| Playwright, Edge pada stack Docker | **10 lulus** dalam satu suite; **1 kasus tambahan lulus** pada run terarah |
| Screenshot aplikasi nyata | Empat PNG: tiga desktop 1440×1000 dan satu mobile 390×844 |
| Kontras dan reflow DOM | Login, karyawan, dan manajer diperiksa pada 320/390/768/1024/1440 px |

Kasus tambahan menguji pembukaan rincian hari kerja, penolakan dengan alasan, pagination ketika tersedia, unduhan CSV, serta tombol keluar. Suite lengkap kini berisi 11 kasus; workflow GitHub menjalankan semuanya dari database baru. Lihat [Actions](https://github.com/zalamanga/leaveflow-hris/actions) untuk hasil checkout yang diperiksa.

Tes PostgreSQL menjalankan dua reservasi bersamaan pada saldo lima hari, masing-masing meminta tiga: satu berhasil, satu menerima 409, saldo tersisa dua dan satu event tersimpan. Dua keputusan dengan versi sama juga menghasilkan satu pemenang. Fixture memakai schema sementara pada database test; database aplikasi tidak dipakai.

Cakupan lain: pelepasan reservasi, akhir pekan/libur kantor, snapshot kebijakan, overlap, saldo kurang, validasi versi ketat, rollback audit, privasi daftar/detail/hitungan/search/CSV/kalender, formula CSV, cookie/sesi/CSRF/Origin, kuota login, migrasi berulang, serta seed idempoten.

Browser memeriksa pengajuan, penarikan, persetujuan, pembatalan, draf saat konflik, server gagal, sesi dicabut, dan data tim lain. Pemeriksaan DOM menghitung kontras teks, placeholder dan batas input; fokus keyboard serta overflow diperiksa tersendiri. [Gate tampilan](UX-REVIEW.md) memuat hasil review akhir.

Satu peringatan deprecation berasal dari adaptor TestClient FastAPI/Starlette ke httpx. Seluruh tes tetap lulus. Hasil ini tidak menyatakan sertifikasi aksesibilitas, keamanan mutlak, kepatuhan hukum, atau kesiapan skala produksi.
