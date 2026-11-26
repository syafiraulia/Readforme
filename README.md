# Pustaka Dengar

Dashboard satu halaman untuk membacakan buku EPUB dan PDF dengan suara, dalam Bahasa Indonesia.

## Fitur

- Upload EPUB atau PDF; teks dan daftar bab diambil otomatis
- Pilih suara cewek atau cowok (suara bawaan perangkat), bahasa, kecepatan, dan nada
- Penanda dengan catatan, penggeser halaman, dan posisi terakhir tersimpan otomatis
- Cari kalimat untuk melanjutkan dari titik terakhir baca di perangkat lain (misalnya Xteink)
- Timer tidur, ukuran huruf, tema terang/gelap

## Cara pakai

Buka `index.html` di browser (Chrome atau Edge paling lengkap suaranya), atau aktifkan GitHub Pages untuk repo ini.

Halaman memuat JSZip dan pdf.js dari cdnjs, jadi butuh internet saat dibuka.

## Catatan

- Buku disimpan di IndexedDB browser, tidak diunggah ke mana pun.
- Pilihan "Suara Claude" hanya muncul saat halaman dibuka lewat claude.ai. Di luar itu dipakai suara bawaan perangkat.
- Label cewek/cowok ditebak dari nama suara, jadi tidak selalu tepat.
