import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pymysql
from pymysql.cursors import DictCursor

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None


PROJECT_ROOT = Path(__file__).resolve().parent
MAIN_PATH = PROJECT_ROOT / "main.py"
LOG_DIR = PROJECT_ROOT / "storage"
WORKER_LOG_PATH = LOG_DIR / "worker.log"

POLL_INTERVAL_SECONDS = int(os.getenv("WORKER_POLL_INTERVAL", "5"))
RECONNECT_DELAY_SECONDS = int(os.getenv("WORKER_RECONNECT_DELAY", "10"))

STOP_REQUESTED = False


def write_log(message: str) -> None:
    """Menampilkan log di terminal dan menyimpannya ke storage/worker.log."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] {message}"

    print(formatted, flush=True)

    with WORKER_LOG_PATH.open("a", encoding="utf-8") as log_file:
        log_file.write(formatted + "\n")


def load_environment() -> None:
    """
    Membaca file .env dari folder project jika python-dotenv tersedia.
    """
    if load_dotenv is not None:
        env_path = PROJECT_ROOT / ".env"
        load_dotenv(dotenv_path=env_path, override=False)


def get_database_connection():
    """Membuat koneksi ke database MySQL Railway."""
    required_variables = [
        "MYSQLHOST",
        "MYSQLPORT",
        "MYSQLUSER",
        "MYSQLPASSWORD",
        "MYSQLDATABASE",
    ]

    missing = [
        variable
        for variable in required_variables
        if not os.getenv(variable)
    ]

    if missing:
        raise RuntimeError(
            "Environment variable database belum lengkap: "
            + ", ".join(missing)
        )

    return pymysql.connect(
        host=os.getenv("MYSQLHOST"),
        port=int(os.getenv("MYSQLPORT", "3306")),
        user=os.getenv("MYSQLUSER"),
        password=os.getenv("MYSQLPASSWORD"),
        database=os.getenv("MYSQLDATABASE"),
        charset="utf8mb4",
        cursorclass=DictCursor,
        autocommit=True,
        connect_timeout=15,
        read_timeout=30,
        write_timeout=30,
    )


def test_database_connection() -> None:
    """Memastikan worker dapat terhubung ke database Railway."""
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT DATABASE() AS database_name")
            result = cursor.fetchone()

        write_log(
            "Database terhubung: "
            + str(result.get("database_name", "-"))
        )
    finally:
        connection.close()


def get_next_queued_run():
    """
    Membaca satu antrean queued paling lama beserta portal yang dipilih.

    Nilai portal yang didukung:
    - all
    - Glints
    - Jobstreet
    - Loker.id

    Worker tidak mengubah status. main.py yang akan mengubah:
    queued -> running -> success/failed.
    """
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, portal
                FROM scraping_runs
                WHERE status = 'queued'
                ORDER BY id ASC
                LIMIT 1
                """
            )
            row = cursor.fetchone()

        if not row:
            return None

        portal = str(row.get("portal") or "all").strip()

        allowed_portals = {
            "all",
            "Glints",
            "Jobstreet",
            "Loker.id",
        }

        if portal not in allowed_portals:
            raise RuntimeError(
                f"Portal pada antrean tidak valid: {portal}. "
                "Pilihan yang diperbolehkan: "
                "all, Glints, Jobstreet, Loker.id."
            )

        return {
            "id": int(row["id"]),
            "portal": portal,
        }

    finally:
        connection.close()


def get_run_status(run_id: int):
    """Membaca status scraping run tertentu."""
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT status, message
                FROM scraping_runs
                WHERE id = %s
                LIMIT 1
                """,
                (run_id,),
            )
            return cursor.fetchone()
    finally:
        connection.close()


def mark_run_failed(run_id: int, message: str) -> None:
    """
    Menandai run gagal hanya jika main.py tidak sempat memperbaruinya.
    """
    connection = get_database_connection()

    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                UPDATE scraping_runs
                SET status = %s,
                    finished_at = %s,
                    message = %s
                WHERE id = %s
                  AND status IN ('queued', 'running')
                """,
                (
                    "failed",
                    datetime.now(),
                    str(message)[:5000],
                    run_id,
                ),
            )
    finally:
        connection.close()


def get_python_command() -> list[str]:
    """
    Pada Windows menggunakan perintah `py`.
    Pada sistem lain memakai interpreter aktif.
    """
    if os.name == "nt":
        return ["py"]

    return [sys.executable]


def run_main_process(run_id: int, portal: str) -> int:
    """
    Menjalankan main.py dengan scraping run ID dan portal
    yang dipilih dari antrean.
    """
    if not MAIN_PATH.exists():
        raise FileNotFoundError(
            f"main.py tidak ditemukan di: {MAIN_PATH}"
        )

    command = get_python_command() + [
        str(MAIN_PATH),
        "--run-id",
        str(run_id),
        "--portal",
        portal,
    ]

    write_log("Menjalankan perintah: " + " ".join(command))

    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
    )

    return_code = process.wait()

    write_log(
        f"main.py untuk run #{run_id} "
        f"portal {portal} selesai "
        f"dengan exit code {return_code}."
    )

    return return_code


def handle_stop_signal(signum, frame) -> None:
    """Menghentikan worker dengan aman."""
    global STOP_REQUESTED
    STOP_REQUESTED = True
    write_log("Permintaan berhenti diterima. Worker akan dihentikan.")


def run_worker() -> None:
    global STOP_REQUESTED

    load_environment()

    signal.signal(signal.SIGINT, handle_stop_signal)

    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, handle_stop_signal)

    write_log("=" * 60)
    write_log("JOB AGGREGATOR LOCAL WORKER V3 - PORTAL SELECTOR")
    write_log("=" * 60)
    write_log(f"Folder project: {PROJECT_ROOT}")
    write_log(f"Interval pengecekan: {POLL_INTERVAL_SECONDS} detik")
    write_log("Perubahan status dikelola sepenuhnya oleh main.py.")

    while not STOP_REQUESTED:
        try:
            test_database_connection()
            break
        except Exception as error:
            write_log(f"Koneksi database gagal: {error}")
            write_log(
                f"Mencoba kembali dalam {RECONNECT_DELAY_SECONDS} detik."
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

    while not STOP_REQUESTED:
        try:
            run_data = get_next_queued_run()

            if run_data is None:
                write_log("Tidak ada antrean. Menunggu...")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            run_id = run_data["id"]
            portal = run_data["portal"]

            write_log(
                f"Antrean scraping #{run_id} ditemukan. "
                f"Portal: {portal}"
            )

            try:
                return_code = run_main_process(run_id, portal)

                status_data = get_run_status(run_id)
                current_status = (
                    status_data.get("status")
                    if status_data
                    else None
                )

                if return_code == 0:
                    write_log(
                        f"Status akhir run #{run_id}: "
                        f"{current_status or 'tidak ditemukan'}."
                    )
                else:
                    write_log(
                        f"main.py gagal untuk run #{run_id}. "
                        f"Status database: {current_status or '-'}."
                    )

                    if current_status in {"queued", "running"}:
                        mark_run_failed(
                            run_id,
                            "Worker mendeteksi main.py berhenti dengan "
                            f"exit code {return_code}. Periksa output terminal "
                            "dan storage/worker.log.",
                        )

            except Exception as process_error:
                write_log(
                    f"Gagal menjalankan main.py untuk run #{run_id}: "
                    f"{process_error}"
                )

                try:
                    status_data = get_run_status(run_id)
                    current_status = (
                        status_data.get("status")
                        if status_data
                        else None
                    )

                    if current_status in {"queued", "running"}:
                        mark_run_failed(
                            run_id,
                            "Worker gagal menjalankan main.py: "
                            f"{process_error}",
                        )
                except Exception as update_error:
                    write_log(
                        "Gagal memperbarui status failed: "
                        f"{update_error}"
                    )

        except pymysql.MySQLError as database_error:
            write_log(f"Kesalahan database: {database_error}")
            write_log(
                f"Mencoba kembali dalam {RECONNECT_DELAY_SECONDS} detik."
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

        except Exception as error:
            write_log(f"Kesalahan worker: {error}")
            write_log(
                f"Mencoba kembali dalam {RECONNECT_DELAY_SECONDS} detik."
            )
            time.sleep(RECONNECT_DELAY_SECONDS)

    write_log("Worker berhenti.")


if __name__ == "__main__":
    run_worker()