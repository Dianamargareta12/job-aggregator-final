PETUNJUK MENJALANKAN WORKER LOKAL
=================================

STRUKTUR FILE
-------------
Letakkan file berikut dalam folder utama project:

project/
├── main.py
├── worker.py
├── start_worker.bat
├── .env
├── parsers/
├── database/
└── frontend/


1. PASTIKAN DATABASE RAILWAY SUDAH MENDUKUNG STATUS QUEUED
----------------------------------------------------------

Jalankan pada MySQL Railway:

ALTER TABLE scraping_runs
MODIFY status ENUM(
    'queued',
    'running',
    'success',
    'failed'
) NOT NULL;


2. PASTIKAN FILE .ENV MENGARAH KE MYSQL RAILWAY
-----------------------------------------------

Contoh:

MYSQLHOST=host-mysql-railway
MYSQLPORT=3306
MYSQLUSER=root
MYSQLPASSWORD=password-railway
MYSQLDATABASE=railway

Gunakan nilai asli dari Variables/Connect milik layanan MySQL Railway.
Jangan menggunakan localhost untuk worker jika antrean dibuat di Railway.


3. PASTIKAN DEPENDENSI TERPASANG
-------------------------------

Jalankan:

py -m pip install pymysql python-dotenv pandas playwright

Kemudian, jika browser Playwright belum terpasang:

py -m playwright install chromium


4. MENJALANKAN WORKER
---------------------

Cara pertama:

py worker.py

Cara kedua:

Klik dua kali file:

start_worker.bat

Terminal worker harus tetap terbuka saat tombol Mulai Scraping ditekan
dari panel admin Railway.


5. ALUR KERJA
-------------

Admin Railway:
Klik Mulai Scraping

Database Railway:
status = queued

Worker lokal:
mengambil antrean dan mengubah status = running

Worker menjalankan:
py main.py --run-id <ID>

Main.py:
scraping -> preprocessing -> simpan MySQL

Status akhir:
success atau failed


6. PENGUJIAN
------------

1. Jalankan start_worker.bat.
2. Pastikan terminal menampilkan "Database terhubung".
3. Buka halaman admin Railway.
4. Klik Mulai Scraping.
5. Status seharusnya berubah:
   queued -> running -> success/failed.
6. Periksa data baru pada tabel jobs dan raw_jobs.


7. CARA MENGHENTIKAN
--------------------

Tekan CTRL+C pada terminal.

Karena start_worker.bat memiliki fitur restart otomatis, setelah CTRL+C
Windows mungkin menanyakan "Terminate batch job (Y/N)?". Ketik Y lalu Enter.


8. TROUBLESHOOTING
------------------

A. Environment variable belum lengkap
Pastikan .env berada satu folder dengan worker.py dan main.py.

B. Tidak bisa terhubung ke Railway
Periksa MYSQLHOST, MYSQLPORT, MYSQLUSER, MYSQLPASSWORD, dan MYSQLDATABASE.

C. main.py tidak ditemukan
Pastikan worker.py sejajar dengan main.py.

D. ModuleNotFoundError
Instal modul menggunakan:

py -m pip install -r requirements.txt

atau instal modul yang disebutkan pada pesan error.

E. Playwright browser tidak ditemukan
Jalankan:

py -m playwright install chromium

F. Status tetap queued
Pastikan terminal worker sedang berjalan dan koneksi database berhasil.

G. Status failed
Lihat output terminal worker dan file:

storage/worker.log


CATATAN PENTING
---------------

Laptop harus menyala, terhubung ke internet, dan worker harus aktif agar
permintaan scraping dari panel admin dapat diproses.

Website Railway tetap dapat diakses saat worker mati, tetapi antrean akan
tetap berstatus queued sampai worker lokal dijalankan kembali.
