<?php

require_once __DIR__ . "/../config.php";

// Jika admin sudah login, langsung menuju dashboard.
if (isset($_SESSION["admin_id"])) {
    header("Location: dashboard.php");
    exit;
}

$errorMessage = "";

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $username = trim($_POST["username"] ?? "");
    $password = $_POST["password"] ?? "";

    if ($username === "" || $password === "") {
        $errorMessage = "Username dan password wajib diisi.";

    } else {
        $statement = $conn->prepare(
            "SELECT
                id,
                nama_lengkap,
                username,
                password
             FROM admins
             WHERE username = ?
             LIMIT 1"
        );

        $statement->bind_param("s", $username);
        $statement->execute();

        $admin = $statement
            ->get_result()
            ->fetch_assoc();

        if (
            $admin &&
            password_verify($password, $admin["password"])
        ) {
            session_regenerate_id(true);

            $_SESSION["admin_id"] = (int) $admin["id"];
            $_SESSION["admin_nama"] = $admin["nama_lengkap"];
            $_SESSION["admin_username"] = $admin["username"];
            $_SESSION["admin_login_time"] = time();

            header("Location: dashboard.php");
            exit;
        }

        $errorMessage = "Username atau password tidak benar.";
    }
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

    <title>Administrator | Job Aggregator</title>

    <script src="https://cdn.tailwindcss.com"></script>
</head>

<body class="min-h-screen bg-slate-100">

    <div class="grid min-h-screen lg:grid-cols-2">

        <section
            class="hidden bg-slate-900 p-12 lg:flex
                   lg:items-center lg:justify-center"
        >
            <div class="max-w-lg text-white">

                <div
                    class="mb-6 inline-flex h-14 w-14 items-center
                           justify-center rounded-2xl bg-blue-600"
                >
                    <svg
                        xmlns="http://www.w3.org/2000/svg"
                        class="h-7 w-7"
                        fill="none"
                        viewBox="0 0 24 24"
                        stroke="currentColor"
                    >
                        <path
                            stroke-linecap="round"
                            stroke-linejoin="round"
                            stroke-width="2"
                            d="M12 11c1.657 0 3-1.343 3-3s-1.343-3-3-3-3
                               1.343-3 3 1.343 3 3 3zm6 8a6 6 0 10-12 0h12z"
                        />
                    </svg>
                </div>

                <p class="mb-3 font-semibold uppercase tracking-widest text-blue-400">
                    Job Aggregator
                </p>

                <h1 class="text-4xl font-bold leading-tight">
                    Panel Administrator Sistem Informasi Lowongan Kerja
                </h1>

                <p class="mt-5 leading-7 text-slate-300">
                    Halaman ini digunakan untuk mengelola data lowongan,
                    memantau hasil scraping, dan memperbarui informasi
                    lowongan kerja.
                </p>

            </div>
        </section>

        <main class="flex items-center justify-center p-6">

            <div class="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">

                <div class="mb-7">

                    <p class="mb-2 text-sm font-semibold text-blue-600 lg:hidden">
                        JOB AGGREGATOR
                    </p>

                    <h2 class="text-2xl font-bold text-slate-800">
                        Login Administrator
                    </h2>

                    <p class="mt-2 text-sm text-slate-500">
                        Masukkan username dan password administrator.
                    </p>

                </div>

                <?php if ($errorMessage !== ""): ?>
                    <div
                        class="mb-5 rounded-lg border border-red-200
                               bg-red-50 px-4 py-3 text-sm text-red-700"
                    >
                        <?= htmlspecialchars($errorMessage) ?>
                    </div>
                <?php endif; ?>

                <form method="POST" class="space-y-5">

                    <div>
                        <label
                            for="username"
                            class="mb-2 block text-sm font-medium text-slate-700"
                        >
                            Username
                        </label>

                        <input
                            type="text"
                            id="username"
                            name="username"
                            required
                            autocomplete="username"
                            value="<?= htmlspecialchars($_POST["username"] ?? "") ?>"
                            class="w-full rounded-lg border border-slate-300
                                   px-4 py-3 outline-none
                                   focus:border-blue-500 focus:ring-2
                                   focus:ring-blue-100"
                        >
                    </div>

                    <div>
                        <label
                            for="password"
                            class="mb-2 block text-sm font-medium text-slate-700"
                        >
                            Password
                        </label>

                        <input
                            type="password"
                            id="password"
                            name="password"
                            required
                            autocomplete="current-password"
                            class="w-full rounded-lg border border-slate-300
                                   px-4 py-3 outline-none
                                   focus:border-blue-500 focus:ring-2
                                   focus:ring-blue-100"
                        >
                    </div>

                    <button
                        type="submit"
                        class="w-full rounded-lg bg-blue-600 px-4 py-3
                               font-semibold text-white transition
                               hover:bg-blue-700"
                    >
                        Masuk ke Dashboard
                    </button>

                </form>

                <div class="mt-6 text-center">
                    <a
                        href="../index.php"
                        class="text-sm font-medium text-slate-500
                               hover:text-blue-600"
                    >
                        Kembali ke halaman utama
                    </a>
                </div>

            </div>

        </main>

    </div>

</body>
</html>