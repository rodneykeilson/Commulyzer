# Instagram Toxicity Scraper

Toolkit untuk mengumpulkan komentar Instagram dari sebuah hashtag kemudian menyiapkan data mentah untuk analisis toksisitas. Proyek ini dibuat di atas paket open-source [`instatouch`](https://github.com/drawrowfly/instagram-scraper).

## Tujuan
- Scrape posting dan komentar dari hashtag publik (contoh awal: `#mobilelegends`).
- Simpan komentar ke JSON Lines agar mudah dianalisis dengan pipeline Python/ML existing.
- Dokumentasikan praktik aman, termasuk penggunaan session cookie Instagram secara lokal.

## Struktur Direktori
```
instagram-toxicity-scraper/
├── README.md
├── package.json
├── .env.example
├── src/
│   └── scrape_hashtag.js
└── data/
    └── raw/
        └── (output JSONL)
```

## Prasyarat
- Node.js 18+ (perlu dukungan fetch & modul modern).
- Akun Instagram yang sedang login. Salin nilai `sessionid` dari browser (lihat panduan di repositori instatouch) dan simpan secara lokal dalam `.env`.
- Jangan commit `.env` atau cookie session ke repository publik.

## Instalasi
```powershell
cd instagram-toxicity-scraper
npm install
copy .env.example .env  # isi INSTAGRAM_SESSION_ID Anda
```

## Menjalankan Scraper
```powershell
node src/scrape_hashtag.js --hashtag mobilelegends --count 60 --max-comments 150 --out data/raw/mobilelegends_comments.jsonl
```

Opsi penting:
- `--hashtag` : hashtag tanpa simbol `#`.
- `--count` : jumlah maksimum post yang dipindai.
- `--max-comments` : komentar per post.
- `--out` : path file output JSONL.
- `--session` : override session ID secara langsung (opsional; default membaca dari `.env`).
- `--delay-ms` : jeda antar request untuk mengurangi risiko rate-limit (default 1500ms).

Scraper akan otomatis menyimpan metadata post ringkas ke bagian `post` di setiap baris JSONL. Hanya data publik yang ditampung.

## Workflow Lanjutan
Setelah data JSONL tersedia, gunakan pipeline toksisitas (misalnya modul Python yang sudah ada di repositori `toxicity-facebook`) untuk preprocess dan scoring. Langkah umum:
1. Jalankan skrip ini untuk menghasilkan `data/raw/mobilelegends_comments.jsonl`.
2. Gunakan utilitas konversi (Python) untuk membuat CSV komentar (lihat dokumentasi pipeline utama).
3. Latih/pakai model toksisitas sesuai kebutuhan.

## Catatan Keamanan & Etika
- Instagram memiliki batasan penggunaan API. Gunakan delay secukupnya dan hindari scraping masif.
- Data yang dikumpulkan hanya untuk analisis akademis. Jangan bagikan komentar mentah tanpa anonimisasi.
- Pastikan session cookie Anda disimpan secara lokal dan tidak diunggah ke repositori publik.

## Lisensi
Kode baru dalam folder ini dirilis di bawah lisensi MIT. Paket pihak ketiga tunduk pada lisensi masing-masing.
