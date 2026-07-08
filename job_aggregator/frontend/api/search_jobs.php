<?php

error_reporting(E_ALL);
ini_set('display_errors', 1);

require_once "../config.php";

/*
|--------------------------------------------------------------------------
| AMBIL DATA
|--------------------------------------------------------------------------
*/

$query = "SELECT * FROM jobs ORDER BY id DESC";

$result = mysqli_query($conn, $query);

if (!$result) {

    die(mysqli_error($conn));
}

/*
|--------------------------------------------------------------------------
| ARRAY DATA
|--------------------------------------------------------------------------
*/

$jobs = [];

while ($row = mysqli_fetch_assoc($result)) {

    $jobs[] = [

        "id" => $row["id"],

        "title" => $row["judul_posisi"],

        "company" => $row["nama_perusahaan"],

        "location" => $row["lokasi"],

        "education" => $row["pendidikan"],

        "source" => $row["portal_sumber"],

        "description" => $row["deskripsi"],

        "qualification" => $row["kualifikasi"],

        "link" => $row["link_lowongan"]

    ];
}

/*
|--------------------------------------------------------------------------
| TAMPILKAN JSON
|--------------------------------------------------------------------------
*/

echo "<pre>";

print_r($jobs);

?>