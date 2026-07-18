<?php
require_once __DIR__ . "/auth.php";

if (empty($_SESSION["csrf_token"])) {
    $_SESSION["csrf_token"] = bin2hex(random_bytes(32));
}

$message = "";
$errorMessage = "";

if ($_SERVER["REQUEST_METHOD"] === "POST" && isset($_POST["delete_id"])) {
    if (!hash_equals($_SESSION["csrf_token"], $_POST["csrf_token"] ?? "")) {
        $errorMessage = "Permintaan tidak valid.";
    } else {
        $deleteId = filter_var($_POST["delete_id"], FILTER_VALIDATE_INT);
        if ($deleteId) {
            $stmt = $conn->prepare("DELETE FROM jobs WHERE id = ?");
            $stmt->bind_param("i", $deleteId);
            $stmt->execute();
            $message = $stmt->affected_rows > 0
                ? "Data lowongan berhasil dihapus."
                : "Data lowongan tidak ditemukan.";
        }
    }
}

$search = trim($_GET["search"] ?? "");
$portal = trim($_GET["portal"] ?? "");
$education = trim($_GET["education"] ?? "");
$page = max(1, (int)($_GET["page"] ?? 1));
$limit = 15;
$offset = ($page - 1) * $limit;

$where = [];
$params = [];
$types = "";

if ($search !== "") {
    $where[] = "(judul_posisi LIKE ? OR nama_perusahaan LIKE ? OR lokasi LIKE ?)";
    $like = "%{$search}%";
    array_push($params, $like, $like, $like);
    $types .= "sss";
}
if ($portal !== "") {
    $where[] = "portal_sumber = ?";
    $params[] = $portal;
    $types .= "s";
}
if ($education !== "") {
    $where[] = "pendidikan = ?";
    $params[] = $education;
    $types .= "s";
}

$whereSql = $where ? " WHERE " . implode(" AND ", $where) : "";

$countStmt = $conn->prepare("SELECT COUNT(*) AS total FROM jobs{$whereSql}");
if ($types !== "") $countStmt->bind_param($types, ...$params);
$countStmt->execute();
$totalRows = (int)($countStmt->get_result()->fetch_assoc()["total"] ?? 0);
$totalPages = max(1, (int)ceil($totalRows / $limit));

$sql = "SELECT id, judul_posisi, nama_perusahaan, lokasi, pendidikan,
               portal_sumber, link_lowongan
        FROM jobs {$whereSql}
        ORDER BY id DESC LIMIT ? OFFSET ?";
$dataParams = $params;
$dataParams[] = $limit;
$dataParams[] = $offset;
$dataTypes = $types . "ii";

$stmt = $conn->prepare($sql);
$stmt->bind_param($dataTypes, ...$dataParams);
$stmt->execute();
$jobs = $stmt->get_result()->fetch_all(MYSQLI_ASSOC);

function pageUrl(array $changes = []): string {
    return "?" . http_build_query(array_merge($_GET, $changes));
}
?>
<!DOCTYPE html>
<html lang="id">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Kelola Lowongan | Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="min-h-screen bg-slate-100">
<?php require __DIR__ . "/navbar.php"; ?>
<main class="mx-auto max-w-7xl p-6">
  <h1 class="text-2xl font-bold text-slate-800">Kelola Lowongan</h1>
  <p class="mt-1 mb-6 text-slate-500">Data bersih dari tabel jobs.</p>

  <?php if ($message): ?>
    <div class="mb-4 rounded-lg bg-green-50 px-4 py-3 text-green-700"><?= htmlspecialchars($message) ?></div>
  <?php endif; ?>
  <?php if ($errorMessage): ?>
    <div class="mb-4 rounded-lg bg-red-50 px-4 py-3 text-red-700"><?= htmlspecialchars($errorMessage) ?></div>
  <?php endif; ?>

  <form method="GET" class="mb-6 grid gap-3 rounded-xl bg-white p-5 shadow-sm md:grid-cols-4">
    <input name="search" value="<?= htmlspecialchars($search) ?>" placeholder="Cari judul, perusahaan, lokasi..." class="rounded-lg border px-4 py-2">
    <select name="portal" class="rounded-lg border px-4 py-2">
      <option value="">Semua portal</option>
      <?php foreach (["Glints","Jobstreet","Loker.id"] as $item): ?>
        <option value="<?= $item ?>" <?= $portal === $item ? "selected" : "" ?>><?= $item ?></option>
      <?php endforeach; ?>
    </select>
    <select name="education" class="rounded-lg border px-4 py-2">
      <option value="">Semua pendidikan</option>
      <?php foreach (["SMA","SMK","D3","S1"] as $item): ?>
        <option value="<?= $item ?>" <?= $education === $item ? "selected" : "" ?>><?= $item ?></option>
      <?php endforeach; ?>
    </select>
    <div class="flex gap-2">
      <button class="flex-1 rounded-lg bg-blue-600 px-4 py-2 font-semibold text-white">Terapkan</button>
      <a href="manage_jobs.php" class="rounded-lg bg-slate-200 px-4 py-2 font-semibold">Reset</a>
    </div>
  </form>

  <div class="overflow-hidden rounded-xl bg-white shadow-sm">
    <div class="flex justify-between border-b px-5 py-4">
      <strong>Total: <?= number_format($totalRows, 0, ",", ".") ?></strong>
      <span class="text-sm text-slate-500">Halaman <?= $page ?> / <?= $totalPages ?></span>
    </div>
    <div class="overflow-x-auto">
      <table class="min-w-full text-left text-sm">
        <thead class="bg-slate-50 text-slate-600">
          <tr>
            <th class="px-4 py-3">No</th>
            <th class="px-4 py-3">Lowongan</th>
            <th class="px-4 py-3">Lokasi</th>
            <th class="px-4 py-3">Pendidikan</th>
            <th class="px-4 py-3">Portal</th>
            <th class="px-4 py-3">Aksi</th>
          </tr>
        </thead>
        <tbody class="divide-y">
        <?php if (!$jobs): ?>
          <tr><td colspan="6" class="px-4 py-10 text-center text-slate-500">Belum ada data.</td></tr>
        <?php endif; ?>
        <?php foreach ($jobs as $index => $job): ?>
          <tr class="align-top hover:bg-slate-50">
            <td class="px-4 py-4"><?= $offset + $index + 1 ?></td>
            <td class="max-w-md px-4 py-4">
              <p class="font-semibold"><?= htmlspecialchars($job["judul_posisi"]) ?></p>
              <p class="mt-1 text-slate-500"><?= htmlspecialchars($job["nama_perusahaan"]) ?></p>
            </td>
            <td class="px-4 py-4"><?= htmlspecialchars($job["lokasi"]) ?></td>
            <td class="px-4 py-4"><?= htmlspecialchars($job["pendidikan"]) ?></td>
            <td class="px-4 py-4"><?= htmlspecialchars($job["portal_sumber"]) ?></td>
            <td class="px-4 py-4">
              <div class="flex gap-2">
                <?php if ($job["link_lowongan"]): ?>
                  <a target="_blank" rel="noopener" href="<?= htmlspecialchars($job["link_lowongan"]) ?>" class="rounded bg-blue-50 px-3 py-2 text-blue-700">Buka</a>
                <?php endif; ?>
                <form method="POST" onsubmit="return confirm('Hapus lowongan ini?');">
                  <input type="hidden" name="csrf_token" value="<?= htmlspecialchars($_SESSION["csrf_token"]) ?>">
                  <input type="hidden" name="delete_id" value="<?= (int)$job["id"] ?>">
                  <button class="rounded bg-red-50 px-3 py-2 text-red-700">Hapus</button>
                </form>
              </div>
            </td>
          </tr>
        <?php endforeach; ?>
        </tbody>
      </table>
    </div>
    <?php if ($totalPages > 1): ?>
      <div class="flex justify-center gap-2 border-t px-5 py-4">
        <?php if ($page > 1): ?>
          <a class="rounded border px-3 py-2" href="<?= htmlspecialchars(pageUrl(["page"=>$page-1])) ?>">Sebelumnya</a>
        <?php endif; ?>
        <span class="rounded bg-blue-600 px-3 py-2 text-white"><?= $page ?></span>
        <?php if ($page < $totalPages): ?>
          <a class="rounded border px-3 py-2" href="<?= htmlspecialchars(pageUrl(["page"=>$page+1])) ?>">Berikutnya</a>
        <?php endif; ?>
      </div>
    <?php endif; ?>
  </div>
</main>
</body>
</html>
