<?php
$currentPage = basename($_SERVER["PHP_SELF"] ?? "");
function navClass(string $page, string $currentPage): string {
    return $page === $currentPage
        ? "bg-blue-600 text-white"
        : "text-slate-300 hover:bg-slate-800 hover:text-white";
}
?>
<nav class="bg-slate-900 text-white shadow">
  <div class="mx-auto max-w-7xl px-6">
    <div class="flex min-h-16 flex-wrap items-center justify-between gap-3 py-3">
      <a href="dashboard.php">
        <p class="font-bold">Job Aggregator Admin</p>
        <p class="text-xs text-slate-400">Panel Administrator</p>
      </a>
      <div class="flex flex-wrap items-center gap-2 text-sm">
        <?php
        $items = [
          "dashboard.php" => "Dashboard",
          "manage_jobs.php" => "Kelola Lowongan",
          "raw_jobs.php" => "Data Mentah",
          "run_scraping.php" => "Jalankan Scraping",
          "scraping_logs.php" => "Log Scraping",
        ];
        foreach ($items as $page => $label):
        ?>
          <a href="<?= $page ?>" class="rounded-lg px-3 py-2 <?= navClass($page, $currentPage) ?>">
            <?= $label ?>
          </a>
        <?php endforeach; ?>
        <a href="logout.php" class="rounded-lg bg-red-600 px-3 py-2 font-semibold hover:bg-red-700">Logout</a>
      </div>
    </div>
  </div>
</nav>
