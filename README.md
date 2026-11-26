# Pustaka Dengar

Dashboard untuk membacakan buku EPUB dan PDF dengan suara, dalam Bahasa Indonesia, lengkap dengan landing page, login, dan sinkron posisi baca antar perangkat.

## Isi repo

| File | Fungsi |
|---|---|
| `index.html` | Landing page + login (Google atau email) |
| `app.html` | Dashboard: upload buku, suara, tempo, penanda, pencarian |
| `firebase-config.js` | Data proyek Firebase-mu (diisi sekali) |
| `firestore.rules` | Aturan keamanan database (tempel ke Firebase) |
| `buku_ke_mp3.py` | Opsional: ubah EPUB/PDF jadi MP3 per bab (suara Ardi/Gadis) |

## Fitur

- Upload EPUB atau PDF; teks dan daftar bab diambil otomatis
- Pilih suara sesuai seleramu (suara bawaan perangkat), bahasa, kecepatan, dan nada
- Penanda dengan catatan, penggeser halaman, dan posisi terakhir tersimpan otomatis
- Login: posisi dengar/baca dan penanda ikut ke perangkat lain
- Cari kalimat untuk melanjutkan dari titik terakhir di perangkat lain (misalnya Xteink)
- Timer tidur, ukuran huruf, mode tanpa akun

## Pasang di GitHub Pages + aktifkan login (sekitar 10 menit, gratis)

Login dan sinkron memakai Firebase paket **Spark** (gratis, tanpa kartu kredit).

1. **Buat proyek.** Buka <https://console.firebase.google.com>, klik **Create a project**, beri nama (mis. `pustaka-dengar`). Google Analytics boleh dimatikan.
2. **Aktifkan login.** Menu **Build > Authentication > Get started > Sign-in method**. Aktifkan **Google** (pilih email dukungan, Save). Kalau mau login pakai email juga, aktifkan **Email/Password**.
3. **Izinkan domain GitHub Pages.** Di **Authentication > Settings > Authorized domains**, klik **Add domain**, isi `NAMAKAMU.github.io` (contoh: `syafiraulia.github.io`).
4. **Buat database.** Menu **Build > Firestore Database > Create database**. Pilih lokasi terdekat (mis. Jakarta atau Singapore), mulai dalam **production mode**.
5. **Pasang aturan keamanan.** Di tab **Rules** pada Firestore, hapus isinya, tempel isi file `firestore.rules`, lalu **Publish**. Aturan ini membuat tiap akun hanya bisa membaca dan menulis datanya sendiri.
6. **Ambil konfigurasi.** Klik ikon roda gigi > **Project settings > Your apps > Web (`</>`)**, daftarkan app, lalu salin isi `firebaseConfig`. Tempel nilainya ke `firebase-config.js` (ganti semua yang berawalan `ISI_`).
7. **Unggah ke GitHub** semua file di folder ini, lalu aktifkan **Settings > Pages > Deploy from a branch > main / (root)**.

Setelah itu buka `https://NAMAKAMU.github.io/NAMA-REPO/`. Jika `firebase-config.js` belum diisi, landing page menampilkan pesan "Login belum aktif" dan tombol **Pakai tanpa akun** tetap jalan.

## Cara sinkron bekerja

- File buku **tidak** diunggah. Yang tersimpan di akun hanya posisi baca (halaman, bab, kalimat), penanda, catatan, dan pengaturan tempo.
- Di perangkat lain, bukumu muncul di Pustaka dengan label "FILE BELUM ADA DI SINI". Ketuk lalu pilih file yang sama, dan kamu lanjut dari titik terakhir.
- Buku dikenali dari isinya, jadi nama atau ukuran file boleh berbeda.
- Kalau dua perangkat dipakai bersamaan, perubahan terakhir yang menang.

## Catatan

- Pilihan "Suara Claude" hanya muncul saat dashboard dibuka lewat claude.ai. Di GitHub Pages dipakai suara bawaan perangkat. Chrome komputer punya "Google Bahasa Indonesia"; Edge punya Ardi dan Gadis.
- Filter nada suara ditebak dari namanya, jadi tidak selalu tepat.
- Di komputer bersama, tekan **Keluar dari akun**. Buku yang pernah kamu tambahkan tetap ada di browser itu sampai kamu hapus.
- Halaman memuat JSZip dan pdf.js dari cdnjs dan Firebase dari gstatic, jadi butuh internet saat dibuka.

## Membuat file MP3 (suara neural)

`buku_ke_mp3.py` mengubah EPUB/PDF jadi MP3 per bab dengan suara Indonesia Ardi (cowok) atau Gadis (cewek) lewat [edge-tts](https://pypi.org/project/edge-tts/). Hasilnya bisa diputar di HP dengan layar terkunci.

```bash
pip install edge-tts pypdf mutagen
python buku_ke_mp3.py buku.epub --list            # lihat daftar bab
python buku_ke_mp3.py buku.epub -v gadis           # suara cewek
python buku_ke_mp3.py buku.epub -v ardi -r 1.1     # suara cowok, 10% lebih cepat
python buku_ke_mp3.py buku.pdf --pages-per-file 15
```

Layanan ini dipakai lewat jalur tidak resmi: gratis dan tanpa kunci API, tapi butuh internet dan bisa berhenti jalan sewaktu-waktu.
