import asyncio
import os
import random
import pandas as pd
from urllib.parse import urlparse, urlunparse

from parsers.glints_parser import GlintsParser
from parsers.jobstreet_parser import JobstreetParser
from parsers.lokerid_parser import LokerIDParser
from database.save_to_mysql import save_csv_to_mysql


# ============================================================
# NORMALISASI URL
# ============================================================

def normalize_url(url):
    """
    Fungsi ini digunakan untuk membersihkan URL lowongan kerja.

    Beberapa portal biasanya menambahkan parameter tambahan pada URL,
    misalnya tanda tanya (?) atau kode tracking. Parameter seperti itu
    tidak diperlukan untuk identifikasi lowongan, sehingga dihapus agar
    proses penghapusan data duplikat menjadi lebih akurat.
    """
    if not isinstance(url, str):
        return ""

    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


# ============================================================
# KEYWORD SMA / SMK
# ============================================================

SMA_SMK_KEYWORDS = [
    # Keyword pendidikan. Digunakan untuk mencari lowongan yang secara
    # langsung menyebutkan syarat pendidikan SMA/SMK.
    "SMA",
    "SMK",
    "lulusan SMA",
    "lulusan SMK",
    "SMA sederajat",
    "SMK sederajat",
    "SMA/SMK",

    # Keyword pekerjaan umum yang sering menerima lulusan SMA/SMK.
    # Keyword ini membantu sistem memperoleh lowongan yang tidak selalu
    # menuliskan syarat pendidikan pada judul, tetapi umum untuk kategori vokasi.
    "admin",
    "admin gudang",
    "operator produksi",
    "staff gudang",
    "kasir",
    "customer service",
    "warehouse",
    "operator",
    "helper",
    "packing",
    "quality control",
    "teknisi",
    "staff toko",
    "barista",
    "sales",
    "driver",
    "kurir",
    "security",
]


# ============================================================
# KEYWORD D3
# ============================================================

D3_KEYWORDS = [
    # Keyword D3 dibuat tidak terlalu banyak agar proses scraping tidak
    # terlalu lama, tetapi tetap mewakili bidang diploma yang umum ditemukan.
    "D3",
    "lulusan D3",
    "D3 administrasi",
    "D3 akuntansi",
    "D3 manajemen",
    "D3 informatika",
    "D3 teknik",
    "D3 keperawatan",
    "D3 farmasi",
    "D3 perpajakan",
]
# ============================================================
# KEYWORD S1 / SARJANA
# ============================================================

S1_KEYWORDS = [
    # Keyword umum untuk jenjang S1/Sarjana.
    "S1",
    "Sarjana",

    # Keyword bidang/jurusan besar yang mewakili rumpun ilmu di UNSRAT.
    # Tidak semua program studi dimasukkan satu per satu agar scraping tidak
    # terlalu berat. Pendekatan ini lebih ringan tetapi tetap mewakili banyak bidang.
    "informatika",
    "teknik",
    "ekonomi",
    "manajemen",
    "akuntansi",
    "hukum",
    "komunikasi",
    "administrasi",
    "pertanian",
    "peternakan",
    "perikanan",
    "kelautan",
    "kedokteran",
    "keperawatan",
    "kesehatan masyarakat",
    "farmasi",
    "matematika",
    "statistika",
    "fisika",
    "kimia",
    "biologi",
    "sastra",
]


# ============================================================
# KEYWORD LOKASI IBU KOTA PROVINSI
# ============================================================

LOCATION_KEYWORDS = [
    # Lokasi menggunakan ibu kota provinsi agar cakupan wilayah Indonesia
    # tetap luas tanpa harus memasukkan seluruh kabupaten/kota.
    # Pendekatan ini dipilih karena ibu kota provinsi umumnya menjadi pusat
    # aktivitas ekonomi, pemerintahan, industri, dan penyedia lowongan kerja.
    "banda aceh",
    "medan",
    "padang",
    "pekanbaru",
    "tanjung pinang",
    "jambi",
    "palembang",
    "pangkal pinang",
    "bengkulu",
    "bandar lampung",

    "jakarta",
    "bandung",
    "semarang",
    "yogyakarta",
    "surabaya",
    "serang",

    "denpasar",
    "mataram",
    "kupang",

    "pontianak",
    "palangka raya",
    "banjarmasin",
    "samarinda",
    "tanjung selor",

    "manado",
    "palu",
    "makassar",
    "kendari",
    "gorontalo",
    "mamuju",

    "ambon",
    "sofifi",

    "jayapura",
    "manokwari",
    "merauke",
    "nabire",
    "wamena",
    "sorong",
]
# ============================================================
# MEMBENTUK KEYWORD FINAL
# ============================================================

def build_keywords():
    """
    Membentuk daftar keyword yang akan digunakan untuk proses scraping.

    Strategi keyword dibuat dalam empat kelompok:
    1. SMA/SMK untuk lowongan vokasi atau pekerjaan tingkat menengah.
    2. D3 untuk lowongan diploma.
    3. S1/Sarjana berdasarkan bidang ilmu utama yang mewakili jurusan di UNSRAT.
    4. Ibu kota provinsi untuk memperluas cakupan lokasi lowongan kerja.

    Daftar keyword sengaja tidak dibuat terlalu banyak agar proses scraping
    tidak berjalan terlalu lama. Namun, keyword tetap cukup mewakili kategori
    pendidikan dan lokasi yang dibutuhkan dalam penelitian.
    """
    keywords = []

    keywords.extend(SMA_SMK_KEYWORDS)
    keywords.extend(D3_KEYWORDS)
    keywords.extend(S1_KEYWORDS)
    keywords.extend(LOCATION_KEYWORDS)

    # Menghapus keyword yang sama tanpa mengubah urutan.
    # Ini penting karena beberapa kata bisa saja muncul di lebih dari satu kelompok.
    clean_keywords = []
    seen = set()

    for keyword in keywords:
        normalized = keyword.strip().lower()

        if normalized and normalized not in seen:
            clean_keywords.append(keyword.strip())
            seen.add(normalized)

    return clean_keywords


# ============================================================
# PROSES UTAMA SCRAPING
# ============================================================

async def main():
    keywords = build_keywords()

    # Setiap portal memiliki parser sendiri agar kode lebih mudah dirawat.
    # Jika suatu saat struktur salah satu website berubah, cukup parser portal itu saja
    # yang diperbaiki tanpa mengubah seluruh sistem.
    parsers = [
        GlintsParser("Glints"),
        JobstreetParser("Jobstreet"),
        LokerIDParser("Loker.id"),
    ]

    all_data = []

    print("=== MEMULAI SCRAPING JOB AGGREGATOR ===")
    print(f"Target: {len(keywords)} keyword pada {len(parsers)} portal\n")

    for parser in parsers:
        for keyword in keywords:
            print(f"\n--- {parser.portal_name} | Keyword: {keyword} ---")

            try:
                data = await parser.scrape(keyword)

                if data:
                    # keyword_sumber disimpan agar kita tahu data tersebut
                    # diperoleh dari keyword pencarian apa.
                    for item in data:
                        item["keyword_sumber"] = item.get("keyword_sumber", keyword)

                    all_data.extend(data)
                    print(f"[BERHASIL] {len(data)} data ditemukan.")
                else:
                    print("[INFO] Tidak ada data ditemukan.")

            except Exception as e:
                # Jika salah satu keyword gagal, proses tidak langsung berhenti.
                # Sistem akan lanjut ke keyword berikutnya agar scraping tetap berjalan.
                print(f"[ERROR] Gagal memproses {parser.portal_name} - {keyword}: {e}")

            # Delay acak digunakan agar request ke website sumber tidak terlalu rapat.
            # Ini membantu mengurangi risiko akses dibatasi oleh portal sumber.
            delay = random.uniform(2, 4)
            print(f"Menunggu {delay:.1f} detik...")
            await asyncio.sleep(delay)

    if all_data:
        df = pd.DataFrame(all_data)

        required_cols = [
            "judul_posisi",
            "nama_perusahaan",
            "lokasi",
            "pendidikan",
            "deskripsi",
            "kualifikasi",
            "link_lowongan",
            "portal_sumber",
            "keyword_sumber",
        ]

        # Jika ada kolom yang tidak dikembalikan oleh salah satu parser,
        # kolom tersebut tetap dibuat agar struktur CSV dan database konsisten.
        for col in required_cols:
            if col not in df.columns:
                df[col] = ""

        df = df[required_cols]

        # Data tanpa judul atau link lowongan tidak digunakan karena tidak cukup valid.
        df = df.dropna(subset=["judul_posisi", "link_lowongan"])

        # Beberapa portal kadang mengembalikan elemen halaman yang bukan lowongan.
        # Pola berikut digunakan untuk membuang data yang tidak relevan.
        invalid_title_patterns = [
                "daftar sebagai pencari kerja",
                "pastikan nomor whatsapp",
                "kembali",
                "untuk perusahaan",
                "pasang lowongan",
                "login",
                "register",
                "rp",
                "juta",
                "gaji",
]

        pattern = "|".join(invalid_title_patterns)

        df = df[
            ~df["judul_posisi"]
            .str.lower()
            .str.contains(pattern, na=False, regex=True)
        ]

        # URL dinormalisasi agar lowongan yang sama tidak masuk berkali-kali
        # hanya karena memiliki parameter URL yang berbeda.
        df["link_normalized"] = df["link_lowongan"].apply(normalize_url)

        # Link rekomendasi bawaan portal tidak dipakai karena biasanya bukan
        # link utama lowongan kerja yang sedang dicari.
        df = df[
            ~df["link_normalized"].str.contains(
                "recommended",
                case=False,
                na=False
            )
        ]

        # Penghapusan duplikat dilakukan dua tahap:
        # 1. Berdasarkan URL normalisasi.
        # 2. Berdasarkan kombinasi judul, perusahaan, dan portal.
        df = df.drop_duplicates(subset=["link_normalized"])
        df = df.drop_duplicates(
            subset=["judul_posisi", "nama_perusahaan", "portal_sumber"]
        )

        df = df.drop(columns=["link_normalized"])

        os.makedirs("data/raw", exist_ok=True)

        output_path = "data/raw/master_raw_data.csv"

        # File CSV digunakan sebagai penyimpanan sementara sebelum data dimasukkan
        # ke MySQL. Encoding utf-8-sig dipakai agar karakter Indonesia terbaca baik.
        df.to_csv(output_path, index=False, encoding="utf-8-sig")

        print("\n=== SCRAPING SELESAI ===")
        print(f"Total data bersih: {len(df)}")
        print(f"File CSV disimpan di: {output_path}")

        print("\n=== MENYIMPAN DATA KE MYSQL ===")
        save_csv_to_mysql(output_path)

        print("\n=== PROSES SELESAI ===")
        print("Data terbaru sudah tersimpan di MySQL.")
        print("Silakan refresh halaman website.")

    else:
        print("\n[PERINGATAN] Tidak ada data yang berhasil diambil.")


if __name__ == "__main__":
    asyncio.run(main())