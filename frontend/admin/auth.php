<?php

require_once __DIR__ . "/../config.php";

// Batas waktu session: 2 jam.
$sessionTimeout = 7200;

if (!isset($_SESSION["admin_id"])) {
    header("Location: index.php");
    exit;
}

// Logout otomatis jika session terlalu lama tidak digunakan.
if (
    isset($_SESSION["admin_last_activity"]) &&
    time() - $_SESSION["admin_last_activity"] > $sessionTimeout
) {
    $_SESSION = [];
    session_destroy();

    header("Location: index.php?status=session_expired");
    exit;
}

$_SESSION["admin_last_activity"] = time();