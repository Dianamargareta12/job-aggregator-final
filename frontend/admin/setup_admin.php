<?php

require_once __DIR__ . "/../config.php";

$message = "";
$messageType = "";

if ($_SERVER["REQUEST_METHOD"] === "POST") {
    $namaLengkap = trim($_POST["nama_lengkap"] ?? "");
    $username = trim($_POST["username"] ?? "");
    $password = $_POST["password"] ?? "";
    $konfirmasiPassword = $_POST["konfirmasi_password"] ?? "";

    if (
        $namaLengkap === "" ||
        $username === "" ||
        $password === "" ||
        $konfirmasiPassword === ""
    ) {
        $message = "Semua kolom wajib diisi.";
        $messageType = "error";

    } elseif (strlen($username) < 4) {
        $message = "Username minimal terdiri dari 4 karakter.";
        $messageType = "error";

    } elseif (strlen($password) < 8) {
        $message = "Password minimal terdiri dari 8 karakter.";
        $messageType = "error";

    } elseif ($password !== $konfirmasiPassword) {
        $message = "Konfirmasi password tidak sama.";
        $messageType = "error";

    } else {
        $checkAdmin = $conn->prepare(
            "SELECT id
             FROM admins
             WHERE username = ?
             LIMIT 1"
        );

        $checkAdmin->bind_param("s", $username);
        $checkAdmin->execute();

        $existingAdmin = $checkAdmin
            ->get_result()
            ->fetch_assoc();

        if ($existingAdmin) {
            $message = "Username sudah digunakan.";
            $messageType = "error";

        } else {
            $passwordHash = password_hash(
                $password,
                PASSWORD_DEFAULT
            );

            $insertAdmin = $conn->prepare(
                "INSERT INTO admins (
                    nama_lengkap,
                    username,
                    password
                )
                VALUES (?, ?, ?)"
            );

            $insertAdmin->bind_param(
                "sss",
                $namaLengkap,
                $username,
                $passwordHash
            );

            $insertAdmin->execute();

            $message = "Akun admin berhasil dibuat. Silakan masuk.";
            $messageType = "success";
        }
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

    <title>Buat Admin | Job Aggregator</title>

    <script src="https://cdn.tailwindcss.com"></script>
</head>

<body class="min-h-screen bg-slate-100 flex items-center justify-center p-6">

    <div class="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg">

        <div class="mb-7 text-center">
            <h1 class="text-2xl font-bold text-slate-800">
                Buat Akun Admin
            </h1>

            <p class="mt-2 text-sm text-slate-500">
                Halaman ini digunakan untuk membuat akun administrator pertama.
            </p>
        </div>

        <?php if ($message !== ""): ?>
            <div
                class="mb-5 rounded-lg px-4 py-3 text-sm
                <?= $messageType === "success"
                    ? "bg-green-100 text-green-700"
                    : "bg-red-100 text-red-700"
                ?>"
            >
                <?= htmlspecialchars($message) ?>
            </div>
        <?php endif; ?>

        <form method="POST" class="space-y-5">

            <div>
                <label
                    for="nama_lengkap"
                    class="mb-2 block text-sm font-medium text-slate-700"
                >
                    Nama Lengkap
                </label>

                <input
                    type="text"
                    id="nama_lengkap"
                    name="nama_lengkap"
                    required
                    value="<?= htmlspecialchars($_POST["nama_lengkap"] ?? "") ?>"
                    class="w-full rounded-lg border border-slate-300 px-4 py-3
                           outline-none focus:border-blue-500
                           focus:ring-2 focus:ring-blue-100"
                >
            </div>

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
                    class="w-full rounded-lg border border-slate-300 px-4 py-3
                           outline-none focus:border-blue-500
                           focus:ring-2 focus:ring-blue-100"
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
                    autocomplete="new-password"
                    class="w-full rounded-lg border border-slate-300 px-4 py-3
                           outline-none focus:border-blue-500
                           focus:ring-2 focus:ring-blue-100"
                >

                <p class="mt-1 text-xs text-slate-500">
                    Password minimal 8 karakter.
                </p>
            </div>

            <div>
                <label
                    for="konfirmasi_password"
                    class="mb-2 block text-sm font-medium text-slate-700"
                >
                    Konfirmasi Password
                </label>

                <input
                    type="password"
                    id="konfirmasi_password"
                    name="konfirmasi_password"
                    required
                    autocomplete="new-password"
                    class="w-full rounded-lg border border-slate-300 px-4 py-3
                           outline-none focus:border-blue-500
                           focus:ring-2 focus:ring-blue-100"
                >
            </div>

            <button
                type="submit"
                class="w-full rounded-lg bg-blue-600 px-4 py-3
                       font-semibold text-white transition hover:bg-blue-700"
            >
                Buat Akun Admin
            </button>

        </form>

        <a
            href="index.php"
            class="mt-5 block text-center text-sm font-medium
                   text-blue-600 hover:underline"
        >
            Kembali ke halaman login
        </a>

    </div>

</body>
</html>