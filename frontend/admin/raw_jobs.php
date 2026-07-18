<?php
require_once __DIR__ . "/auth.php";

$portal = trim($_GET["portal"] ?? "");
$status = trim($_GET["status"] ?? "");
$search = trim($_GET["search"] ?? "");
$runId = (int)($_GET["run_id"] ?? 0);
$page = max(1, (int)($_GET["page"] ?? 1));
$limit = 20;
$offset = ($page - 1) * $limit;

if ($runId <= 0) {
    $r = $conn->query("SELECT id FROM scraping_runs ORDER BY id DESC LIMIT 1");
    $runId = (int)(($r ? $r->fetch_assoc()["id"] : 0) ?? 0);
}

$where = [];
$params = [];
$types = "";

if ($runId > 0) { $where[] = "scraping_run_id = ?"; $params[] = $runId; $types .= "i"; }
if ($portal !== "") { $where[] = "portal_sumber = ?"; $params[] = $portal; $types .= "s"; }
if ($status !== "") { $where[] = "validation_status = ?"; $params[] = $status; $types .= "s"; }
if ($search !== "") {
    $where[] = "(judul_posisi LIKE ? OR nama_perusahaan LIKE ? OR rejection_reason LIKE ?)";
    $like = "%{$search}%";
    array_push($params, $like, $like, $like);
    $types .= "sss";
}
$whereSql = $where ? " WHERE " . implode(" AND ", $where) : "";

$countStmt = $conn->prepare("SELECT COUNT(*) AS total FROM raw_jobs{$whereSql}");
if ($types !== "") $countStmt->bind_param($types, ...$params);
$countStmt->execute();
$totalRows = (int)($countStmt->get_result()->fetch_assoc()["total"] ?? 0);
$totalPages = max(1, (int)ceil($totalRows / $limit));

$sql = "SELECT portal_sumber, judul_posisi, nama_perusahaan, lokasi, pendidikan,
               validation_status, rejection_reason
        FROM raw_jobs {$whereSql}
        ORDER BY id DESC LIMIT ? OFFSET ?";
$dataParams = $params;
$dataParams[] = $limit;
$dataParams[] = $offset;
$dataTypes = $types . "ii";
$stmt = $conn->prepare($sql);
$stmt->bind_param($dataTypes, ...$dataParams);
$stmt->execute();
$rows = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);

$runs = $conn->query("SELECT id, started_at FROM scraping_runs ORDER BY id DESC LIMIT 20")->fetch_all(MYSQLI_ASSOC);

function rawUrl(array $changes = []): string {
    return "?" . http_build_query(array_merge($_GET, $changes));
}
function rawBadge(string $status): string {
    return $status === "clean" ? "bg-green-100 text-green-700"
         : ($status === "rejected" ? "bg-red-100 text-red-700" : "bg-slate-100 text-slate-700");
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Data Mentah | Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100">
<?php require __DIR__ . "/navbar.php"; ?>
<main class="mx-auto max-w-7xl p-6">
  <h1 class="text-2xl font-bold text-slate-800">Data Mentah</h1>
  <p class="mt-1 mb-6 text-slate-500">Data sebelum dan sesudah preprocessing.</p>

  <form method="GET" class="mb-6 grid gap-3 rounded-xl bg-white p-5 shadow-sm md:grid-cols-5">
    <select name="run_id" class="rounded-lg border px-3 py-2">
      <?php foreach ($runs as $run): ?>
        <option value="<?= (int)$run["id"] ?>" <?= $runId === (int)$run["id"] ? "selected" : "" ?>>
          Run #<?= (int)$run["id"] ?> — <?= htmlspecialchars($run["started_at"] ?? "-") ?>
        </option>
      <?php endforeach; ?>
    </select>
    <input name="search" value="<?= htmlspecialchars($search) ?>" placeholder="Cari data..." class="rounded-lg border px-3 py-2">
    <select name="portal" class="rounded-lg border px-3 py-2">
      <option value="">Semua portal</option>
      <?php foreach (["Glints","Jobstreet","Loker.id"] as $item): ?>
        <option value="<?= $item ?>" <?= $portal === $item ? "selected" : "" ?>><?= $item ?></option>
      <?php endforeach; ?>
    </select>
    <select name="status" class="rounded-lg border px-3 py-2">
      <option value="">Semua status</option>
      <option value="clean" <?= $status === "clean" ? "selected" : "" ?>>Clean</option>
      <option value="rejected" <?= $status === "rejected" ? "selected" : "" ?>>Rejected</option>
    </select>
    <div class="flex gap-2">
      <button class="flex-1 rounded-lg bg-blue-600 px-3 py-2 font-semibold text-white">Terapkan</button>
      <a href="raw_jobs.php" class="rounded-lg bg-slate-200 px-3 py-2 font-semibold">Reset</a>
    </div>
  </form>

  <div class="overflow-hidden rounded-xl bg-white shadow-sm">
    <div class="flex justify-between border-b px-5 py-4">
      <strong>Total: <?= number_format($totalRows,0,",",".") ?></strong>
      <span class="text-sm text-slate-500">Run #<?= $runId ?: "-" ?></span>
    </div>
    <div class="overflow-x-auto">
      <table class="min-w-full text-left text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3">No</th>
            <th class="px-4 py-3">Portal</th>
            <th class="px-4 py-3">Lowongan</th>
            <th class="px-4 py-3">Lokasi</th>
            <th class="px-4 py-3">Pendidikan</th>
            <th class="px-4 py-3">Status</th>
            <th class="px-4 py-3">Alasan</th>
          </tr>
        </thead>
        <tbody class="divide-y">
        <?php if (!$rows): ?>
          <tr><td colspan="7" class="px-4 py-10 text-center text-slate-500">Tidak ada data.</td></tr>
        <?php endif; ?>
        <?php foreach ($rows as $index => $row): ?>
          <tr class="align-top hover:bg-slate-50">
            <td class="px-4 py-4"><?= $offset + $index + 1 ?></td>
            <td class="px-4 py-4"><?= htmlspecialchars($row["portal_sumber"]) ?></td>
            <td class="max-w-md px-4 py-4">
              <p class="font-semibold"><?= htmlspecialchars($row["judul_posisi"] ?: "-") ?></p>
              <p class="mt-1 text-slate-500"><?= htmlspecialchars($row["nama_perusahaan"] ?: "-") ?></p>
            </td>
            <td class="px-4 py-4"><?= htmlspecialchars($row["lokasi"] ?: "-") ?></td>
            <td class="px-4 py-4"><?= htmlspecialchars($row["pendidikan"] ?: "-") ?></td>
            <td class="px-4 py-4">
              <span class="rounded-full px-3 py-1 text-xs font-semibold <?= rawBadge($row["validation_status"]) ?>">
                <?= htmlspecialchars($row["validation_status"]) ?>
              </span>
            </td>
            <td class="max-w-xs px-4 py-4"><?= htmlspecialchars($row["rejection_reason"] ?: "-") ?></td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
    <?php if ($totalPages > 1): ?>
      <div class="flex justify-center gap-2 border-t px-5 py-4">
        <?php if ($page > 1): ?>
          <a class="rounded border px-3 py-2" href="<?= htmlspecialchars(rawUrl(["page"=>$page-1])) ?>">Sebelumnya</a>
        <?php endif; ?>
        <span class="rounded bg-blue-600 px-3 py-2 text-white"><?= $page ?> / <?= $totalPages ?></span>
        <?php if ($page < $totalPages): ?>
          <a class="rounded border px-3 py-2" href="<?= htmlspecialchars(rawUrl(["page"=>$page+1])) ?>">Berikutnya</a>
        <?php endif; ?>
      </div>
    <?php endif; ?>
  </div>
</main>
</body>
</html>
