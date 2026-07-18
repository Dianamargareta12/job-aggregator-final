<?php
require_once __DIR__ . "/auth.php";

$totalJobs = 0;
$totalRawJobs = 0;
$totalSources = 3;

$latestRun = [
    "status" => "belum_ada",
    "started_at" => null,
    "finished_at" => null,
    "raw_glints" => 0,
    "raw_jobstreet" => 0,
    "raw_lokerid" => 0,
    "total_raw" => 0,
    "duplicate_data" => 0,
    "education_not_detected" => 0,
    "total_rejected" => 0,
    "total_clean" => 0,
    "message" => "Belum ada proses scraping."
];

try {
    $result = $conn->query("SELECT COUNT(*) AS total FROM jobs");
    if ($result) {
        $row = $result->fetch_assoc();
        $totalJobs = (int) ($row["total"] ?? 0);
    }

    $result = $conn->query("SELECT COUNT(*) AS total FROM raw_jobs");
    if ($result) {
        $row = $result->fetch_assoc();
        $totalRawJobs = (int) ($row["total"] ?? 0);
    }

    $result = $conn->query(
        "SELECT
            status,
            started_at,
            finished_at,
            raw_glints,
            raw_jobstreet,
            raw_lokerid,
            total_raw,
            duplicate_data,
            education_not_detected,
            total_rejected,
            total_clean,
            message
         FROM scraping_runs
         ORDER BY id DESC
         LIMIT 1"
    );

    if ($result && $result->num_rows > 0) {
        $latestRun = array_merge(
            $latestRun,
            $result->fetch_assoc()
        );
    }
} catch (mysqli_sql_exception $error) {
    $latestRun["message"] =
        "Dashboard belum dapat membaca database: " . $error->getMessage();
}

function formatNumber($value): string
{
    return number_format((int) $value, 0, ",", ".");
}

function formatDateTime($value): string
{
    if (!$value) {
        return "-";
    }

    $timestamp = strtotime($value);
    return $timestamp ? date("d-m-Y H:i:s", $timestamp) : "-";
}

function statusLabel($status): string
{
    return match ($status) {
        "success" => "Berhasil",
        "running" => "Sedang Berjalan",
        "failed" => "Gagal",
        default => "Belum Ada",
    };
}

function statusClass($status): string
{
    return match ($status) {
        "success" => "bg-green-100 text-green-700",
        "running" => "bg-amber-100 text-amber-700",
        "failed" => "bg-red-100 text-red-700",
        default => "bg-slate-100 text-slate-600",
    };
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard Admin | Job Aggregator</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100">
<nav class="bg-slate-900 text-white shadow">
    <div class="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
        <div>
            <h1 class="text-lg font-bold">Job Aggregator Admin</h1>
            <p class="text-xs text-slate-400">Panel Administrator</p>
        </div>

        <div class="flex items-center gap-4">
            <div class="hidden text-right sm:block">
                <p class="text-sm font-medium">
                    <?= htmlspecialchars($_SESSION["admin_nama"] ?? "Administrator") ?>
                </p>
                <p class="text-xs text-slate-400">
                    <?= htmlspecialchars($_SESSION["admin_username"] ?? "admin") ?>
                </p>
            </div>

            <a href="logout.php"
               class="rounded-lg bg-red-600 px-4 py-2 text-sm font-semibold hover:bg-red-700">
                Logout
            </a>
        </div>
    </div>
</nav>

<main class="mx-auto max-w-7xl p-6">
    <section class="mb-8">
        <div class="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
                <h2 class="text-2xl font-bold text-slate-800">
                    Selamat datang,
                    <?= htmlspecialchars($_SESSION["admin_nama"] ?? "Administrator") ?>
                </h2>
                <p class="mt-2 text-slate-500">
                    Pantau data mentah, hasil preprocessing, dan data bersih.
                </p>
            </div>

            <span class="inline-flex rounded-full px-3 py-1 text-sm font-semibold <?= statusClass($latestRun["status"]) ?>">
                Scraping: <?= htmlspecialchars(statusLabel($latestRun["status"])) ?>
            </span>
        </div>
    </section>

    <section class="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        <div class="rounded-xl bg-white p-6 shadow-sm">
            <p class="text-sm font-medium text-slate-500">Data Bersih di Jobs</p>
            <p class="mt-3 text-3xl font-bold text-slate-800"><?= formatNumber($totalJobs) ?></p>
        </div>

        <div class="rounded-xl bg-white p-6 shadow-sm">
            <p class="text-sm font-medium text-slate-500">Raw Jobs Tersimpan</p>
            <p class="mt-3 text-3xl font-bold text-slate-800"><?= formatNumber($totalRawJobs) ?></p>
        </div>

        <div class="rounded-xl bg-white p-6 shadow-sm">
            <p class="text-sm font-medium text-slate-500">Portal Sumber</p>
            <p class="mt-3 text-3xl font-bold text-slate-800"><?= formatNumber($totalSources) ?></p>
        </div>

        <div class="rounded-xl bg-white p-6 shadow-sm">
            <p class="text-sm font-medium text-slate-500">Administrator</p>
            <p class="mt-3 text-lg font-bold text-slate-800">
                <?= htmlspecialchars($_SESSION["admin_username"] ?? "admin") ?>
            </p>
        </div>
    </section>

    <section class="mt-8 rounded-xl bg-white p-6 shadow-sm">
        <div class="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
                <h3 class="text-lg font-bold text-slate-800">Hasil Scraping Terbaru</h3>
                <p class="mt-1 text-sm text-slate-500">
                    Data diambil dari tabel scraping_runs.
                </p>
            </div>

            <a href="scraping_logs.php"
               class="text-sm font-semibold text-blue-600 hover:text-blue-700">
                Lihat semua log
            </a>
        </div>

        <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <div class="rounded-lg border border-slate-200 p-5">
                <p class="text-sm text-slate-500">Raw Glints</p>
                <p class="mt-2 text-2xl font-bold"><?= formatNumber($latestRun["raw_glints"]) ?></p>
            </div>

            <div class="rounded-lg border border-slate-200 p-5">
                <p class="text-sm text-slate-500">Raw Jobstreet</p>
                <p class="mt-2 text-2xl font-bold"><?= formatNumber($latestRun["raw_jobstreet"]) ?></p>
            </div>

            <div class="rounded-lg border border-slate-200 p-5">
                <p class="text-sm text-slate-500">Raw Loker.id</p>
                <p class="mt-2 text-2xl font-bold"><?= formatNumber($latestRun["raw_lokerid"]) ?></p>
            </div>

            <div class="rounded-lg border border-blue-200 bg-blue-50 p-5">
                <p class="text-sm text-blue-700">Total Data Mentah</p>
                <p class="mt-2 text-2xl font-bold text-blue-800"><?= formatNumber($latestRun["total_raw"]) ?></p>
            </div>

            <div class="rounded-lg border border-red-200 bg-red-50 p-5">
                <p class="text-sm text-red-700">Data Ditolak</p>
                <p class="mt-2 text-2xl font-bold text-red-800"><?= formatNumber($latestRun["total_rejected"]) ?></p>
            </div>

            <div class="rounded-lg border border-green-200 bg-green-50 p-5">
                <p class="text-sm text-green-700">Data Bersih</p>
                <p class="mt-2 text-2xl font-bold text-green-800"><?= formatNumber($latestRun["total_clean"]) ?></p>
            </div>

            <div class="rounded-lg border border-slate-200 p-5">
                <p class="text-sm text-slate-500">Data Duplikat</p>
                <p class="mt-2 text-2xl font-bold"><?= formatNumber($latestRun["duplicate_data"]) ?></p>
            </div>

            <div class="rounded-lg border border-slate-200 p-5">
                <p class="text-sm text-slate-500">Pendidikan Tidak Terdeteksi</p>
                <p class="mt-2 text-2xl font-bold">
                    <?= formatNumber($latestRun["education_not_detected"]) ?>
                </p>
            </div>
        </div>

        <div class="mt-6 grid gap-4 rounded-lg bg-slate-50 p-5 text-sm md:grid-cols-3">
            <div>
                <p class="text-slate-500">Mulai</p>
                <p class="mt-1 font-semibold"><?= htmlspecialchars(formatDateTime($latestRun["started_at"])) ?></p>
            </div>

            <div>
                <p class="text-slate-500">Selesai</p>
                <p class="mt-1 font-semibold"><?= htmlspecialchars(formatDateTime($latestRun["finished_at"])) ?></p>
            </div>

            <div>
                <p class="text-slate-500">Pesan</p>
                <p class="mt-1 font-semibold">
                    <?= htmlspecialchars($latestRun["message"] ?: "Tidak ada pesan.") ?>
                </p>
            </div>
        </div>
    </section>

    <section class="mt-8 rounded-xl bg-white p-6 shadow-sm">
        <h3 class="text-lg font-bold text-slate-800">Menu Administrator</h3>

        <div class="mt-5 grid gap-4 md:grid-cols-2 lg:grid-cols-4">
            <a href="manage_jobs.php"
               class="rounded-lg border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-blue-50">
                <h4 class="font-semibold">Kelola Lowongan</h4>
                <p class="mt-2 text-sm text-slate-500">Melihat data bersih pada tabel jobs.</p>
            </a>

            <a href="raw_jobs.php"
               class="rounded-lg border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-blue-50">
                <h4 class="font-semibold">Data Mentah</h4>
                <p class="mt-2 text-sm text-slate-500">Melihat raw, clean, dan rejected.</p>
            </a>

            <a href="run_scraping.php"
               class="rounded-lg border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-blue-50">
                <h4 class="font-semibold">Jalankan Scraping</h4>
                <p class="mt-2 text-sm text-slate-500">Menjalankan main.py dari admin.</p>
            </a>

            <a href="scraping_logs.php"
               class="rounded-lg border border-slate-200 p-5 transition hover:border-blue-400 hover:bg-blue-50">
                <h4 class="font-semibold">Log Scraping</h4>
                <p class="mt-2 text-sm text-slate-500">Melihat riwayat proses scraping.</p>
            </a>
        </div>
    </section>
</main>
</body>
</html>