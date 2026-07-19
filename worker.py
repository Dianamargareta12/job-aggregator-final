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
    Tanpa python-dotenv, worker tetap memakai environment variable Windows.
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
        autocommit=False,
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


def claim_next_queued_run():
    """
    Mengambil satu antrean paling lama secara atomik.

    Baris langsung diubah dari queued menjadi running agar dua worker
    tidak menjalankan scraping run yang sama.
    """
    connection = get_database_connection()

    try:
        connection.begin()

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id
                FROM scraping_runs
                WHERE status = 'queued'
                ORDER BY id ASC
                LIMIT 1
                FOR UPDATE
                """
            )

            row = cursor.fetchone()

            if not row:
                connection.commit()
                return None

            run_id = int(row["id"])

            cursor.execute(
                """
                UPDATE scraping_runs
                SET status = %s,
                    started_at = %s,
                    finished_at = NULL,
                    message = %s
                WHERE id = %s
                  AND status = 'queued'
                """,
                (
                    "running",
                    datetime.now(),
                    "Antrean diambil oleh worker lokal. "
                    "Main.py akan segera dijalankan.",
                    run_id,
                ),
            )

            if cursor.rowcount != 1:
                connection.rollback()
                return None

        connection.commit()
        return run_id

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def mark_run_failed(run_id: int, message: str) -> None:
    """Menandai scraping run gagal jika proses tidak sempat ditangani main.py."""
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

        connection.commit()

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


def get_python_command() -> list[str]:
    """
    Pengguna menjalankan Python menggunakan perintah `py`.
    Pada Windows worker akan memakai `py`; pada sistem lain memakai
    interpreter yang sedang menjalankan worker.
    """
    if os.name == "nt":
        return ["py"]

    return [sys.executable]


def run_main_process(run_id: int) -> int:
    """Menjalankan main.py untuk scraping run tertentu."""
    if not MAIN_PATH.exists():
        raise FileNotFoundError(
            f"main.py tidak ditemukan di: {MAIN_PATH}"
        )

    command = get_python_command() + [
        str(MAIN_PATH),
        "--run-id",
        str(run_id),
    ]

    write_log(
        "Menjalankan perintah: "
        + " ".join(command)
    )

    process = subprocess.Popen(
        command,
        cwd=str(PROJECT_ROOT),
    )

    return_code = process.wait()

    write_log(
        f"Proses main.py untuk run #{run_id} selesai "
        f"dengan exit code {return_code}."
    )

    return return_code


def handle_stop_signal(signum, frame) -> None:
    """Menghentikan worker dengan aman saat Ctrl+C atau terminal ditutup."""
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
    write_log("JOB AGGREGATOR LOCAL WORKER")
    write_log("=" * 60)
    write_log(f"Folder project: {PROJECT_ROOT}")
    write_log(f"Interval pengecekan: {POLL_INTERVAL_SECONDS} detik")

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
            run_id = claim_next_queued_run()

            if run_id is None:
                write_log("Tidak ada antrean. Menunggu...")
                time.sleep(POLL_INTERVAL_SECONDS)
                continue

            write_log(f"Antrean scraping #{run_id} ditemukan.")

            try:
                return_code = run_main_process(run_id)

                if return_code != 0:
                    try:
                        mark_run_failed(
                            run_id,
                            "Worker mendeteksi main.py berhenti dengan "
                            f"exit code {return_code}. Periksa log terminal.",
                        )
                    except Exception as update_error:
                        write_log(
                            "Gagal memperbarui status failed: "
                            f"{update_error}"
                        )

            except Exception as process_error:
                write_log(
                    f"Gagal menjalankan main.py untuk run #{run_id}: "
                    f"{process_error}"
                )

                try:
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