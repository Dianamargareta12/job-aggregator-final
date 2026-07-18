<?php

// Menjalankan session jika belum aktif.
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// Mengecek apakah aplikasi berjalan di Railway.
$isRailway = getenv("MYSQLHOST") !== false
    && getenv("MYSQLHOST") !== "";

// Konfigurasi database.
if ($isRailway) {
    $host = getenv("MYSQLHOST");
    $port = (int) (getenv("MYSQLPORT") ?: 3306);
    $user = getenv("MYSQLUSER");
    $password = getenv("MYSQLPASSWORD");
    $database = getenv("MYSQLDATABASE");
} else {
    // Konfigurasi database localhost.
    $host = "localhost";
    $port = 3306;
    $user = "root";
    $password = "";
    $database = "job_aggregator_final";
}

mysqli_report(MYSQLI_REPORT_ERROR | MYSQLI_REPORT_STRICT);

try {
    $conn = new mysqli(
        $host,
        $user,
        $password,
        $database,
        $port
    );

    $conn->set_charset("utf8mb4");

} catch (mysqli_sql_exception $error) {
    http_response_code(500);

    die(
        "Koneksi database gagal: " .
        htmlspecialchars($error->getMessage())
    );
}