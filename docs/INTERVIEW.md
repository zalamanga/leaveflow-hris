# Menjelaskan LeaveFlow saat interview

## Pembuka sekitar satu menit

"Saya membuat LeaveFlow untuk mengerjakan bagian HRIS yang memiliki aturan transaksi: cuti tahunan. Karyawan melihat saldo dan mengajukan tanggal, sedangkan manajer hanya meninjau tim yang melapor langsung kepadanya. Pengajuan menunggu langsung mereservasi saldo. Tantangannya adalah memastikan dua pengajuan bersamaan tidak memakai kuota yang sama, serta mencegah keputusan lama dari tab lain menimpa keputusan terbaru. Saya memakai transaksi PostgreSQL, urutan row lock yang konsisten, dan version checking."

Katakan ini sebagai penjelasan proyek latihan. Jangan menyatakan proyek sudah digunakan perusahaan atau mematuhi hukum ketenagakerjaan tertentu.

## Urutan demo

1. Masuk sebagai karyawan, tunjukkan saldo tersedia, menunggu dan disetujui.
2. Pilih rentang yang melewati akhir pekan. Hitung hari kerja dan buka daftar tanggal yang tidak dihitung.
3. Kirim. Tunjukkan reservasi saldo dan event pengajuan.
4. Masuk sebagai manajer. Buka permintaan tadi, setujui, lalu perlihatkan perubahan riwayat.
5. Tunjukkan kalender hanya memuat cuti disetujui dan tidak memuat alasan pribadi.
6. Batalkan persetujuan dengan alasan yang jelas, atau demonstrasikan penolakan pada permintaan lain. Tunjukkan saldo yang kembali.
7. Bila pewawancara meminta sisi teknis, buka `lock_account`, `locked_request`, dan tes concurrent reservation.

## Pertanyaan teknis yang mungkin muncul

**Mengapa saldo menunggu ikut dikurangi?**

Jika hanya cuti disetujui yang mengurangi saldo, karyawan bisa mengirim beberapa permintaan dan semuanya tampak mencukupi saat dibuat. Reservasi memegang kuota sejak pengajuan. Approval memindahkan pending ke approved tanpa mengurangi saldo dua kali.

**Mengapa perlu row lock dan versi sekaligus?**

Lock menserialkan transaksi pada akun/grant yang sama, termasuk dua pengajuan yang ID-nya berbeda. Versi mendeteksi bahwa browser membawa saldo atau status yang sudah lama. Keduanya mengatasi sumber konflik yang berbeda.

**Mengapa tidak memakai counter saldo yang bisa berkurang terus?**

Versi ini menghitung penggunaan dari pengajuan pending/approved. Riwayat status menjadi sumber data penggunaan, sehingga pembatalan tidak perlu memperbaiki counter terpisah. Pada skala lebih besar, ringkasan teragregasi dapat dipakai dengan rekonsiliasi yang jelas.

**Bagaimana melindungi data tim lain?**

Setiap query memakai filter otorisasi SQL. Hal ini berlaku pada daftar, hitungan, pencarian, export dan detail, bukan hanya tombol. Menebak ID tim lain menghasilkan 404.

**Mengapa tanggal kerja disimpan?**

Kalender libur bisa berubah. Snapshot mempertahankan penjelasan mengapa pengajuan lama dihitung sejumlah hari tertentu. Perubahan kalender berikutnya tidak mengubah saldo pengajuan lama secara diam-diam.

**Apa keterbatasan proyek?**

Ini modul cuti tahunan dengan satu tahap persetujuan. Belum ada payroll, carry-over, cuti setengah hari, delegasi, lampiran sensitif atau SSO. Kebijakan 12 hari adalah contoh yang dapat diubah melalui CLI, bukan klaim legal.

**Apa yang akan dikembangkan berikutnya?**

Mulai dari kebutuhan nyata: delegasi saat manajer tidak hadir, ledger kuota dengan alasan penyesuaian, dan notifikasi yang dikirim melalui outbox transaksi. Setiap tambahan perlu aturan privasi, status gagal, serta pengujian yang sesuai.
