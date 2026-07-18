import os

import pandas as pd
import pymysql


# ============================================================
# DETEKSI PENDIDIKAN
# ============================================================

def detect_education(row):
    """
    Menentukan jenjang pendidikan berdasarkan informasi lowongan.

    keyword_sumber tidak dipakai untuk menentukan pendidikan karena
    keyword pencarian belum tentu sama dengan persyaratan lowongan.
    """

    text = " ".join([
        str(row.get("pendidikan", "")),
        str(row.get("judul_posisi", "")),
        str(row.get("kualifikasi", "")),
        str(row.get("deskripsi", "")),
    ]).lower()

    # Urutan dibuat dari penyebutan yang lebih spesifik.
    if "smk" in text:
        return "SMK"

    if "sma" in text:
        return "SMA"

    if (
        "d3" in text
        or "diploma" in text
        or "d1 - d4" in text
        or "d1-d4" in text
    ):
        return "D3"

    if "s1" in text or "sarjana" in text:
        return "S1"

    return clean_text(row.get("pendidikan", ""), 100)


# ============================================================
# NORMALISASI PORTAL
# ============================================================

def normalize_portal(value):
    text = str(value or "").strip().lower()

    if "glints" in text:
        return "Glints"

    if "jobstreet" in text:
        return "Jobstreet"

    if "loker" in text:
        return "Loker.id"

    return str(value or "").strip()


# ============================================================
# PEMBERSIHAN TEKS
# ============================================================

def clean_text(value, limit=None):
    """
    Membersihkan karakter null dan karakter Unicode tersembunyi.
    Emoji tetap dipertahankan karena database menggunakan utf8mb4.
    """

    if value is None:
        return ""

    text = str(value)

    hidden_characters = [
        "\x00",
        "\u200b",
        "\u200c",
        "\u200d",
        "\u2060",
        "\ufeff",
    ]

    for character in hidden_characters:
        text = text.replace(character, "")

    text = " ".join(text.split()).strip()

    if limit is not None:
        return text[:limit]

    return text


# ============================================================
# MENENTUKAN PATH CSV
# ============================================================

def resolve_csv_path(csv_path):
    """
    Memastikan file CSV dapat ditemukan ketika dijalankan dari
    folder utama project maupun folder database.
    """

    if os.path.isabs(csv_path) and os.path.exists(csv_path):
        return csv_path

    if os.path.exists(csv_path):
        return os.path.abspath(csv_path)

    project_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..")
    )

    project_path = os.path.join(project_root, csv_path)

    if os.path.exists(project_path):
        return project_path

    raise FileNotFoundError(
        f"File CSV tidak ditemukan: {csv_path}"
    )


# ============================================================
# KONEKSI DATABASE
# ============================================================

def get_database_connection():
    """
    Mendukung koneksi localhost dan Railway melalui environment variable.
    """

    return pymysql.connect(
        host=os.getenv("MYSQLHOST", "localhost"),
        port=int(os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("MYSQLUSER", "root"),
        password=os.getenv("MYSQLPASSWORD", ""),
        database=os.getenv(
            "MYSQLDATABASE",
            "job_aggregator_final",
        ),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


# ============================================================
# MENYIAPKAN DATAFRAME
# ============================================================

def prepare_dataframe(csv_path):
    dataframe = pd.read_csv(
        csv_path,
        encoding="utf-8-sig",
    )

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

    for column in required_columns:
        if column not in dataframe.columns:
            dataframe[column] = ""

    dataframe = dataframe[required_columns]
    dataframe = dataframe.fillna("")

    dataframe["portal_sumber"] = (
        dataframe["portal_sumber"]
        .apply(normalize_portal)
    )

    dataframe["judul_posisi"] = (
        dataframe["judul_posisi"]
        .apply(lambda value: clean_text(value, 255))
    )

    dataframe["nama_perusahaan"] = (
        dataframe["nama_perusahaan"]
        .apply(lambda value: clean_text(value, 255))
    )

    dataframe["lokasi"] = (
        dataframe["lokasi"]
        .apply(lambda value: clean_text(value, 255))
    )

    dataframe["deskripsi"] = (
        dataframe["deskripsi"]
        .apply(lambda value: clean_text(value))
    )

    dataframe["kualifikasi"] = (
        dataframe["kualifikasi"]
        .apply(lambda value: clean_text(value))
    )

    dataframe["link_lowongan"] = (
        dataframe["link_lowongan"]
        .apply(lambda value: clean_text(value))
    )

    dataframe["keyword_sumber"] = (
        dataframe["keyword_sumber"]
        .apply(lambda value: clean_text(value, 255))
    )

    # Deteksi dilakukan setelah kolom teks dibersihkan.
    dataframe["pendidikan"] = dataframe.apply(
        detect_education,
        axis=1,
    )

    dataframe["pendidikan"] = (
        dataframe["pendidikan"]
        .apply(lambda value: clean_text(value, 100))
    )

    # Data tanpa judul atau URL tidak dimasukkan ke jobs.
    dataframe = dataframe[
        dataframe["judul_posisi"].ne("")
        & dataframe["link_lowongan"].ne("")
    ].copy()

    # Perlindungan tambahan terhadap duplikasi.
    dataframe = dataframe.drop_duplicates(
        subset=["link_lowongan"],
        keep="first",
    )

    dataframe = dataframe.drop_duplicates(
        subset=[
            "judul_posisi",
            "nama_perusahaan",
            "portal_sumber",
        ],
        keep="first",
    )

    return dataframe.reset_index(drop=True)


# ============================================================
# MEMASTIKAN TABEL JOBS
# ============================================================

def ensure_jobs_table(cursor):
    """
    Membuat tabel jobs jika belum tersedia dan memastikan charset utf8mb4.
    """

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id INT AUTO_INCREMENT PRIMARY KEY,
            judul_posisi VARCHAR(255) NULL,
            nama_perusahaan VARCHAR(255) NULL,
            lokasi TEXT NULL,
            pendidikan VARCHAR(100) NULL,
            deskripsi LONGTEXT NULL,
            kualifikasi LONGTEXT NULL,
            link_lowongan TEXT NULL,
            portal_sumber VARCHAR(100) NULL,
            keyword_sumber VARCHAR(255) NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            INDEX idx_jobs_portal (portal_sumber),
            INDEX idx_jobs_pendidikan (pendidikan),
            INDEX idx_jobs_created_at (created_at)
        )
        ENGINE=InnoDB
        DEFAULT CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
        """
    )

    # CREATE TABLE IF NOT EXISTS tidak mengubah tabel lama.
    # Karena itu tabel lama juga dipastikan memakai utf8mb4.
    cursor.execute(
        """
        ALTER TABLE jobs
        CONVERT TO CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
        """
    )

    additional_columns = [
        ("deskripsi", "LONGTEXT NULL"),
        ("kualifikasi", "LONGTEXT NULL"),
        ("keyword_sumber", "VARCHAR(255) NULL"),
        (
            "created_at",
            "TIMESTAMP DEFAULT CURRENT_TIMESTAMP",
        ),
    ]

    for column_name, column_definition in additional_columns:
        cursor.execute(
            f"SHOW COLUMNS FROM jobs LIKE '{column_name}'"
        )

        if cursor.fetchone() is None:
            cursor.execute(
                f"""
                ALTER TABLE jobs
                ADD COLUMN {column_name} {column_definition}
                """
            )


# ============================================================
# TABEL SEMENTARA
# ============================================================

def create_temporary_jobs_table(cursor):
    """
    Menggunakan tabel sementara agar data jobs lama tidak langsung
    hilang ketika proses insert data baru mengalami kegagalan.
    """

    cursor.execute(
        """
        DROP TEMPORARY TABLE IF EXISTS jobs_import
        """
    )

    cursor.execute(
        """
        CREATE TEMPORARY TABLE jobs_import (
            judul_posisi VARCHAR(255) NULL,
            nama_perusahaan VARCHAR(255) NULL,
            lokasi TEXT NULL,
            pendidikan VARCHAR(100) NULL,
            deskripsi LONGTEXT NULL,
            kualifikasi LONGTEXT NULL,
            link_lowongan TEXT NULL,
            portal_sumber VARCHAR(100) NULL,
            keyword_sumber VARCHAR(255) NULL
        )
        ENGINE=InnoDB
        DEFAULT CHARACTER SET utf8mb4
        COLLATE utf8mb4_unicode_ci
        """
    )


# ============================================================
# MENYIMPAN CSV KE MYSQL
# ============================================================

def save_csv_to_mysql(
    csv_path="data/clean/clean_jobs.csv",
):
    csv_path = resolve_csv_path(csv_path)

    dataframe = prepare_dataframe(csv_path)

    if dataframe.empty:
        raise ValueError(
            "CSV tidak memiliki data bersih yang dapat disimpan."
        )

    connection = get_database_connection()

    insert_import_query = """
        INSERT INTO jobs_import (
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
        VALUES (
            %s, %s, %s, %s, %s,
            %s, %s, %s, %s
        )
    """

    rows = [
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
        )
        for _, row in dataframe.iterrows()
    ]

    try:
        with connection.cursor() as cursor:
            ensure_jobs_table(cursor)
            create_temporary_jobs_table(cursor)

            # Masukkan seluruh data ke tabel sementara.
            cursor.executemany(
                insert_import_query,
                rows,
            )

            cursor.execute(
                """
                SELECT COUNT(*) AS total
                FROM jobs_import
                """
            )

            imported_total = int(
                cursor.fetchone()["total"]
            )

            if imported_total != len(dataframe):
                raise RuntimeError(
                    "Jumlah data pada tabel sementara "
                    "tidak sesuai dengan jumlah data CSV."
                )

            # Data lama baru dikosongkan setelah import sementara berhasil.
            cursor.execute("DELETE FROM jobs")

            cursor.execute(
                """
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
                SELECT
                    judul_posisi,
                    nama_perusahaan,
                    lokasi,
                    pendidikan,
                    deskripsi,
                    kualifikasi,
                    link_lowongan,
                    portal_sumber,
                    keyword_sumber
                FROM jobs_import
                """
            )

        connection.commit()

        print(
            f"[MYSQL] {len(dataframe)} data berhasil "
            "dimasukkan ke tabel jobs."
        )

    except Exception as error:
        connection.rollback()

        print(
            f"[MYSQL ERROR] {error}"
        )

        raise

    finally:
        connection.close()


# ============================================================
# MENJALANKAN FILE LANGSUNG
# ============================================================

if __name__ == "__main__":
    save_csv_to_mysql(
        "data/clean/clean_jobs.csv"
    )