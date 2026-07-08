import os
import pandas as pd
import pymysql


PORTAL_SOURCES = [
    {
        "nama_portal": "Glints",
        "url_portal": "https://glints.com",
        "status_portal": "Aktif",
        "deskripsi": "Portal sumber lowongan kerja Glints."
    },
    {
        "nama_portal": "Jobstreet",
        "url_portal": "https://www.jobstreet.co.id",
        "status_portal": "Aktif",
        "deskripsi": "Portal sumber lowongan kerja Jobstreet."
    },
    {
        "nama_portal": "Loker.id",
        "url_portal": "https://www.loker.id",
        "status_portal": "Aktif",
        "deskripsi": "Portal sumber lowongan kerja Loker.id."
    },
]


def detect_education(row):
    text = f"{row.get('keyword_sumber', '')} {row.get('pendidikan', '')} {row.get('judul_posisi', '')} {row.get('kualifikasi', '')}".lower()

    if "smk" in text:
        return "SMK"
    if "sma" in text:
        return "SMA"
    if "d3" in text or "diploma" in text:
        return "D3"
    if "s1" in text or "sarjana" in text:
        return "S1"

    return row.get("pendidikan", "")


def normalize_portal(value):
    text = str(value).strip().lower()

    if "glints" in text:
        return "Glints"
    if "jobstreet" in text:
        return "Jobstreet"
    if "loker" in text:
        return "Loker.id"

    return str(value).strip()


def clean_text(value, limit=None):
    text = str(value).replace("\x00", "").strip()

    if limit:
        return text[:limit]

    return text


def resolve_csv_path(csv_path):
    """
    Membantu agar file tetap bisa dijalankan dari root project:
    py database/save_to_mysql.py

    atau dari folder database:
    py save_to_mysql.py
    """
    if os.path.exists(csv_path):
        return csv_path

    project_root_path = os.path.join(os.path.dirname(__file__), "..", csv_path)

    if os.path.exists(project_root_path):
        return project_root_path

    raise FileNotFoundError(f"File CSV tidak ditemukan: {csv_path}")


def save_csv_to_mysql(csv_path="data/raw/master_raw_data.csv"):
    csv_path = resolve_csv_path(csv_path)

    df = pd.read_csv(csv_path)

    required_columns = [
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

    for col in required_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[required_columns]
    df = df.fillna("")

    df["pendidikan"] = df.apply(detect_education, axis=1)
    df["portal_sumber"] = df["portal_sumber"].apply(normalize_portal)

    df["judul_posisi"] = df["judul_posisi"].apply(lambda x: clean_text(x, 255))
    df["nama_perusahaan"] = df["nama_perusahaan"].apply(lambda x: clean_text(x, 255))
    df["lokasi"] = df["lokasi"].apply(lambda x: clean_text(x, 255))
    df["pendidikan"] = df["pendidikan"].apply(lambda x: clean_text(x, 100))
    df["portal_sumber"] = df["portal_sumber"].apply(lambda x: clean_text(x, 100))
    df["keyword_sumber"] = df["keyword_sumber"].apply(lambda x: clean_text(x, 255))
    df["deskripsi"] = df["deskripsi"].apply(lambda x: clean_text(x, 1000))
    df["kualifikasi"] = df["kualifikasi"].apply(lambda x: clean_text(x, 1000))

    conn = pymysql.connect(
        host=os.getenv("MYSQLHOST", "localhost"),
        port=int(os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv("MYSQLDATABASE", "job_aggregator"),
        charset="utf8mb4",
    )

    try:
        with conn.cursor() as cursor:
            # ------------------------------------------------------------------
            # TABEL JOBS
            # Menyimpan data utama lowongan kerja hasil scraping.
            # ------------------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    judul_posisi VARCHAR(255),
                    nama_perusahaan VARCHAR(255),
                    lokasi TEXT,
                    pendidikan VARCHAR(100),
                    deskripsi TEXT,
                    kualifikasi TEXT,
                    link_lowongan TEXT,
                    portal_sumber VARCHAR(100),
                    keyword_sumber VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # ------------------------------------------------------------------
            # TABEL SOURCES
            # Menyimpan daftar portal sumber scraping.
            # ------------------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    nama_portal VARCHAR(100),
                    url_portal VARCHAR(255),
                    status_portal VARCHAR(50),
                    deskripsi TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    ON UPDATE CURRENT_TIMESTAMP
                );
            """)

            # ------------------------------------------------------------------
            # TABEL SCRAPING_LOGS
            # Menyimpan riwayat proses penyimpanan data scraping ke database.
            # ------------------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scraping_logs (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    portal_sumber VARCHAR(100),
                    keyword VARCHAR(255),
                    total_data INT,
                    status VARCHAR(50),
                    keterangan TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)

            # Memastikan kolom tambahan pada tabel jobs tetap tersedia
            for col_name, col_type in [
                ("deskripsi", "TEXT"),
                ("kualifikasi", "TEXT"),
                ("keyword_sumber", "VARCHAR(255)"),
                ("created_at", "TIMESTAMP DEFAULT CURRENT_TIMESTAMP"),
            ]:
                cursor.execute(f"SHOW COLUMNS FROM jobs LIKE '{col_name}'")
                if cursor.fetchone() is None:
                    cursor.execute(f"ALTER TABLE jobs ADD {col_name} {col_type}")

            # Mengisi tabel sources jika data portal belum tersedia
            for source in PORTAL_SOURCES:
                cursor.execute(
                    "SELECT id FROM sources WHERE nama_portal = %s LIMIT 1",
                    (source["nama_portal"],),
                )
                existing_source = cursor.fetchone()

                if existing_source is None:
                    cursor.execute(
                        """
                        INSERT INTO sources (
                            nama_portal,
                            url_portal,
                            status_portal,
                            deskripsi
                        )
                        VALUES (%s, %s, %s, %s)
                        """,
                        (
                            source["nama_portal"],
                            source["url_portal"],
                            source["status_portal"],
                            source["deskripsi"],
                        ),
                    )

            # Mengosongkan tabel jobs agar data lama tidak tercampur dengan hasil scraping terbaru
            cursor.execute("TRUNCATE TABLE jobs")

            sql = """
                INSERT INTO jobs (
                    judul_posisi,
                    nama_perusahaan,
                    lokasi,
                    pendidikan,
                    deskripsi,
                    kualifikasi,
                    link_lowongan,
                    portal_sumber,
                    keyword_sumber
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """

            for _, row in df.iterrows():
                cursor.execute(
                    sql,
                    (
                        row["judul_posisi"],
                        row["nama_perusahaan"],
                        row["lokasi"],
                        row["pendidikan"],
                        row["deskripsi"],
                        row["kualifikasi"],
                        row["link_lowongan"],
                        row["portal_sumber"],
                        row["keyword_sumber"],
                    ),
                )

            # Menyimpan log proses scraping berdasarkan portal sumber
            portal_groups = df.groupby("portal_sumber")

            for portal_sumber, group in portal_groups:
                keywords = ", ".join(sorted(set(group["keyword_sumber"].astype(str))))[:255]
                total_data = len(group)

                cursor.execute(
                    """
                    INSERT INTO scraping_logs (
                        portal_sumber,
                        keyword,
                        total_data,
                        status,
                        keterangan
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        portal_sumber,
                        keywords,
                        total_data,
                        "Berhasil",
                        f"{total_data} data berhasil disimpan dari portal {portal_sumber}.",
                    ),
                )

        conn.commit()
        print(f"[MYSQL] {len(df)} data berhasil dimasukkan ke tabel jobs.")
        print("[MYSQL] Tabel sources berhasil dibuat/diperbarui.")
        print("[MYSQL] Log scraping berhasil disimpan ke tabel scraping_logs.")

    except Exception as e:
        conn.rollback()
        print(f"[MYSQL ERROR] {e}")
        raise

    finally:
        conn.close()


if __name__ == "__main__":
    save_csv_to_mysql()
