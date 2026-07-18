<?php
require_once __DIR__ . "/auth.php";

$page = max(1, (int)($_GET["page"] ?? 1));
$limit = 15;
$offset = ($page - 1) * $limit;

$totalRows = (int)($conn->query("SELECT COUNT(*) AS total FROM scraping_runs")->fetch_assoc()["total"] ?? 0);
$totalPages = max(1, (int)ceil($totalRows / $limit));

$stmt = $conn->prepare("SELECT id,status,started_at,finished_at,raw_glints,raw_jobstreet,
                               raw_lokerid,total_raw,total_rejected,total_clean,message
                        FROM scraping_runs ORDER BY id DESC LIMIT ? OFFSET ?");
$stmt->bind_param("ii", $limit, $offset);
$stmt->execute();
$runs = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);

function badgeClass(string $status): string {
    return $status === "success" ? "bg-green-100 text-green-700"
         : ($status === "running" ? "bg-amber-100 text-amber-700"
         : ($status === "failed" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700"));
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Log Scraping | Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100">
<?php require __DIR__ . "/navbar.php"; ?>
<main class="mx-auto max-w-7xl p-6">
  <h1 class="text-2xl font-bold text-slate-800">Log Scraping</h1>
  <p class="mt-1 mb-6 text-slate-500">Riwayat scraping dan preprocessing.</p>

  <div class="overflow-hidden rounded-xl bg-white shadow-sm">
    <div class="border-b px-5 py-4 font-semibold">Total proses: <?= number_format($totalRows,0,",",".") ?></div>
    <div class="overflow-x-auto">
      <table class="min-w-full text-left text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3">Run</th>
            <th class="px-4 py-3">Waktu</th>
            <th class="px-4 py-3">Status</th>
            <th class="px-4 py-3">Glints</th>
            <th class="px-4 py-3">Jobstreet</th>
            <th class="px-4 py-3">Loker.id</th>
            <th class="px-4 py-3">Raw</th>
            <th class="px-4 py-3">Ditolak</th>
            <th class="px-4 py-3">Bersih</th>
            <th class="px-4 py-3">Pesan</th>
          </tr>
        </thead>
        <tbody class="divide-y">
        <?php if (!$runs): ?>
          <tr><td colspan="10" class="px-4 py-10 text-center text-slate-500">Belum ada log.</td></tr>
        <?php endif; ?>
        <?php foreach ($runs as $run): ?>
          <tr class="align-top hover:bg-slate-50">
            <td class="px-4 py-4 font-semibold">#<?= (int)$run["id"] ?></td>
            <td class="whitespace-nowrap px-4 py-4">
              <p><?= htmlspecialchars($run["started_at"] ?? "-") ?></p>
              <p class="mt-1 text-xs text-slate-500"><?= htmlspecialchars($run["finished_at"] ?? "Belum selesai") ?></p>
            </td>
            <td class="px-4 py-4">
              <span class="rounded-full px-3 py-1 text-xs font-semibold <?= badgeClass($run["status"]) ?>">
                <?= htmlspecialchars($run["status"]) ?>
              </span>
            </td>
            <td class="px-4 py-4"><?= (int)$run["raw_glints"] ?></td>
            <td class="px-4 py-4"><?= (int)$run["raw_jobstreet"] ?></td>
            <td class="px-4 py-4"><?= (int)$run["raw_lokerid"] ?></td>
            <td class="px-4 py-4 font-semibold"><?= (int)$run["total_raw"] ?></td>
            <td class="px-4 py-4 text-red-700"><?= (int)$run["total_rejected"] ?></td>
            <td class="px-4 py-4 text-green-700"><?= (int)$run["total_clean"] ?></td>
            <td class="max-w-sm px-4 py-4"><?= htmlspecialchars($run["message"] ?: "-") ?></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
    <?php if ($totalPages > 1): ?>
      <div class="flex justify-center gap-2 border-t px-5 py-4">
        <?php if ($page > 1): ?><a class="rounded border px-3 py-2" href="?page=<?= $page-1 ?>">Sebelumnya</a><?php endif; ?>
        <span class="rounded bg-blue-600 px-3 py-2 text-white"><?= $page ?> / <?= $totalPages ?></span>
        <?php if ($page < $totalPages): ?><a class="rounded border px-3 py-2" href="?page=<?= $page+1 ?>">Berikutnya</a><?php endif; ?>
      </div>
    <?php endif; ?>
  </div>
</main>
</body>
</html>
