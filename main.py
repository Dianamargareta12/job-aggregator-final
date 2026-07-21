import argparse
import asyncio
import os
import random
from datetime import datetime
from urllib.parse import urlparse, urlunparse

import pandas as pd
import pymysql

from parsers.glints_parser import GlintsParser
from parsers.jobstreet_parser import JobstreetParser
from parsers.lokerid_parser import LokerIDParser
from database.save_to_mysql import save_csv_to_mysql


PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
RAW_DIR = os.path.join(PROJECT_ROOT, "data", "raw")
REJECTED_DIR = os.path.join(PROJECT_ROOT, "data", "rejected")
CLEAN_DIR = os.path.join(PROJECT_ROOT, "data", "clean")

RAW_GLINTS_PATH = os.path.join(RAW_DIR, "raw_glints.csv")
RAW_JOBSTREET_PATH = os.path.join(RAW_DIR, "raw_jobstreet.csv")
RAW_LOKERID_PATH = os.path.join(RAW_DIR, "raw_lokerid.csv")
MASTER_RAW_PATH = os.path.join(RAW_DIR, "master_raw_data.csv")
REJECTED_PATH = os.path.join(REJECTED_DIR, "rejected_jobs.csv")
CLEAN_PATH = os.path.join(CLEAN_DIR, "clean_jobs.csv")

REQUIRED_COLUMNS = [
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

INVALID_TITLE_PATTERNS = [
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


def normalize_url(url):
    if not isinstance(url, str):
        return ""
    url = url.strip()
    if not url:
        return ""
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path.rstrip("/"),
            "",
            "",
            "",
        )
    )


def is_valid_url(url):
    if not isinstance(url, str) or not url.strip():
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme.lower() in {"http", "https"} and bool(parsed.netloc)


SMA_SMK_KEYWORDS = [
    "SMA", "SMK", "lulusan SMA", "lulusan SMK", "SMA sederajat",
    "SMK sederajat", "SMA/SMK", "admin", "admin gudang",
    "operator produksi", "staff gudang", "kasir", "customer service",
    "warehouse", "operator", "helper", "packing", "quality control",
    "teknisi", "staff toko", "barista", "sales", "driver", "kurir",
    "security",
]

D3_KEYWORDS = [
    "D3", "lulusan D3", "D3 administrasi", "D3 akuntansi",
    "D3 manajemen", "D3 informatika", "D3 teknik", "D3 keperawatan",
    "D3 farmasi", "D3 perpajakan",
]

S1_KEYWORDS = [
    "S1", "Sarjana", "informatika", "teknik", "ekonomi", "manajemen",
    "akuntansi", "hukum", "komunikasi", "administrasi", "pertanian",
    "peternakan", "perikanan", "kelautan", "kedokteran", "keperawatan",
    "kesehatan masyarakat", "farmasi", "matematika", "statistika",
    "fisika", "kimia", "biologi", "sastra",
]

LOCATION_KEYWORDS = [
    "banda aceh", "medan", "padang", "pekanbaru", "tanjung pinang",
    "jambi", "palembang", "pangkal pinang", "bengkulu", "bandar lampung",
    "jakarta", "bandung", "semarang", "yogyakarta", "surabaya", "serang",
    "denpasar", "mataram", "kupang", "pontianak", "palangka raya",
    "banjarmasin", "samarinda", "tanjung selor", "manado", "palu",
    "makassar", "kendari", "gorontalo", "mamuju", "ambon", "sofifi",
    "jayapura", "manokwari", "merauke", "nabire", "wamena", "sorong",
]

# Ubah menjadi False jika ingin menjalankan seluruh keyword
TEST_MODE = False

# Keyword yang digunakan saat testing
TEST_KEYWORDS = [
    "admin",
    "D3",
    "manado",
]

def build_keywords():
    """
    Membentuk daftar keyword yang akan digunakan untuk proses scraping.

    Saat TEST_MODE = True, hanya menggunakan beberapa keyword
    agar proses pengujian lebih cepat.
    """

    # Mode Testing
    if TEST_MODE:
        print("\n=== MODE TESTING AKTIF ===")
        print(f"Keyword yang digunakan: {TEST_KEYWORDS}\n")
        return TEST_KEYWORDS

    # Mode Normal
    keywords = SMA_SMK_KEYWORDS + D3_KEYWORDS + S1_KEYWORDS + LOCATION_KEYWORDS

    clean_keywords = []
    seen = set()

    for keyword in keywords:
        normalized = keyword.strip().lower()

        if normalized and normalized not in seen:
            clean_keywords.append(keyword.strip())
            seen.add(normalized)

    return clean_keywords


def get_database_connection():
    required_variables = [
        "MYSQLHOST",
        "MYSQLPORT",
        "MYSQLUSER",
        "MYSQLPASSWORD",
        "MYSQLDATABASE",
    ]

    missing_variables = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing_variables:
        raise RuntimeError(
            "Environment variable database belum lengkap: "
            + ", ".join(missing_variables)
        )

    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
        autocommit=False,
    )


def create_scraping_run():
    connection = get_database_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO scraping_runs (status, started_at, message)
                VALUES (%s, %s, %s)
                """,
                ("running", datetime.now(), "Proses scraping sedang berjalan."),
            )
            run_id = cursor.lastrowid
        connection.commit()
        return run_id
    finally:
        connection.close()


def start_existing_scraping_run(run_id):
    """
    Menggunakan baris scraping_runs yang sudah dibuat oleh panel admin.

    Fungsi ini mengubah status queued menjadi running tanpa membuat
    record scraping_runs baru.
    """
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE scraping_runs
                SET status=%s,
                    started_at=NOW(),
                    finished_at=NULL,
                    message=%s
                WHERE id=%s
                  AND status='queued'
                """,
                (
                    "running",
                    "Worker lokal sedang menjalankan proses scraping.",
                    run_id,
                ),
            )

            if cursor.rowcount == 0:
                raise RuntimeError(
                    f"Scraping run ID {run_id} tidak ditemukan "
                    "atau statusnya sudah tidak dapat dijalankan."
                )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_scraping_run_success(run_id, statistics):
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE scraping_runs
                SET status=%s,
                    finished_at=NOW(),
                    raw_glints=%s,
                    raw_jobstreet=%s,
                    raw_lokerid=%s,
                    total_raw=%s,
                    empty_data=%s,
                    duplicate_data=%s,
                    invalid_url=%s,
                    education_not_detected=%s,
                    total_rejected=%s,
                    total_clean=%s,
                    clean_csv_path=%s,
                    message=%s
                WHERE id=%s
                """,
                (
                    "success",
                    statistics["raw_glints"],
                    statistics["raw_jobstreet"],
                    statistics["raw_lokerid"],
                    statistics["total_raw"],
                    statistics["empty_data"],
                    statistics["duplicate_data"],
                    statistics["invalid_url"],
                    statistics["education_not_detected"],
                    statistics["total_rejected"],
                    statistics["total_clean"],
                    CLEAN_PATH,
                    "Scraping dan preprocessing berhasil diselesaikan.",
                    run_id,
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def update_scraping_run_failed(run_id, message):
    if not run_id:
        return

    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE scraping_runs
                SET status=%s,
                    finished_at=NOW(),
                    message=%s
                WHERE id=%s
                """,
                (
                    "failed",
                    str(message)[:5000],
                    run_id,
                ),
            )

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def clean_database_value(value):
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    return str(value).strip()


def save_raw_jobs_to_database(run_id, raw_status_df):
    if raw_status_df.empty:
        return
    connection = get_database_connection()
    query = """
        INSERT INTO raw_jobs (
            scraping_run_id, portal_sumber, judul_posisi,
            nama_perusahaan, lokasi, pendidikan, deskripsi,
            link_lowongan, validation_status, rejection_reason
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    rows = []
    for _, row in raw_status_df.iterrows():
        rows.append((
            run_id,
            clean_database_value(row.get("portal_sumber")),
            clean_database_value(row.get("judul_posisi")),
            clean_database_value(row.get("nama_perusahaan")),
            clean_database_value(row.get("lokasi")),
            clean_database_value(row.get("pendidikan")),
            clean_database_value(row.get("deskripsi")),
            clean_database_value(row.get("link_lowongan")),
            clean_database_value(row.get("validation_status")) or "raw",
            clean_database_value(row.get("rejection_reason")),
        ))
    try:
        with connection.cursor() as cursor:
            cursor.executemany(query, rows)
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def ensure_required_columns(dataframe, portal_name=None):
    dataframe = dataframe.copy()
    for column in REQUIRED_COLUMNS:
        if column not in dataframe.columns:
            dataframe[column] = ""
    if portal_name:
        dataframe["portal_sumber"] = dataframe["portal_sumber"].replace("", portal_name)
        dataframe["portal_sumber"] = dataframe["portal_sumber"].fillna(portal_name)
    return dataframe[REQUIRED_COLUMNS]

def clean_hidden_characters(value):
    """
    Membersihkan karakter Unicode tersembunyi yang sering terbawa
    dari halaman website saat proses scraping.
    """
    if value is None:
        return ""

    text = str(value)

    hidden_characters = [
        "\u200b",  # Zero Width Space
        "\u200c",  # Zero Width Non-Joiner
        "\u200d",  # Zero Width Joiner
        "\u2060",  # Word Joiner
        "\ufeff",  # Zero Width No-Break Space / BOM
    ]

    for character in hidden_characters:
        text = text.replace(character, "")

    return text

def clean_text_columns(dataframe):
    """
    Membersihkan spasi berlebih dan karakter Unicode tersembunyi.
    """
    dataframe = dataframe.copy()

    for column in REQUIRED_COLUMNS:
        dataframe[column] = (
            dataframe[column]
            .fillna("")
            .astype(str)
            .apply(clean_hidden_characters)
            .str.replace(r"\s+", " ", regex=True)
            .str.strip()
        )

    return dataframe


def save_dataframe_csv(dataframe, output_path):
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    dataframe.to_csv(output_path, index=False, encoding="utf-8-sig")


async def scrape_single_portal(parser, keywords):
    portal_data = []
    for keyword in keywords:
        print(f"\n--- {parser.portal_name} | Keyword: {keyword} ---")
        try:
            data = await parser.scrape(keyword)
            if data:
                for item in data:
                    item["portal_sumber"] = item.get("portal_sumber") or parser.portal_name
                    item["keyword_sumber"] = item.get("keyword_sumber") or keyword
                portal_data.extend(data)
                print(f"[BERHASIL] {len(data)} data ditemukan.")
            else:
                print("[INFO] Tidak ada data ditemukan.")
        except Exception as error:
            print(f"[ERROR] {parser.portal_name} - {keyword}: {error}")
        delay = random.uniform(2, 4)
        print(f"Menunggu {delay:.1f} detik...")
        await asyncio.sleep(delay)

    dataframe = pd.DataFrame(portal_data)
    dataframe = ensure_required_columns(dataframe, parser.portal_name)
    return clean_text_columns(dataframe)


def education_not_detected(value):
    normalized = str(value or "").strip().lower()
    return normalized in {
        "", "-", "tidak ada", "tidak diketahui", "tidak terdeteksi",
        "unknown", "none", "nan",
    }


def preprocess_jobs(raw_dataframe):
    dataframe = raw_dataframe.copy().reset_index(drop=True)
    dataframe["_raw_id"] = range(1, len(dataframe) + 1)
    dataframe["validation_status"] = "raw"
    dataframe["rejection_reason"] = ""
    dataframe["link_normalized"] = dataframe["link_lowongan"].apply(normalize_url)

    available = dataframe["validation_status"].eq("raw")
    mask = (
        dataframe["judul_posisi"].str.strip().eq("")
        | dataframe["link_lowongan"].str.strip().eq("")
    ) & available
    dataframe.loc[mask, ["validation_status", "rejection_reason"]] = [
        "rejected", "Kolom wajib kosong"
    ]

    available = dataframe["validation_status"].eq("raw")
    invalid_pattern = "|".join(INVALID_TITLE_PATTERNS)
    mask = (
        dataframe["judul_posisi"].str.lower()
        .str.contains(invalid_pattern, na=False, regex=True)
        & available
    )
    dataframe.loc[mask, ["validation_status", "rejection_reason"]] = [
        "rejected", "Judul tidak relevan"
    ]

    available = dataframe["validation_status"].eq("raw")
    mask = (
        ~dataframe["link_lowongan"].apply(is_valid_url)
        | dataframe["link_normalized"].str.contains("recommended", case=False, na=False)
    ) & available
    dataframe.loc[mask, ["validation_status", "rejection_reason"]] = [
        "rejected", "URL tidak valid"
    ]

    available = dataframe["validation_status"].eq("raw")
    duplicate_url = dataframe.loc[available, "link_normalized"].duplicated(keep="first")
    duplicate_indexes = dataframe.loc[available].index[duplicate_url]
    dataframe.loc[duplicate_indexes, ["validation_status", "rejection_reason"]] = [
        "rejected", "Data duplikat"
    ]

    available = dataframe["validation_status"].eq("raw")
    identity_columns = ["judul_posisi", "nama_perusahaan", "portal_sumber"]
    identity_values = (
        dataframe.loc[available, identity_columns].astype(str)
        .apply(lambda column: column.str.strip().str.lower())
    )
    duplicate_identity = identity_values.duplicated(
        subset=identity_columns, keep="first"
    )
    duplicate_indexes = dataframe.loc[available].index[duplicate_identity]
    dataframe.loc[duplicate_indexes, ["validation_status", "rejection_reason"]] = [
        "rejected", "Data duplikat"
    ]

    available = dataframe["validation_status"].eq("raw")
    mask = dataframe["pendidikan"].apply(education_not_detected) & available
    dataframe.loc[mask, ["validation_status", "rejection_reason"]] = [
        "rejected", "Pendidikan tidak terdeteksi"
    ]

    dataframe.loc[dataframe["validation_status"].eq("raw"), "validation_status"] = "clean"

    clean_dataframe = dataframe[dataframe["validation_status"].eq("clean")].copy()
    rejected_dataframe = dataframe[dataframe["validation_status"].eq("rejected")].copy()

    clean_dataframe = clean_dataframe[REQUIRED_COLUMNS]
    rejected_dataframe = rejected_dataframe[REQUIRED_COLUMNS + ["rejection_reason"]]
    raw_status_dataframe = dataframe[
        REQUIRED_COLUMNS + ["_raw_id", "validation_status", "rejection_reason"]
    ].copy()

    statistics = {
        "empty_data": int(dataframe["rejection_reason"].eq("Kolom wajib kosong").sum()),
        "invalid_title": int(dataframe["rejection_reason"].eq("Judul tidak relevan").sum()),
        "duplicate_data": int(dataframe["rejection_reason"].eq("Data duplikat").sum()),
        "invalid_url": int(dataframe["rejection_reason"].eq("URL tidak valid").sum()),
        "education_not_detected": int(
            dataframe["rejection_reason"].eq("Pendidikan tidak terdeteksi").sum()
        ),
        "total_rejected": int(len(rejected_dataframe)),
        "total_clean": int(len(clean_dataframe)),
    }
    return clean_dataframe, rejected_dataframe, raw_status_dataframe, statistics


async def main(existing_run_id=None, selected_portal="all"):
    run_id = None
    try:
        os.makedirs(RAW_DIR, exist_ok=True)
        os.makedirs(REJECTED_DIR, exist_ok=True)
        os.makedirs(CLEAN_DIR, exist_ok=True)

        if existing_run_id is None:
            run_id = create_scraping_run()
            print("[MODE MANUAL] Membuat scraping run baru.")
        else:
            run_id = existing_run_id
            start_existing_scraping_run(run_id)
            print(
                f"[MODE WORKER] Menggunakan scraping run yang sudah ada: #{run_id}"
            )
        keywords = build_keywords()

        portal_parsers = {
            "Glints": GlintsParser("Glints"),
            "Jobstreet": JobstreetParser("Jobstreet"),
            "Loker.id": LokerIDParser("Loker.id"),
        }

        if selected_portal == "all":
            parsers = list(portal_parsers.values())
        else:
            selected_parser = portal_parsers.get(selected_portal)

            if selected_parser is None:
                valid_portals = ", ".join(["all", *portal_parsers.keys()])
                raise ValueError(
                    f"Portal tidak valid: {selected_portal}. "
                    f"Pilihan yang tersedia: {valid_portals}"
                )

            parsers = [selected_parser]

        print("=== MEMULAI SCRAPING JOB AGGREGATOR ===")
        print(f"Mode portal: {selected_portal}")
        print(f"Target: {len(keywords)} keyword pada {len(parsers)} portal")
        print(f"Scraping run ID: {run_id}\n")

        portal_dataframes = {}
        for parser in parsers:
            print("\n====================================================")
            print(f"MEMULAI PORTAL: {parser.portal_name}")
            print("====================================================")
            portal_dataframe = await scrape_single_portal(parser, keywords)
            portal_dataframes[parser.portal_name] = portal_dataframe
            print(
                f"\n[PORTAL SELESAI] {parser.portal_name}: "
                f"{len(portal_dataframe)} data mentah"
            )

        glints_dataframe = portal_dataframes.get(
            "Glints", pd.DataFrame(columns=REQUIRED_COLUMNS)
        )
        jobstreet_dataframe = portal_dataframes.get(
            "Jobstreet", pd.DataFrame(columns=REQUIRED_COLUMNS)
        )
        lokerid_dataframe = portal_dataframes.get(
            "Loker.id", pd.DataFrame(columns=REQUIRED_COLUMNS)
        )

        save_dataframe_csv(glints_dataframe, RAW_GLINTS_PATH)
        save_dataframe_csv(jobstreet_dataframe, RAW_JOBSTREET_PATH)
        save_dataframe_csv(lokerid_dataframe, RAW_LOKERID_PATH)

        master_raw_dataframe = pd.concat(
            [glints_dataframe, jobstreet_dataframe, lokerid_dataframe],
            ignore_index=True,
        )
        master_raw_dataframe = ensure_required_columns(master_raw_dataframe)
        master_raw_dataframe = clean_text_columns(master_raw_dataframe)
        save_dataframe_csv(master_raw_dataframe, MASTER_RAW_PATH)

        raw_glints = len(glints_dataframe)
        raw_jobstreet = len(jobstreet_dataframe)
        raw_lokerid = len(lokerid_dataframe)
        total_raw = len(master_raw_dataframe)

        print("\n=== DATA MENTAH BERHASIL DISIMPAN ===")
        print(f"Glints     : {raw_glints}")
        print(f"Jobstreet  : {raw_jobstreet}")
        print(f"Loker.id   : {raw_lokerid}")
        print(f"Total raw  : {total_raw}")

        if master_raw_dataframe.empty:
            raise RuntimeError("Tidak ada data yang berhasil diambil dari seluruh portal.")

        (
            clean_dataframe,
            rejected_dataframe,
            raw_status_dataframe,
            preprocessing_statistics,
        ) = preprocess_jobs(master_raw_dataframe)

        save_dataframe_csv(rejected_dataframe, REJECTED_PATH)
        save_dataframe_csv(clean_dataframe, CLEAN_PATH)

        statistics = {
            "raw_glints": raw_glints,
            "raw_jobstreet": raw_jobstreet,
            "raw_lokerid": raw_lokerid,
            "total_raw": total_raw,
            **preprocessing_statistics,
        }

        save_raw_jobs_to_database(run_id, raw_status_dataframe)

        print("\n=== MENYIMPAN DATA BERSIH KE MYSQL ===")
        if clean_dataframe.empty:
            raise RuntimeError("Tidak ada data bersih yang lolos preprocessing.")
        save_csv_to_mysql(CLEAN_PATH)

        update_scraping_run_success(run_id, statistics)

        print("\n=== PROSES SELESAI ===")
        print(f"Data mentah Glints          : {raw_glints}")
        print(f"Data mentah Jobstreet       : {raw_jobstreet}")
        print(f"Data mentah Loker.id        : {raw_lokerid}")
        print(f"Total data mentah           : {total_raw}")
        print(f"Kolom wajib kosong          : {statistics['empty_data']}")
        print(f"Judul tidak relevan         : {statistics['invalid_title']}")
        print(f"URL tidak valid             : {statistics['invalid_url']}")
        print(f"Data duplikat               : {statistics['duplicate_data']}")
        print(f"Pendidikan tidak terdeteksi : {statistics['education_not_detected']}")
        print(f"Total data ditolak          : {statistics['total_rejected']}")
        print(f"Total data bersih           : {statistics['total_clean']}")
        print(f"\nRaw Glints     : {RAW_GLINTS_PATH}")
        print(f"Raw Jobstreet  : {RAW_JOBSTREET_PATH}")
        print(f"Raw Loker.id   : {RAW_LOKERID_PATH}")
        print(f"Rejected CSV   : {REJECTED_PATH}")
        print(f"Clean CSV      : {CLEAN_PATH}")
        print("\nData terbaru sudah tersimpan di MySQL.")
        print("Silakan refresh dashboard dan website.")

    except Exception as error:
        print("\n=== PROSES GAGAL ===")
        print(f"[ERROR] {error}")
        try:
            update_scraping_run_failed(run_id, str(error))
        except Exception as update_error:
            print(f"[ERROR] Gagal memperbarui status scraping: {update_error}")
        raise


if __name__ == "__main__":
    argument_parser = argparse.ArgumentParser(
        description="Menjalankan scraping Job Aggregator."
    )
    argument_parser.add_argument(
        "--run-id",
        type=int,
        default=None,
        help=(
            "ID pada tabel scraping_runs yang sudah dibuat oleh panel admin. "
            "Jika tidak diberikan, main.py akan membuat scraping run baru."
        ),
    )
    argument_parser.add_argument(
        "--portal",
        type=str,
        default="all",
        choices=[
            "all",
            "Glints",
            "Jobstreet",
            "Loker.id",
        ],
        help=(
            "Portal yang akan di-scrape. Gunakan 'all' untuk semua portal, "
            "atau pilih Glints, Jobstreet, maupun Loker.id."
        ),
    )

    arguments = argument_parser.parse_args()

    asyncio.run(
        main(
            existing_run_id=arguments.run_id,
            selected_portal=arguments.portal,
        )
    )