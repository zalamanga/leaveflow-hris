# Arah tampilan LeaveFlow

Sumber arah: pengguna memilih tampilan terang dan rapi seperti aplikasi kerja pada sesi ini. LeaveFlow menerapkan pilihan tersebut pada pekerjaan pengajuan dan peninjauan cuti. Penjabaran layout serta warna di bawah adalah keputusan implementasi untuk fungsi tersebut.

- Pengguna: karyawan yang memeriksa saldo dan manajer yang meninjau permintaan tim.
- Kepribadian: tenang, jelas, tidak meriah. Bahasa Indonesia langsung menyebut tindakan dan akibatnya.
- ENERGY 1: permukaan terang dengan satu bidang saldo hijau lembut. Status memakai teks dan warna sekaligus.
- RHYTHM 2: saldo berukuran besar, diikuti urutan formulir, daftar, lalu detail. Layar manajer memakai dua kolom karena tugasnya membaca dan memutuskan.
- MOTION 1: perubahan warna singkat pada hover. Tidak ada animasi dekoratif atau carousel; reduced motion dihormati.

Hijau tua dipakai pada tindakan utama dan penanda saldo, sehingga satu alur pengajuan mudah dikenali. Amber berarti menunggu, merah berarti penolakan atau tindakan membatalkan. Semua status tetap memiliki label teks. Nomor bagian menunjukkan urutan tugas, bukan statistik.

Sidebar memiliki dua tujuan yang benar-benar tersedia: permintaan dan kalender. Tidak ada menu payroll, pengaturan organisasi atau profile editor yang belum berfungsi. Tidak ada logo gambar, avatar sintetis atau aset dekoratif baru.

Pada layar sempit, urutan tetap formulir -> daftar -> detail. Tanggal dipisah menjadi satu kolom pada 320 px. Kalender menampilkan tanggal kerja dan menyediakan ringkasan tekstual di bawah agar nama dan rentang tetap terbaca. Area klik utama minimal 44 px. Fokus keyboard memakai outline biru yang jelas.

Keadaan yang harus diperiksa: login salah, pemuatan awal, daftar kosong, filter tanpa hasil, server gagal, preview tidak valid, saldo tidak cukup, konflik versi, detail berubah, keputusan dengan alasan, kalender kosong, desktop 1440 px dan mobile 390/320 px. Hasil pemeriksaan aktual dicatat pada VERIFICATION.md dan UX-REVIEW.md setelah runtime tersedia.
