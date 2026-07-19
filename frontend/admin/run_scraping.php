<?php

declare(strict_types=1);

require_once __DIR__ . "/auth.php";

/*
|--------------------------------------------------------------------------
| CSRF Token
|--------------------------------------------------------------------------
*/

if (empty($_SESSION["csrf_token"])) {
    $_SESSION["csrf_token"] = bin2hex(random_bytes(32));
}

/*
|--------------------------------------------------------------------------
| Variabel pesan
|--------------------------------------------------------------------------
*/

$message = "";
$errorMessage = "";

/*
|--------------------------------------------------------------------------
| Fungsi mengambil proses aktif
|--------------------------------------------------------------------------
|
| Proses dianggap aktif apabila statusnya:
| - queued  : menunggu worker lokal
| - running : sedang dikerjakan worker lokal
|
*/

function getActiveScrapingRun(mysqli $conn): ?array
{
    $sql = "
        SELECT
            id,
            status,
            started_at,
            finished_at,
            message,
            created_at
        FROM scraping_runs
        WHERE status IN ('queued', 'running')
        ORDER BY id DESC
        LIMIT 1
    ";

    $result = $conn->query($sql);

    if (!$result) {
        throw new RuntimeException(
            "Gagal membaca proses scraping aktif: " . $conn->error
        );
    }

    $row = $result->fetch_assoc();

    return $row ?: null;
}

/*
|--------------------------------------------------------------------------
| Fungsi mengambil proses terakhir
|--------------------------------------------------------------------------
*/

function getLatestScrapingRun(mysqli $conn): ?array
{
    $sql = "
        SELECT
            id,
            status,
            started_at,
            finished_at,
            raw_glints,
            raw_jobstreet,
            raw_lokerid,
            total_raw,
            total_rejected,
            total_clean,
            message,
            created_at
        FROM scraping_runs
        ORDER BY id DESC
        LIMIT 1
    ";

    $result = $conn->query($sql);

    if (!$result) {
        throw new RuntimeException(
            "Gagal membaca proses scraping terakhir: " . $conn->error
        );
    }

    $row = $result->fetch_assoc();

    return $row ?: null;
}

/*
|--------------------------------------------------------------------------
| Fungsi mengambil riwayat scraping
|--------------------------------------------------------------------------
*/

function getScrapingHistory(mysqli $conn, int $limit = 10): array
{
    $limit = max(1, min($limit, 50));

    $sql = "
        SELECT
            id,
            status,
            started_at,
            finished_at,
            raw_glints,
            raw_jobstreet,
            raw_lokerid,
            total_raw,
            total_rejected,
            total_clean,
            message,
            created_at
        FROM scraping_runs
        ORDER BY id DESC
        LIMIT {$limit}
    ";

    $result = $conn->query($sql);

    if (!$result) {
        throw new RuntimeException(
            "Gagal membaca riwayat scraping: " . $conn->error
        );
    }

    $history = [];

    while ($row = $result->fetch_assoc()) {
        $history[] = $row;
    }

    return $history;
}

/*
|--------------------------------------------------------------------------
| Membaca proses aktif sebelum memproses POST
|--------------------------------------------------------------------------
*/

try {
    $activeRun = getActiveScrapingRun($conn);
} catch (Throwable $error) {
    $activeRun = null;
    $errorMessage = $error->getMessage();
}

$isActive = $activeRun !== null;

/*
|--------------------------------------------------------------------------
| Menangani tombol Mulai Scraping
|--------------------------------------------------------------------------
*/

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $submittedToken = $_POST["csrf_token"] ?? "";

    if (
        !is_string($submittedToken)
        || !hash_equals($_SESSION["csrf_token"], $submittedToken)
    ) {
        $errorMessage = "Permintaan tidak valid. Silakan muat ulang halaman.";
    } else {
        try {
            /*
             * Pemeriksaan dilakukan lagi untuk mencegah dua antrean
             * dibuat secara bersamaan.
             */
            $conn->begin_transaction();

            $checkSql = "
                SELECT id, status
                FROM scraping_runs
                WHERE status IN ('queued', 'running')
                ORDER BY id DESC
                LIMIT 1
                FOR UPDATE
            ";

            $checkResult = $conn->query($checkSql);

            if (!$checkResult) {
                throw new RuntimeException(
                    "Gagal memeriksa antrean scraping: " . $conn->error
                );
            }

            $existingRun = $checkResult->fetch_assoc();

            if ($existingRun) {
                $conn->rollback();

                $existingStatus = $existingRun["status"] ?? "aktif";
                $existingId = (int) ($existingRun["id"] ?? 0);

                $errorMessage =
                    "Masih ada proses scraping aktif pada antrean "
                    . "#{$existingId} dengan status {$existingStatus}.";
            } else {
                /*
                 * started_at dibuat NULL karena proses belum benar-benar
                 * berjalan. Worker lokal yang akan mengisinya ketika
                 * mengambil antrean.
                 */
                $insertSql = "
                    INSERT INTO scraping_runs (
                        status,
                        started_at,
                        finished_at,
                        raw_glints,
                        raw_jobstreet,
                        raw_lokerid,
                        total_raw,
                        empty_data,
                        duplicate_data,
                        invalid_url,
                        education_not_detected,
                        total_rejected,
                        total_clean,
                        clean_csv_path,
                        message
                    ) VALUES (
                        'queued',
                        NULL,
                        NULL,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        0,
                        NULL,
                        ?
                    )
                ";

                $queueMessage =
                    "Menunggu worker lokal untuk menjalankan proses scraping.";

                $statement = $conn->prepare($insertSql);

                if (!$statement) {
                    throw new RuntimeException(
                        "Gagal menyiapkan antrean scraping: " . $conn->error
                    );
                }

                $statement->bind_param("s", $queueMessage);

                if (!$statement->execute()) {
                    throw new RuntimeException(
                        "Gagal membuat antrean scraping: "
                        . $statement->error
                    );
                }

                $runId = (int) $statement->insert_id;

                $statement->close();
                $conn->commit();

                $message =
                    "Permintaan scraping berhasil dimasukkan ke antrean "
                    . "#{$runId}. Worker lokal akan menjalankannya.";

                /*
                 * Membuat token baru setelah POST berhasil.
                 */
                $_SESSION["csrf_token"] = bin2hex(random_bytes(32));
            }
        } catch (Throwable $error) {
            if ($conn->errno === 0 || $conn->ping()) {
                try {
                    $conn->rollback();
                } catch (Throwable $rollbackError) {
                    // Abaikan kegagalan rollback.
                }
            }

            $errorMessage = $error->getMessage();
        }
    }
}

/*
|--------------------------------------------------------------------------
| Mengambil data terbaru setelah POST
|--------------------------------------------------------------------------
*/

try {
    $activeRun = getActiveScrapingRun($conn);
    $latestRun = getLatestScrapingRun($conn);
    $scrapingHistory = getScrapingHistory($conn, 10);
} catch (Throwable $error) {
    $activeRun = $activeRun ?? null;
    $latestRun = null;
    $scrapingHistory = [];

    if ($errorMessage === "") {
        $errorMessage = $error->getMessage();
    }
}

$isActive = $activeRun !== null;
$currentStatus = $latestRun["status"] ?? "Belum ada";

/*
|--------------------------------------------------------------------------
| Helper tampilan
|--------------------------------------------------------------------------
*/

function escapeHtml(?string $value): string
{
    return htmlspecialchars(
        $value ?? "",
        ENT_QUOTES,
        "UTF-8"
    );
}

function formatDateTime(?string $value): string
{
    if (!$value) {
        return "-";
    }

    $timestamp = strtotime($value);

    if ($timestamp === false) {
        return $value;
    }

    return date("d-m-Y H:i:s", $timestamp);
}

function statusLabel(string $status): string
{
    return match ($status) {
        "queued" => "Menunggu Worker",
        "running" => "Sedang Berjalan",
        "success" => "Berhasil",
        "failed" => "Gagal",
        default => ucfirst($status),
    };
}

function statusBadgeClass(string $status): string
{
    return match ($status) {
        "queued" =>
            "bg-amber-100 text-amber-700 ring-amber-200",

        "running" =>
            "bg-blue-100 text-blue-700 ring-blue-200",

        "success" =>
            "bg-emerald-100 text-emerald-700 ring-emerald-200",

        "failed" =>
            "bg-red-100 text-red-700 ring-red-200",

        default =>
            "bg-slate-100 text-slate-700 ring-slate-200",
    };
}

?>
<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">

    <meta
        name="viewport"
        content="width=device-width, initial-scale=1.0"
    >

    <title>Jalankan Scraping | Admin</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <?php if ($isActive): ?>
        <!--
            Refresh otomatis selama status queued atau running.
            Halaman akan membaca perubahan status dari database Railway.
        -->
        <meta http-equiv="refresh" content="5">
    <?php endif; ?>
</head>

<body class="min-h-screen bg-slate-100">

<?php require __DIR__ . "/navbar.php"; ?>

<main class="mx-auto max-w-6xl p-4 sm:p-6">

    <div class="mb-6">
        <h1 class="text-2xl font-bold text-slate-800">
            Jalankan Scraping
        </h1>

        <p class="mt-1 text-sm text-slate-500">
            Permintaan dibuat dari panel admin dan dijalankan oleh
            worker lokal.
        </p>
    </div>

    <?php if ($message !== ""): ?>
        <div
            class="mb-4 rounded-xl border border-emerald-200
                   bg-emerald-50 px-4 py-3 text-sm text-emerald-700"
        >
            <?= escapeHtml($message) ?>
        </div>
    <?php endif; ?>

    <?php if ($errorMessage !== ""): ?>
        <div
            class="mb-4 rounded-xl border border-red-200
                   bg-red-50 px-4 py-3 text-sm text-red-700"
        >
            <?= escapeHtml($errorMessage) ?>
        </div>
    <?php endif; ?>

    <!-- Kontrol scraping -->
    <section class="rounded-2xl bg-white p-6 shadow-sm">

        <div
            class="flex flex-col gap-5
                   sm:flex-row sm:items-center sm:justify-between"
        >
            <div>
                <h2 class="text-lg font-bold text-slate-800">
                    Kontrol Scraping
                </h2>

                <p class="mt-2 text-sm text-slate-500">
                    Klik tombol untuk memasukkan permintaan scraping
                    ke antrean database Railway.
                </p>

                <p class="mt-1 text-sm text-slate-500">
                    Worker pada komputer lokal akan mengambil antrean
                    dan menjalankan Playwright.
                </p>
            </div>

            <form
                method="POST"
                onsubmit="
                    return confirm(
                        'Masukkan proses scraping ke antrean sekarang?'
                    );
                "
            >
                <input
                    type="hidden"
                    name="csrf_token"
                    value="<?= escapeHtml($_SESSION["csrf_token"]) ?>"
                >

                <button
                    type="submit"
                    <?= $isActive ? "disabled" : "" ?>
                    class="
                        rounded-xl px-5 py-3 text-sm font-semibold
                        text-white transition

                        <?php if ($isActive): ?>
                            cursor-not-allowed bg-slate-400
                        <?php else: ?>
                            bg-blue-600 hover:bg-blue-700
                        <?php endif; ?>
                    "
                >
                    <?php if (($activeRun["status"] ?? "") === "queued"): ?>
                        Menunggu Worker Lokal...
                    <?php elseif (($activeRun["status"] ?? "") === "running"): ?>
                        Scraping Sedang Berjalan...
                    <?php else: ?>
                        Mulai Scraping
                    <?php endif; ?>
                </button>
            </form>
        </div>

        <?php if ($isActive): ?>
            <div
                class="mt-6 rounded-xl border border-blue-100
                       bg-blue-50 p-4"
            >
                <div
                    class="flex flex-col gap-2
                           sm:flex-row sm:items-center
                           sm:justify-between"
                >
                    <div>
                        <p class="text-sm font-semibold text-blue-800">
                            Proses aktif #<?= (int) $activeRun["id"] ?>
                        </p>

                        <p class="mt-1 text-sm text-blue-700">
                            <?= escapeHtml(
                                $activeRun["message"]
                                ?? "Menunggu pembaruan status."
                            ) ?>
                        </p>
                    </div>

                    <span
                        class="
                            inline-flex w-fit rounded-full px-3 py-1
                            text-xs font-semibold ring-1 ring-inset
                            <?= statusBadgeClass(
                                $activeRun["status"] ?? ""
                            ) ?>
                        "
                    >
                        <?= escapeHtml(
                            statusLabel($activeRun["status"] ?? "")
                        ) ?>
                    </span>
                </div>

                <p class="mt-3 text-xs text-blue-600">
                    Halaman diperbarui otomatis setiap 5 detik.
                </p>
            </div>
        <?php endif; ?>

        <!-- Informasi proses terakhir -->
        <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">

            <div class="rounded-xl bg-slate-50 p-4">
                <p class="text-xs font-medium text-slate-500">
                    Run Terakhir
                </p>

                <p class="mt-2 text-lg font-bold text-slate-800">
                    #<?= (int) ($latestRun["id"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl bg-slate-50 p-4">
                <p class="text-xs font-medium text-slate-500">
                    Status
                </p>

                <div class="mt-2">
                    <?php if ($latestRun): ?>
                        <span
                            class="
                                inline-flex rounded-full px-3 py-1
                                text-xs font-semibold ring-1 ring-inset
                                <?= statusBadgeClass(
                                    $latestRun["status"] ?? ""
                                ) ?>
                            "
                        >
                            <?= escapeHtml(
                                statusLabel(
                                    $latestRun["status"] ?? ""
                                )
                            ) ?>
                        </span>
                    <?php else: ?>
                        <p class="font-bold text-slate-800">
                            Belum ada
                        </p>
                    <?php endif; ?>
                </div>
            </div>

            <div class="rounded-xl bg-slate-50 p-4">
                <p class="text-xs font-medium text-slate-500">
                    Waktu Mulai
                </p>

                <p class="mt-2 text-sm font-bold text-slate-800">
                    <?= escapeHtml(
                        formatDateTime($latestRun["started_at"] ?? null)
                    ) ?>
                </p>
            </div>

            <div class="rounded-xl bg-slate-50 p-4">
                <p class="text-xs font-medium text-slate-500">
                    Waktu Selesai
                </p>

                <p class="mt-2 text-sm font-bold text-slate-800">
                    <?= escapeHtml(
                        formatDateTime($latestRun["finished_at"] ?? null)
                    ) ?>
                </p>
            </div>

        </div>
    </section>

    <!-- Ringkasan hasil terakhir -->
    <section class="mt-6 rounded-2xl bg-white p-6 shadow-sm">

        <h2 class="text-lg font-bold text-slate-800">
            Ringkasan Hasil Terakhir
        </h2>

        <div
            class="mt-5 grid gap-4
                   sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6"
        >
            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Glints</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["raw_glints"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Jobstreet</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["raw_jobstreet"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Loker.id</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["raw_lokerid"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Total Raw</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["total_raw"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Ditolak</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["total_rejected"] ?? 0) ?>
                </p>
            </div>

            <div class="rounded-xl border border-slate-200 p-4">
                <p class="text-xs text-slate-500">Data Bersih</p>
                <p class="mt-1 text-xl font-bold text-slate-800">
                    <?= (int) ($latestRun["total_clean"] ?? 0) ?>
                </p>
            </div>
        </div>

        <div class="mt-5 rounded-xl bg-slate-50 p-4">
            <p class="text-xs font-medium text-slate-500">
                Pesan proses terakhir
            </p>

            <p class="mt-2 text-sm text-slate-700">
                <?= escapeHtml(
                    $latestRun["message"]
                    ?? "Belum ada proses scraping."
                ) ?>
            </p>
        </div>
    </section>

    <!-- Riwayat scraping -->
    <section class="mt-6 overflow-hidden rounded-2xl bg-white shadow-sm">

        <div
            class="flex items-center justify-between
                   border-b border-slate-200 px-6 py-5"
        >
            <div>
                <h2 class="text-lg font-bold text-slate-800">
                    Riwayat Scraping
                </h2>

                <p class="mt-1 text-sm text-slate-500">
                    Menampilkan 10 proses terbaru.
                </p>
            </div>

            <a
                href="run_scraping.php"
                class="text-sm font-semibold text-blue-600
                       hover:text-blue-700"
            >
                Refresh
            </a>
        </div>

        <div class="overflow-x-auto">
            <table class="min-w-full divide-y divide-slate-200">

                <thead class="bg-slate-50">
                    <tr>
                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            ID
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Status
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Dibuat
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Mulai
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Selesai
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Raw
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Bersih
                        </th>

                        <th
                            class="px-5 py-3 text-left text-xs
                                   font-semibold uppercase
                                   tracking-wide text-slate-500"
                        >
                            Pesan
                        </th>
                    </tr>
                </thead>

                <tbody class="divide-y divide-slate-100 bg-white">

                <?php if (empty($scrapingHistory)): ?>
                    <tr>
                        <td
                            colspan="8"
                            class="px-5 py-8 text-center
                                   text-sm text-slate-500"
                        >
                            Belum ada riwayat scraping.
                        </td>
                    </tr>
                <?php else: ?>
                    <?php foreach ($scrapingHistory as $run): ?>
                        <tr class="hover:bg-slate-50">

                            <td
                                class="whitespace-nowrap
                                       px-5 py-4 text-sm
                                       font-semibold text-slate-800"
                            >
                                #<?= (int) $run["id"] ?>
                            </td>

                            <td class="whitespace-nowrap px-5 py-4">
                                <span
                                    class="
                                        inline-flex rounded-full
                                        px-3 py-1 text-xs font-semibold
                                        ring-1 ring-inset
                                        <?= statusBadgeClass(
                                            $run["status"] ?? ""
                                        ) ?>
                                    "
                                >
                                    <?= escapeHtml(
                                        statusLabel(
                                            $run["status"] ?? ""
                                        )
                                    ) ?>
                                </span>
                            </td>

                            <td
                                class="whitespace-nowrap px-5 py-4
                                       text-sm text-slate-600"
                            >
                                <?= escapeHtml(
                                    formatDateTime(
                                        $run["created_at"] ?? null
                                    )
                                ) ?>
                            </td>

                            <td
                                class="whitespace-nowrap px-5 py-4
                                       text-sm text-slate-600"
                            >
                                <?= escapeHtml(
                                    formatDateTime(
                                        $run["started_at"] ?? null
                                    )
                                ) ?>
                            </td>

                            <td
                                class="whitespace-nowrap px-5 py-4
                                       text-sm text-slate-600"
                            >
                                <?= escapeHtml(
                                    formatDateTime(
                                        $run["finished_at"] ?? null
                                    )
                                ) ?>
                            </td>

                            <td
                                class="whitespace-nowrap px-5 py-4
                                       text-sm font-semibold
                                       text-slate-700"
                            >
                                <?= (int) ($run["total_raw"] ?? 0) ?>
                            </td>

                            <td
                                class="whitespace-nowrap px-5 py-4
                                       text-sm font-semibold
                                       text-slate-700"
                            >
                                <?= (int) ($run["total_clean"] ?? 0) ?>
                            </td>

                            <td
                                class="max-w-xs px-5 py-4
                                       text-sm text-slate-600"
                            >
                                <span class="line-clamp-2">
                                    <?= escapeHtml(
                                        $run["message"] ?? "-"
                                    ) ?>
                                </span>
                            </td>

                        </tr>
                    <?php endforeach; ?>
                <?php endif; ?>

                </tbody>
            </table>
        </div>
    </section>

</main>
</body>
</html>