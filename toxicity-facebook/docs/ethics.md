# Checklist Etika Analisis Toksisitas Facebook

Semua anggota tim wajib meninjau checklist berikut sebelum menjalankan pipeline:

- [ ] Pastikan proyek memiliki persetujuan IRB/komite etik (atau konfirmasi bahwa studi dibebaskan).
- [ ] Batasi scraping hanya pada halaman publik dan konten yang tersedia untuk umum.
- [ ] Gunakan cookie atau kredensial hanya bila diperlukan dan simpan secara ephemeral di `.env` lokal.
- [ ] Hindari menyimpan data pribadi (nama user, tautan profil, foto). Simpan `post_id` dan ringkasan anonim bila memungkinkan.
- [ ] Dokumentasikan tujuan penelitian dan dampak potensial terhadap komunitas yang dianalisis.
- [ ] Sediakan mekanisme opt-out apabila ada pemilik konten yang meminta penghapusan data.
- [ ] Tinjau hasil model untuk bias bahasa, dialek, gender, atau kelompok sosial tertentu.
- [ ] Jangan membagikan dataset mentah tanpa pembersihan tambahan dan peringatan konteks.
- [ ] Simpan audit log setiap penggunaan model (lihat `api/app.py`) untuk menjaga akuntabilitas.

Catatan: Pelajar bertanggung jawab mematuhi kebijakan institusi dan aturan platform setiap saat.
