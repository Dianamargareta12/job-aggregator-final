<?php
require_once "config.php";

$id = isset($_GET['id']) ? intval($_GET['id']) : 0;

$job = null;

try {
    if (isset($conn) && $id > 0) {
        $query = "SELECT * FROM jobs WHERE id = $id LIMIT 1";
        $result = mysqli_query($conn, $query);

        if ($result && mysqli_num_rows($result) > 0) {
            $job = mysqli_fetch_assoc($result);
        }
    }
} catch (Exception $e) {
    $job = null;
}

if (!$job) {
    $job = [
        "judul_posisi" => "Judul Lowongan",
        "nama_perusahaan" => "Nama Perusahaan",
        "lokasi" => "Lokasi tidak tersedia",
        "pendidikan" => "Umum",
        "portal_sumber" => "Portal",
        "deskripsi" => "Deskripsi lowongan belum tersedia.",
        "kualifikasi" => "Kualifikasi belum tersedia.",
        "link_lowongan" => "#"
    ];
}

$title = $job['judul_posisi'] ?? 'Judul Lowongan';
$company = $job['nama_perusahaan'] ?? 'Nama Perusahaan';
$location = $job['lokasi'] ?? 'Lokasi tidak tersedia';
$education = $job['pendidikan'] ?? 'Umum';
$source = $job['portal_sumber'] ?? 'Portal';
$description = $job['deskripsi'] ?? 'Deskripsi lowongan belum tersedia.';
$qualification = $job['kualifikasi'] ?? 'Kualifikasi belum tersedia.';
$link = $job['link_lowongan'] ?? '#';
$date = 'Data terbaru';

function badgeColor($text) {
    $text = strtolower((string)$text);

    if (str_contains($text, "sma")) return "bg-blue-100 text-blue-700";
    if (str_contains($text, "smk")) return "bg-blue-100 text-blue-700";
    if (str_contains($text, "s1")) return "bg-purple-100 text-purple-700";
    if (str_contains($text, "d3")) return "bg-violet-100 text-violet-700";
    if (str_contains($text, "glints")) return "bg-emerald-100 text-emerald-700";
    if (str_contains($text, "jobstreet")) return "bg-indigo-100 text-indigo-700";
    if (str_contains($text, "loker")) return "bg-sky-100 text-sky-700";

    return "bg-slate-100 text-slate-700";
}

function initialCompany($company) {
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
?>

<!DOCTYPE html>
<html lang="id">
<head>
    <meta charset="UTF-8">

    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title><?= htmlspecialchars($title); ?> - Job Aggregator</title>

    <script src="https://cdn.tailwindcss.com"></script>

    <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3.x.x/dist/cdn.min.js"></script>

    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">

    <link rel="stylesheet" href="assets/css/style.css">

    <style>
        body {
            font-family: 'Inter', sans-serif;
        }

        .detail-hero {
            background:
                radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 32%),
                linear-gradient(135deg, #0ea5e9, #2563eb, #1e40af);
        }

        [x-cloak] {
            display: none !important;
        }
    </style>
</head>

<body class="bg-slate-50 text-slate-800">

    <!-- NAVBAR -->
    <header x-data="{ open:false }"
        class="bg-white border-b border-slate-200 sticky top-0 z-50">

        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-20 flex items-center justify-between">

            <a href="index.php" class="flex items-center gap-3">
                <div class="w-11 h-11 rounded-xl bg-blue-600 flex items-center justify-center text-white font-bold text-xl shadow">
                    J
                </div>

                <div>
                    <h1 class="text-xl font-bold text-slate-900">Job Aggregator</h1>
                    <p class="text-sm text-slate-500">Web Scraping Lowongan Kerja</p>
                </div>
            </a>

            <nav class="hidden md:flex items-center gap-10 text-sm font-semibold">
                <a href="index.php" class="text-slate-700 hover:text-blue-600">Beranda</a>
                <a href="index.php#lowongan" class="text-blue-600 border-b-2 border-blue-600 pb-2">Cari Lowongan</a>
                <a href="index.php#lokasi" class="text-slate-700 hover:text-blue-600">Lokasi</a>
                <a href="index.php#tentang" class="text-slate-700 hover:text-blue-600">Tentang Sistem</a>
            </nav>

            <div class="flex items-center gap-3">
                <a href="index.php#lowongan"
                   class="hidden md:inline-flex items-center gap-2 px-5 py-3 rounded-xl border border-blue-600 text-blue-600 font-semibold hover:bg-blue-50 transition">
                    ← Kembali
                </a>

                <button
                    type="button"
                    @click="open = !open"
                    class="md:hidden w-11 h-11 rounded-xl border border-slate-200 flex items-center justify-center text-xl">
                    ☰
                </button>
            </div>
        </div>

        <!-- MOBILE MENU -->
        <div
            x-cloak
            x-show="open"
            x-transition
            class="md:hidden border-t border-slate-200 bg-white">

            <div class="px-4 py-5 space-y-4 text-sm font-semibold">
                <a href="index.php" class="block text-slate-700 hover:text-blue-600">Beranda</a>
                <a href="index.php#lowongan" class="block text-slate-700 hover:text-blue-600">Cari Lowongan</a>
                <a href="index.php#lokasi" class="block text-slate-700 hover:text-blue-600">Lokasi</a>
                <a href="index.php#tentang" class="block text-slate-700 hover:text-blue-600">Tentang Sistem</a>
            </div>
        </div>
    </header>

    <!-- HERO DETAIL -->
    <section class="detail-hero text-white">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">

            <a href="index.php#lowongan" class="inline-flex items-center text-sm text-blue-100 hover:text-white mb-6">
                ← Kembali ke daftar lowongan
            </a>

            <div class="grid lg:grid-cols-[1fr_320px] gap-8 items-end">

                <div>
                    <div class="flex items-center gap-4 mb-6">
                        <div class="w-16 h-16 rounded-2xl bg-white text-blue-700 font-extrabold text-xl flex items-center justify-center shadow-lg">
                            <?= htmlspecialchars(initialCompany($company)); ?>
                        </div>

                        <div>
                            <p class="text-blue-100 text-sm">Perusahaan</p>
                            <h2 class="text-xl font-bold"><?= htmlspecialchars($company); ?></h2>
                        </div>
                    </div>

                    <h1 class="text-3xl md:text-5xl font-extrabold leading-tight">
                        <?= htmlspecialchars($title); ?>
                    </h1>

                    <div class="flex flex-wrap gap-3 mt-6 text-sm">
                        <span class="px-4 py-2 rounded-full bg-white/15">
                            📍 <?= htmlspecialchars($location); ?>
                        </span>

                        <span class="px-4 py-2 rounded-full bg-white/15">
                            🎓 <?= htmlspecialchars($education ?: 'Umum'); ?>
                        </span>

                        <span class="px-4 py-2 rounded-full bg-white/15">
                            🌐 <?= htmlspecialchars($source); ?>
                        </span>
                    </div>
                </div>

                <div class="bg-white/10 border border-white/20 rounded-2xl p-6 backdrop-blur">
                    <p class="text-sm text-blue-100 mb-2">Tanggal Scraping</p>
                    <p class="font-bold mb-5"><?= htmlspecialchars($date); ?></p>

                    <a href="<?= htmlspecialchars($link); ?>" target="_blank"
                       class="block w-full text-center py-3 rounded-xl bg-white text-blue-700 font-bold hover:bg-blue-50 transition">
                        Buka Sumber Lowongan
                    </a>
                </div>
            </div>
        </div>
    </section>

    <!-- CONTENT -->
    <main class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
        <div class="grid lg:grid-cols-[1fr_340px] gap-8">

            <section class="space-y-6">

                <div class="bg-white border border-slate-200 rounded-2xl p-7 shadow-sm">
                    <h3 class="text-xl font-bold text-slate-900 mb-4">
                        Deskripsi Pekerjaan
                    </h3>

                    <p class="text-slate-600 leading-relaxed">
                        <?= nl2br(htmlspecialchars($description)); ?>
                    </p>
                </div>

                <div class="bg-white border border-slate-200 rounded-2xl p-7 shadow-sm">
                    <h3 class="text-xl font-bold text-slate-900 mb-4">
                        Kualifikasi
                    </h3>

                    <p class="text-slate-600 leading-relaxed">
                        <?= nl2br(htmlspecialchars($qualification)); ?>
                    </p>
                </div>

                <div class="bg-blue-50 border border-blue-100 rounded-2xl p-7">
                    <h3 class="text-xl font-bold text-slate-900 mb-4">
                        Catatan Sistem
                    </h3>

                    <p class="text-slate-600 leading-relaxed">
                        Informasi lowongan ini diperoleh melalui proses web scraping dari portal sumber.
                        Pengguna disarankan untuk tetap membuka halaman sumber asli lowongan untuk memastikan
                        informasi terbaru, persyaratan lengkap, dan proses pendaftaran resmi.
                    </p>
                </div>
            </section>

            <aside class="space-y-6">

                <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                    <h3 class="text-lg font-bold mb-5">Ringkasan Lowongan</h3>

                    <div class="space-y-5 text-sm">
                        <div>
                            <p class="text-slate-400 mb-1">Perusahaan</p>
                            <p class="font-semibold text-slate-800"><?= htmlspecialchars($company); ?></p>
                        </div>

                        <div>
                            <p class="text-slate-400 mb-1">Lokasi</p>
                            <p class="font-semibold text-slate-800"><?= htmlspecialchars($location); ?></p>
                        </div>

                        <div>
                            <p class="text-slate-400 mb-1">Pendidikan</p>
                            <span class="inline-block px-3 py-1 rounded-full text-xs font-semibold <?= badgeColor($education); ?>">
                                <?= htmlspecialchars($education ?: 'Umum'); ?>
                            </span>
                        </div>

                        <div>
                            <p class="text-slate-400 mb-1">Sumber Data</p>
                            <span class="inline-block px-3 py-1 rounded-full text-xs font-semibold <?= badgeColor($source); ?>">
                                <?= htmlspecialchars($source); ?>
                            </span>
                        </div>
                    </div>
                </div>

                <div class="bg-white border border-slate-200 rounded-2xl p-6 shadow-sm">
                    <h3 class="text-lg font-bold mb-4">Aksi</h3>

                    <div class="space-y-3">
                        <a href="<?= htmlspecialchars($link); ?>" target="_blank"
                           class="block w-full text-center py-3 rounded-xl bg-blue-600 text-white font-bold hover:bg-blue-700 transition">
                            Buka Lowongan Asli
                        </a>

                        <button onclick="window.print()"
                                class="w-full py-3 rounded-xl border border-slate-200 font-bold text-slate-700 hover:bg-slate-50 transition">
                            Cetak Detail
                        </button>

                        <a href="index.php#lowongan"
                           class="block w-full text-center py-3 rounded-xl border border-slate-200 font-bold text-slate-700 hover:bg-slate-50 transition">
                            Kembali ke Daftar
                        </a>
                    </div>
                </div>

                <div class="bg-yellow-50 border border-yellow-100 rounded-2xl p-6">
                    <h3 class="font-bold text-slate-900 mb-2">Perhatian</h3>
                    <p class="text-sm text-slate-600 leading-relaxed">
                        Sistem ini hanya menampilkan informasi lowongan dari hasil pengumpulan data.
                        Pastikan kamu mengecek ulang informasi pada portal sumber resmi.
                    </p>
                </div>
            </aside>
        </div>
    </main>

    <!-- FOOTER -->
    <footer class="bg-blue-950 text-white mt-8">
        <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">

            <div class="flex flex-col md:flex-row justify-between gap-4 items-center">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-blue-600 flex items-center justify-center font-bold">
                        J
                    </div>

                    <div>
                        <h3 class="font-bold">Job Aggregator</h3>
                        <p class="text-sm text-blue-200">Web Scraping Lowongan Kerja</p>
                    </div>
                </div>

                <p class="text-sm text-blue-200">
                    © 2025 Job Aggregator. All rights reserved.
                </p>
            </div>
        </div>
    </footer>

</body>
</html>