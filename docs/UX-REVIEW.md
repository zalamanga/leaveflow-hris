# Gate tampilan LeaveFlow

**PASS**, ditinjau langsung oleh root pada 28 Oktober 2026 setelah build Docker, pemeriksaan browser, dan inspeksi empat screenshot. Bukti yang dapat diulang: `e2e/99-accessibility.spec.ts`, `e2e/leaveflow.spec.ts`, [VERIFICATION.md](VERIFICATION.md), dan `screenshots/`.

- R-01 PASS: warna datar; tidak ada gradient atau glow dekoratif.
- R-02 PASS: pemeriksaan source UI dan dokumentasi tidak menemukan em dash.
- R-03 PASS: DOM tidak meluap pada 320/390/768/1024/1440 px; mobile memakai susunan vertikal.
- R-04 PASS: penanda tanggal dan angka bagian menjelaskan kalender/alur, tanpa paket ikon dekoratif.
- R-05 PASS: saldo, formulir, inbox, detail, dan kalender memakai komposisi sesuai pekerjaan masing-masing.
- R-06 PASS: font sistem dan hierarki judul dijelaskan pada DESIGN.md; tidak ada heading monospace.
- R-07 PASS: grid hanya untuk tanggal kalender, bukan pola latar.
- R-08 PASS: tombol memakai kata kerja; tidak ada panah dekoratif di setiap tindakan.
- R-09 PASS: label status berasal dari pengajuan; tidak ada badge pemasaran di atas judul.
- R-10 PASS: panel memakai permukaan solid, tanpa glassmorphism.
- R-11 PASS: radius kontrol kecil dan panel lebih besar; elemen tidak semuanya berbentuk pill.
- R-12 PASS: batas panel memisahkan pekerjaan; tidak ada shadow besar pada seluruh komponen.
- R-13 PASS: warna status dan fokus tidak memakai glow.
- R-14 PASS: ukuran formulir, riwayat, dan detail mengikuti isi; kalender mempunyai area tersendiri.
- R-15 PASS: tindakan bernama Hitung hari kerja, Kirim permintaan, Setujui cuti, dan Ekspor CSV.
- R-16 PASS: copy menyebut tindakan dan aturan contoh, tanpa klaim pemasaran generik.
- R-17 PASS: saldo, hitungan pengajuan, dan kalender berasal dari respons API/database.
- R-18 PASS: tidak ada testimonial atau pelanggan fiktif.
- R-19 PASS: tidak ada loop animasi; state berubah setelah tindakan atau respons server.
- R-20 PASS: reservasi saldo dan keputusan cuti menjadi fokus, bukan shell dashboard beserta grafik pengisi.
- R-21 PASS: tampilan terang mengikuti pilihan pengguna; tidak ada toggle tema yang belum selesai.
- R-22 PASS: tidak memakai ilustrasi generik; visual utama adalah data kerja dan kalender.
- R-23 PASS: tidak ada logo/foto buatan; data sintetis diberi banner Training dan gambar berasal dari aplikasi.
- R-24 PASS: navigasi membuka permintaan atau kalender; tautan dokumentasi mempunyai tujuan nyata.
- R-25 PASS: tes DOM memeriksa teks/placeholder ≥4,5:1 dan batas input ≥3:1 pada lima lebar layar.
- R-26 PASS: kontrol terhubung ke handler/endpoint; alur mutasi, CSV, rincian, pagination dan logout diuji.
- R-27 PASS: browser memeriksa daftar kosong, pemuatan, kegagalan server, validasi, dan retry yang dapat dipakai.
- R-28 PASS: tidak ada FAQ pengisi.
- R-29 PASS: permukaan netral, aksen teal, dan warna status yang bermakna; alasan ditulis pada DESIGN.md.
- R-30 PASS: komposisi mengikuti pengajuan cuti; tidak menyalin tampilan produk lain.
- R-31 PASS: hierarki saldo, pemisahan panel, dan kalender mempunyai alasan kerja tertulis.
- R-32 PASS: kontrol native, label input, skip link dan fokus terlihat; perpindahan keyboard diperiksa di browser.
- R-33 PASS: UI tertulis pada source React/CSS; tidak ada patch DOM, CSS atau navigasi saat aplikasi dibuka.
- R-34 PASS: satu tema terang diperiksa pada kedua peran dan state pemuatan/kegagalan.
- R-35 PASS: production build dijalankan dan click-through pengajuan, keputusan, kalender, CSV serta logout tercatat di tes browser.
- R-36 PASS: kuota 12 hari disebut kebijakan latihan; tidak ada klaim kepatuhan atau keamanan mutlak.
- R-37 PASS: arah terang/rapi dan ENERGY 1 / RHYTHM 2 / MOTION 1 dinyatakan sebelum pengerjaan.
- R-38 PASS: nama Training, domain .test dan banner membedakan dataset contoh dari data organisasi nyata.

- Dials PASS: ENERGY 1 pada warna solid, RHYTHM 2 pada perbedaan formulir/inbox/kalender, MOTION 1 tanpa animasi berulang.
- Focal point PASS: saldo dan pengajuan menjadi fokus karyawan; permintaan menunggu menjadi fokus manajer.
- Whitespace PASS: jarak memisahkan formulir, hasil, dan alasan keputusan, bukan ruang pengisi.
- Accent PASS: teal menandai navigasi aktif dan tindakan utama.
- Identity PASS: tanggal, hitungan hari, dan penanda urutan menghubungkan halaman dengan pekerjaan cuti.
- Design Read PASS: arah aplikasi kerja terang dari pengguna tercatat pada DESIGN.md.
- C-1 PASS: keputusan warna, tipografi dan susunan mempunyai alasan pada DESIGN.md.
- C-2 PASS: tombol aktif mempunyai perilaku; alasan minimum dan versi usang menonaktifkan mutasi dengan penjelasan.
- C-3 PASS: setiap bagian melayani saldo, pengajuan, keputusan, atau kalender.
- C-4 PASS: lima lebar layar, keyboard, empty/error, sesi berakhir, dan konflik versi diperiksa.
- C-5 PASS: angka diturunkan dari database dan seluruh data latihan diberi label; bukti screenshot berasal dari runtime.

Pemeriksaan ini mencakup alur dan tampilan yang dicatat, bukan sertifikasi aksesibilitas menyeluruh.
