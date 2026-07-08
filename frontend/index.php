<?php
require_once "config.php";

$limit = 9;
$page = isset($_GET['page']) ? (int) $_GET['page'] : 1;

if ($page < 1) {
    $page = 1;
}

$offset = ($page - 1) * $limit;

/*
|--------------------------------------------------------------------------
| FILTER INPUT
|--------------------------------------------------------------------------
*/

$keyword = isset($_GET['keyword']) ? trim($_GET['keyword']) : "";
$locationFilter = isset($_GET['location']) ? trim($_GET['location']) : "";
$educationFilters = isset($_GET['education']) ? (array) $_GET['education'] : [];
$sourceFilters = isset($_GET['source']) ? (array) $_GET['source'] : [];

$jobs = [];
$where = [];
$params = [];
$types = "";

/*
|--------------------------------------------------------------------------
| FILTER KEYWORD
|--------------------------------------------------------------------------
*/

if ($keyword !== "") {
    $where[] = "(
        judul_posisi LIKE ?
        OR nama_perusahaan LIKE ?
        OR deskripsi LIKE ?
        OR kualifikasi LIKE ?
    )";

    $search = "%" . $keyword . "%";

    $params[] = $search;
    $params[] = $search;
    $params[] = $search;
    $params[] = $search;

    $types .= "ssss";
}

/*
|--------------------------------------------------------------------------
| FILTER LOKASI
|--------------------------------------------------------------------------
*/

if ($locationFilter !== "") {
    $where[] = "lokasi LIKE ?";
    $params[] = "%" . $locationFilter . "%";
    $types .= "s";
}

/*
|--------------------------------------------------------------------------
| FILTER PENDIDIKAN
|--------------------------------------------------------------------------
*/

if (!empty($educationFilters)) {
    $educationConditions = [];

    foreach ($educationFilters as $education) {
        $education = trim($education);

        if ($education === "") {
            continue;
        }

        if ($education === "SMA/SMK") {
            $educationConditions[] = "(pendidikan LIKE ? OR pendidikan LIKE ?)";
            $params[] = "%SMA%";
            $params[] = "%SMK%";
            $types .= "ss";
        } else {
            $educationConditions[] = "pendidikan LIKE ?";
            $params[] = "%" . $education . "%";
            $types .= "s";
        }
    }

    if (!empty($educationConditions)) {
        $where[] = "(" . implode(" OR ", $educationConditions) . ")";
    }
}

/*
|--------------------------------------------------------------------------
| FILTER PORTAL SUMBER
|--------------------------------------------------------------------------
*/

if (!empty($sourceFilters)) {
    $sourceConditions = [];

    foreach ($sourceFilters as $source) {
        $source = trim($source);

        if ($source === "") {
            continue;
        }

        $sourceConditions[] = "portal_sumber LIKE ?";
        $params[] = "%" . $source . "%";
        $types .= "s";
    }

    if (!empty($sourceConditions)) {
        $where[] = "(" . implode(" OR ", $sourceConditions) . ")";
    }
}

$whereSql = "";

if (!empty($where)) {
    $whereSql = " WHERE " . implode(" AND ", $where);
}

/*
|--------------------------------------------------------------------------
| TOTAL DATA SETELAH FILTER
|--------------------------------------------------------------------------
*/

$totalData = 0;
$totalPages = 1;

try {
    if (isset($conn)) {
        $countSql = "SELECT COUNT(*) AS total FROM jobs " . $whereSql;
        $countStmt = mysqli_prepare($conn, $countSql);

        if ($countStmt) {
            if (!empty($params)) {
                mysqli_stmt_bind_param($countStmt, $types, ...$params);
            }

            mysqli_stmt_execute($countStmt);
            $countResult = mysqli_stmt_get_result($countStmt);

            if ($countResult) {
                $totalData = mysqli_fetch_assoc($countResult)['total'] ?? 0;
            }
        }

        $totalPages = max(1, ceil($totalData / $limit));
    }
} catch (Exception $e) {
    $totalData = 0;
    $totalPages = 1;
}

/*
|--------------------------------------------------------------------------
| AMBIL DATA LOWONGAN
|--------------------------------------------------------------------------
*/

try {
    if (isset($conn)) {
        $query = "
            SELECT * FROM jobs
            " . $whereSql . "
            ORDER BY 
                CASE 
                    WHEN nama_perusahaan IS NULL THEN 1
                    WHEN nama_perusahaan = '' THEN 1
                    WHEN nama_perusahaan = 'Tidak tersedia' THEN 1
                    WHEN nama_perusahaan LIKE '%LokerID by%' THEN 1
                    ELSE 0
                END ASC,
                id DESC
            LIMIT ? OFFSET ?
        ";

        $stmt = mysqli_prepare($conn, $query);

        if ($stmt) {
            $dataParams = $params;
            $dataTypes = $types . "ii";

            $dataParams[] = $limit;
            $dataParams[] = $offset;

            mysqli_stmt_bind_param($stmt, $dataTypes, ...$dataParams);
            mysqli_stmt_execute($stmt);

            $result = mysqli_stmt_get_result($stmt);

            if ($result) {
                while ($row = mysqli_fetch_assoc($result)) {
                    $jobs[] = $row;
                }
            }
        }
    }
} catch (Exception $e) {
    $jobs = [];
}

function isChecked($name, $value)
{
    $items = isset($_GET[$name]) ? (array) $_GET[$name] : [];
    return in_array($value, $items) ? "checked" : "";
}

function selectedValue($current, $value)
{
    return $current === $value ? "selected" : "";
}

function badgeColor($text)
{
    $text = strtolower((string)$text);

    if (str_contains($text, "sma")) return "bg-blue-100 text-blue-700";
    if (str_contains($text, "s1")) return "bg-purple-100 text-purple-700";
    if (str_contains($text, "d3")) return "bg-violet-100 text-violet-700";
    if (str_contains($text, "glints")) return "bg-emerald-100 text-emerald-700";
    if (str_contains($text, "jobstreet")) return "bg-indigo-100 text-indigo-700";
    if (str_contains($text, "loker")) return "bg-sky-100 text-sky-700";

    return "bg-slate-100 text-slate-700";
}

function initialCompany($company)
{
    $words = explode(" ", trim((string)$company));
    $initial = "";

    foreach ($words as $word) {
        if (!empty($word)) {
            $initial .= strtoupper(substr($word, 0, 1));
        }

        if (strlen($initial) >= 2) {
            break;
        }
    }

    return $initial ?: "JB";
}

function cleanCompanyName($company)
{
    $company = trim((string)$company);

    $company = str_replace(
        [
            "�",
            "\n",
            "\r",
            "\t"
        ],
        '',
        $company
    );

    $company = preg_replace('/[^\P{C}\n]+/u', '', $company);
    $company = preg_replace('/\s+/', ' ', $company);

    $removePatterns = [
        '/^2026\s*LokerID\s*by\s*/i',
        '/^LokerID\s*by\s*/i',
        '/^by\s*/i',
    ];

    foreach ($removePatterns as $pattern) {
        $company = preg_replace($pattern, '', $company);
    }

    if (empty($company) || strlen($company) < 3) {
        $company = "Perusahaan Tidak Diketahui";
    }

    if (strlen($company) > 32) {
        $company = substr($company, 0, 32) . "...";
    }

    return $company;
}


function pageUrl($targetPage)
{
    $query = $_GET;
    $query['page'] = $targetPage;

    return "index.php?" . http_build_query($query) . "#lowongan";
}

function getJobUrl($job)
{
    return $job['url']
        ?? $job['link']
        ?? $job['job_url']
        ?? $job['source_url']
        ?? $job['link_lowongan']
        ?? "";
}
?>

<!DOCTYPE html>
<html lang="id">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Job Aggregator</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <style>
        body {
            font-family: 'Inter', sans-serif;
        }

        .line-clamp-1,
        .line-clamp-2,
        .line-clamp-3 {
            overflow: hidden;
            display: -webkit-box;
            -webkit-box-orient: vertical;
        }

        .line-clamp-1 {
            -webkit-line-clamp: 1;
        }

        .line-clamp-2 {
            -webkit-line-clamp: 2;
        }

        .line-clamp-3 {
            -webkit-line-clamp: 3;
        }

        .hero-pattern {
            background:
                radial-gradient(circle at top right, rgba(255,255,255,0.16), transparent 32%),
                linear-gradient(135deg, #0ea5e9, #2563eb, #1d4ed8);
        }
    </style>
</head>

<body class="bg-slate-50 text-slate-800">

<header class="bg-white border-b border-slate-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">

        <div class="flex items-center gap-3">
            <div class="w-11 h-11 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-xl shadow">
                J
            </div>

            <div>
                <h1 class="text-xl font-bold text-slate-900">Job Aggregator</h1>
                <p class="text-sm text-slate-500">Web Scraping Lowongan Kerja</p>
            </div>
        </div>

        <nav class="hidden md:flex items-center gap-10 text-sm font-semibold">
            <a href="index.php" class="text-blue-600 border-b-2 border-blue-600 pb-2">Beranda</a>
            <a href="#lowongan" class="text-slate-700 hover:text-blue-600">Cari Lowongan</a>
            <a href="#lokasi" class="text-slate-700 hover:text-blue-600">Lokasi</a>
            <a href="#tentang" class="text-slate-700 hover:text-blue-600">Tentang Sistem</a>
        </nav>

    </div>
</header>

<section class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-6">
    <div class="hero-pattern rounded-3xl p-7 md:p-12 overflow-hidden text-white shadow-sm">

        <div class="grid md:grid-cols-2 gap-8 items-center">
            <div>
                <h2 class="text-3xl md:text-5xl font-extrabold leading-tight">
                    Temukan pekerjaan <br>
                    terbaik untuk <span class="text-yellow-300">kariermu</span>
                </h2>

                <p class="mt-5 text-blue-50 leading-relaxed max-w-xl">
                    Ribuan lowongan kerja terbaru dari berbagai portal terpercaya dalam satu tempat.
                </p>
            </div>

            <div class="hidden md:flex justify-end">
                <div class="text-[140px]">👩‍💻</div>
            </div>
        </div>

        <form method="GET" action="index.php#lowongan" class="mt-8 bg-white rounded-2xl p-4 shadow-xl">
            <div class="grid md:grid-cols-[1fr_1fr_auto] gap-4">

                <div class="flex items-center gap-3 border border-slate-200 rounded-xl px-4 h-14">
                    <span class="text-slate-400">🔍</span>
                    <input
                        type="text"
                        name="keyword"
                        value="<?= htmlspecialchars($keyword); ?>"
                        placeholder="Cari pekerjaan, skill, atau perusahaan"
                        class="w-full outline-none text-slate-700 text-sm">
                </div>

                <div class="flex items-center gap-3 border border-slate-200 rounded-xl px-4 h-14">
                    <span class="text-slate-400">📍</span>

                    <select name="location" class="w-full outline-none text-slate-600 text-sm bg-white">
                        <option value="">Semua Kota / Provinsi</option>
                        <option value="Jakarta" <?= selectedValue($locationFilter, "Jakarta"); ?>>Jakarta</option>
                        <option value="Bekasi" <?= selectedValue($locationFilter, "Bekasi"); ?>>Bekasi</option>
                        <option value="Bandung" <?= selectedValue($locationFilter, "Bandung"); ?>>Bandung</option>
                        <option value="Surabaya" <?= selectedValue($locationFilter, "Surabaya"); ?>>Surabaya</option>
                        <option value="Tangerang" <?= selectedValue($locationFilter, "Tangerang"); ?>>Tangerang</option>
                        <option value="Manado" <?= selectedValue($locationFilter, "Manado"); ?>>Manado</option>
                        <option value="Makassar" <?= selectedValue($locationFilter, "Makassar"); ?>>Makassar</option>
                        <option value="Yogyakarta" <?= selectedValue($locationFilter, "Yogyakarta"); ?>>Yogyakarta</option>
                    </select>
                </div>

                <button type="submit" class="h-14 px-10 rounded-xl bg-blue-600 text-white font-semibold hover:bg-blue-700 transition">
                    Cari
                </button>

            </div>
        </form>

    </div>
</section>

<main id="lowongan" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-10">
    <div class="grid lg:grid-cols-[280px_1fr] gap-8">

        <aside class="bg-white border border-slate-200 rounded-2xl p-6 h-fit shadow-sm">
            <h3 class="text-lg font-bold mb-6">🔎 Filter Lowongan</h3>

            <form method="GET" action="index.php#lowongan" class="space-y-8">

                <input type="hidden" name="keyword" value="<?= htmlspecialchars($keyword); ?>">
                <input type="hidden" name="location" value="<?= htmlspecialchars($locationFilter); ?>">

                <div>
                    <h4 class="font-semibold mb-4">Tingkat Pendidikan</h4>

                    <div class="space-y-3 text-sm text-slate-600">
                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="education[]" value="SMA/SMK" <?= isChecked("education", "SMA/SMK"); ?>>
                            SMA / SMK
                        </label>

                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="education[]" value="D3" <?= isChecked("education", "D3"); ?>>
                            D3
                        </label>

                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="education[]" value="S1" <?= isChecked("education", "S1"); ?>>
                            S1 / Sarjana
                        </label>
                    </div>
                </div>

                <div>
                    <h4 class="font-semibold mb-4">Portal Sumber</h4>

                    <div class="space-y-3 text-sm text-slate-600">
                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="source[]" value="Glints" <?= isChecked("source", "Glints"); ?>>
                            Glints
                        </label>

                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="source[]" value="Jobstreet" <?= isChecked("source", "Jobstreet"); ?>>
                            Jobstreet
                        </label>

                        <label class="flex gap-2 items-center">
                            <input type="checkbox" name="source[]" value="Loker.id" <?= isChecked("source", "Loker.id"); ?>>
                            Loker.id
                        </label>
                    </div>
                </div>

                <button type="submit" class="w-full py-3 rounded-xl bg-blue-600 text-white font-semibold">
                    Terapkan Filter
                </button>

                <a href="index.php#lowongan" class="block text-center text-sm font-semibold text-slate-500 hover:text-blue-600">
                    Reset Filter
                </a>
            </form>
        </aside>

        <section>
            <div class="mb-6">
                <h3 class="text-2xl font-bold text-slate-900">Lowongan Tersedia</h3>

                <p class="text-sm text-slate-500 mt-1">
                    Menampilkan
                    <span class="text-blue-600 font-semibold"><?= $totalData; ?></span>
                    lowongan kerja
                </p>
            </div>

            <div class="grid md:grid-cols-2 xl:grid-cols-3 gap-6">

                <?php foreach ($jobs as $job): ?>

                    <?php
                    $id = $job['id'] ?? 0;
                    $title = $job['judul_posisi'] ?? 'Judul';
                    $company = cleanCompanyName($job['nama_perusahaan'] ?? 'Perusahaan');
                    $location = $job['lokasi'] ?? 'Lokasi';
                    $education = $job['pendidikan'] ?? '';
                    $source = $job['portal_sumber'] ?? 'Portal';
                    $description = $job['deskripsi'] ?? '';
                    $jobUrl = getJobUrl($job);
                    ?>

                    <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm h-[438px] flex flex-col hover:shadow-md transition">

                        <div class="flex justify-between items-start gap-3 mb-5 h-[48px]">

                            <div class="flex items-start gap-3 min-w-0 flex-1">
                                <div class="w-12 h-12 shrink-0 rounded-xl bg-blue-600 text-white font-bold flex items-center justify-center overflow-hidden">
                                    <span class="text-sm leading-none text-center px-1 line-clamp-1">
                                        <?= htmlspecialchars(initialCompany($company)); ?>
                                    </span>
                                </div>

                                <p class="text-sm font-medium text-slate-600 leading-snug line-clamp-2 min-h-[42px]">
                                    <?= htmlspecialchars($company); ?>
                                </p>
                            </div>

                            <button class="text-slate-400 hover:text-blue-600 text-xl shrink-0">♡</button>
                        </div>

                        <h4 class="text-2xl font-bold text-slate-900 leading-snug line-clamp-2 h-[68px]">
                            <?= htmlspecialchars($title); ?>
                        </h4>

                        <p class="text-sm text-slate-500 mt-3 line-clamp-1 h-[22px]">
                            📍 <?= htmlspecialchars($location); ?>
                        </p>

                        <div class="flex flex-wrap gap-2 mt-4 h-[28px] overflow-hidden">
                            <?php if (!empty($education)): ?>
                                <span class="px-3 py-1 rounded-full text-xs font-semibold <?= badgeColor($education); ?>">
                                    <?= htmlspecialchars($education); ?>
                                </span>
                            <?php endif; ?>

                            <span class="px-3 py-1 rounded-full text-xs font-semibold <?= badgeColor($source); ?>">
                                <?= htmlspecialchars($source); ?>
                            </span>
                        </div>

                        <p class="text-sm text-slate-600 mt-5 leading-relaxed line-clamp-3 h-[72px]">
                            <?= htmlspecialchars($description ?: 'Deskripsi lowongan belum tersedia.'); ?>
                        </p>

                        <div class="mt-auto pt-6">
                            <p class="text-xs text-slate-500 mb-4">💼 Data scraping</p>

                            <div class="flex items-center justify-between gap-3">
                                <a href="detail.php?id=<?= $id; ?>"
                                    class="text-sm font-bold text-blue-600 hover:underline whitespace-nowrap">
                                    Lihat Detail
                                </a>

                                <?php if (!empty($jobUrl)): ?>
                                    <a href="<?= htmlspecialchars($jobUrl); ?>"
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        class="text-sm font-bold bg-blue-600 text-white px-4 py-2 rounded-xl hover:bg-blue-700 transition whitespace-nowrap">
                                        Daftar →
                                    </a>
                                <?php else: ?>
                                    <span class="text-xs text-slate-400 whitespace-nowrap">
                                        Link tidak tersedia
                                    </span>
                                <?php endif; ?>
                            </div>
                        </div>

                    </div>

                <?php endforeach; ?>

            </div>

            <div class="flex justify-center items-center gap-2 mt-10">

                <?php if ($page > 1): ?>
                    <a href="<?= pageUrl($page - 1); ?>"
                        class="w-10 h-10 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:bg-slate-50">
                        ‹
                    </a>
                <?php endif; ?>

                <?php for ($i = 1; $i <= $totalPages; $i++): ?>

                    <?php if ($i <= 3 || $i == $totalPages || abs($i - $page) <= 1): ?>

                        <a href="<?= pageUrl($i); ?>"
                            class="w-10 h-10 flex items-center justify-center rounded-lg border
                            <?= $i == $page
                                ? 'bg-blue-600 text-white border-blue-600'
                                : 'bg-white border-slate-200 hover:bg-slate-50'; ?>">
                            <?= $i; ?>
                        </a>

                    <?php elseif ($i == 4): ?>

                        <span class="w-10 h-10 flex items-center justify-center">...</span>

                    <?php endif; ?>

                <?php endfor; ?>

                <?php if ($page < $totalPages): ?>
                    <a href="<?= pageUrl($page + 1); ?>"
                        class="w-10 h-10 flex items-center justify-center rounded-lg border border-slate-200 bg-white hover:bg-slate-50">
                        ›
                    </a>
                <?php endif; ?>

            </div>

        </section>

    </div>
</main>

<section id="lokasi" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-12">
    <div class="bg-blue-50 border border-blue-100 rounded-2xl p-8">
        <h3 class="text-xl font-bold mb-2">📍 Loker di Kota Besar</h3>

        <p class="text-sm text-slate-600 mb-5">
            Pilih kota favoritmu untuk menemukan lebih banyak peluang kerja.
        </p>

        <div class="flex flex-wrap gap-3">
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Jakarta</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Bekasi</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Bandung</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Surabaya</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Tangerang</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Manado</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Makassar</a>
            <a href="#" class="px-5 py-3 rounded-xl bg-white border text-blue-600 font-semibold hover:bg-blue-600 hover:text-white transition">Yogyakarta</a>
        </div>
    </div>
</section>

<section id="tentang" class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 mt-8 mb-12">
    <div class="grid md:grid-cols-4 gap-5">

        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div class="text-3xl mb-3">📅</div>
            <h4 class="font-bold">Data Terupdate</h4>
            <p class="text-sm text-slate-500 mt-2">Lowongan kerja terbaru dari berbagai portal setiap hari.</p>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div class="text-3xl mb-3">🔍</div>
            <h4 class="font-bold">Pencarian Mudah</h4>
            <p class="text-sm text-slate-500 mt-2">Cari pekerjaan sesuai keahlian, lokasi, dan pendidikan.</p>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div class="text-3xl mb-3">🛡️</div>
            <h4 class="font-bold">Sumber Terpercaya</h4>
            <p class="text-sm text-slate-500 mt-2">Dikumpulkan dari portal lowongan kerja terpercaya.</p>
        </div>

        <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
            <div class="text-3xl mb-3">🏷️</div>
            <h4 class="font-bold">Gratis & Mudah</h4>
            <p class="text-sm text-slate-500 mt-2">Gunakan semua fitur secara gratis tanpa registrasi.</p>
        </div>

    </div>
</section>

<footer class="bg-blue-950 text-white">
    <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">

        <div class="grid md:grid-cols-5 gap-8">

            <div class="md:col-span-2">
                <div class="flex items-center gap-3 mb-4">
                    <div class="w-11 h-11 rounded-xl bg-blue-600 flex items-center justify-center font-bold text-xl">
                        J
                    </div>

                    <div>
                        <h3 class="font-bold text-lg">Job Aggregator</h3>
                        <p class="text-sm text-blue-200">Web Scraping Lowongan Kerja</p>
                    </div>
                </div>

                <p class="text-sm text-blue-100 leading-relaxed max-w-md">
                    Platform pencarian lowongan kerja yang mengumpulkan informasi dari berbagai portal terpercaya untuk memudahkan pencarian pekerjaan.
                </p>
            </div>

            <div>
                <h4 class="font-bold mb-4">Navigasi</h4>
                <ul class="space-y-2 text-sm text-blue-100">
                    <li><a href="index.php">Beranda</a></li>
                    <li><a href="#lowongan">Cari Lowongan</a></li>
                    <li><a href="#lokasi">Lokasi</a></li>
                    <li><a href="#tentang">Tentang Sistem</a></li>
                </ul>
            </div>

            <div>
                <h4 class="font-bold mb-4">Sumber Data</h4>
                <ul class="space-y-2 text-sm text-blue-100">
                    <li>Glints</li>
                    <li>Jobstreet</li>
                    <li>Loker.id</li>
                </ul>
            </div>

            <div>
                <h4 class="font-bold mb-4">Informasi</h4>
                <ul class="space-y-2 text-sm text-blue-100">
                    <li>Tentang Sistem</li>
                    <li>Kebijakan Privasi</li>
                    <li>Syarat & Ketentuan</li>
                </ul>
            </div>

        </div>

        <div class="border-t border-blue-800 mt-8 pt-6 flex flex-col md:flex-row justify-between gap-3 text-sm text-blue-200">
            <p>© 2025 Job Aggregator. All rights reserved.</p>
            <p>Dibuat dengan ❤️ untuk pencari kerja di Indonesia</p>
        </div>

    </div>
</footer>

</body>
</html>