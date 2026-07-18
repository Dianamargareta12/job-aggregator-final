<?php
require_once __DIR__ . "/auth.php";

if (empty($_SESSION["csrf_token"])) {
    $_SESSION["csrf_token"] = bin2hex(random_bytes(32));
}

$projectRoot = dirname(__DIR__, 2);
$mainPath = $projectRoot . DIRECTORY_SEPARATOR . "main.py";
$logDir = $projectRoot . DIRECTORY_SEPARATOR . "storage";
$logPath = $logDir . DIRECTORY_SEPARATOR . "scraping_output.log";

if (!is_dir($logDir)) {
    mkdir($logDir, 0775, true);
}

$message = "";
$errorMessage = "";

$latest = $conn->query("SELECT id,status,started_at,finished_at,message FROM scraping_runs ORDER BY id DESC LIMIT 1");
$latestRun = $latest ? $latest->fetch_assoc() : null;
$isRunning = ($latestRun["status"] ?? "") === "running";

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    if (!hash_equals($_SESSION["csrf_token"], $_POST["csrf_token"] ?? "")) {
        $errorMessage = "Permintaan tidak valid.";
    } elseif ($isRunning) {
        $errorMessage = "Proses scraping lain masih berjalan.";
    } elseif (!file_exists($mainPath)) {
        $errorMessage = "main.py tidak ditemukan: " . $mainPath;
    } else {
        file_put_contents($logPath, "[" . date("Y-m-d H:i:s") . "] Memulai scraping..." . PHP_EOL);

        if (PHP_OS_FAMILY === "Windows") {
            $command = 'start /B "" cmd /C "cd /D ' . escapeshellarg($projectRoot)
                     . ' && py main.py >> ' . escapeshellarg($logPath) . ' 2>&1"';
            pclose(popen($command, "r"));
        } else {
            $command = "cd " . escapeshellarg($projectRoot)
                     . " && nohup python3 main.py >> " . escapeshellarg($logPath) . " 2>&1 &";
            exec($command);
        }

        $message = "Perintah scraping berhasil dikirim. Tunggu lalu refresh halaman.";
        $isRunning = true;
    }
}

$logContent = file_exists($logPath) ? file_get_contents($logPath) : "";
if (strlen($logContent) > 20000) {
    $logContent = substr($logContent, -20000);
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Jalankan Scraping | Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
<?php if ($isRunning): ?><meta http-equiv="refresh" content="10"><?php endif; ?>
</head>
<body class="min-h-screen bg-slate-100">
<?php require __DIR__ . "/navbar.php"; ?>
<main class="mx-auto max-w-5xl p-6">
  <h1 class="text-2xl font-bold text-slate-800">Jalankan Scraping</h1>
  <p class="mt-1 mb-6 text-slate-500">Menjalankan main.py dari panel administrator.</p>

  <?php if ($message): ?>
    <div class="mb-4 rounded-lg bg-green-50 px-4 py-3 text-green-700"><?= htmlspecialchars($message) ?></div>
  <?php endif; ?>
  <?php if ($errorMessage): ?>
    <div class="mb-4 rounded-lg bg-red-50 px-4 py-3 text-red-700"><?= htmlspecialchars($errorMessage) ?></div>
  <?php endif; ?>

  <section class="rounded-xl bg-white p-6 shadow-sm">
    <div class="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h2 class="text-lg font-bold">Kontrol Scraping</h2>
        <p class="mt-2 text-sm text-slate-500">Mode keyword mengikuti TEST_MODE pada main.py.</p>
        <p class="mt-1 text-xs text-slate-400"><?= htmlspecialchars($mainPath) ?></p>
      </div>
      <form method="POST" onsubmit="return confirm('Jalankan scraping sekarang?');">
        <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION["csrf_token"]) ?>">
        <button <?= $isRunning ? "disabled" : "" ?>
                class="rounded-lg px-5 py-3 font-semibold text-white <?= $isRunning ? "cursor-not-allowed bg-slate-400" : "bg-blue-600 hover:bg-blue-700" ?>">
          <?= $isRunning ? "Scraping Sedang Berjalan..." : "Mulai Scraping" ?>
        </button>
      </form>
    </div>

    <div class="mt-6 grid gap-4 md:grid-cols-4">
      <div class="rounded-lg bg-slate-50 p-4"><p class="text-xs text-slate-500">Run terakhir</p><p class="mt-1 font-bold">#<?= (int)($latestRun["id"] ?? 0) ?></p></div>
      <div class="rounded-lg bg-slate-50 p-4"><p class="text-xs text-slate-500">Status</p><p class="mt-1 font-bold"><?= htmlspecialchars($latestRun["status"] ?? "Belum ada") ?></p></div>
      <div class="rounded-lg bg-slate-50 p-4"><p class="text-xs text-slate-500">Mulai</p><p class="mt-1 font-bold"><?= htmlspecialchars($latestRun["started_at"] ?? "-") ?></p></div>
      <div class="rounded-lg bg-slate-50 p-4"><p class="text-xs text-slate-500">Selesai</p><p class="mt-1 font-bold"><?= htmlspecialchars($latestRun["finished_at"] ?? "-") ?></p></div>
    </div>
  </section>

  <section class="mt-6 overflow-hidden rounded-xl bg-slate-900 shadow-sm">
    <div class="flex justify-between border-b border-slate-700 px-5 py-4 text-white">
      <h2 class="font-bold">Output Terminal</h2>
      <a href="run_scraping.php" class="text-sm text-blue-300">Refresh</a>
    </div>
    <pre class="max-h-[520px] overflow-auto whitespace-pre-wrap p-5 text-xs text-green-300"><?= htmlspecialchars($logContent ?: "Belum ada output scraping.") ?></pre>
  </section>
</main>
</body>
</html>
