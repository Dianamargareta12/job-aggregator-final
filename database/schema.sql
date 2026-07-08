CREATE TABLE IF NOT EXISTS jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    judul_posisi VARCHAR(255),
    nama_perusahaan VARCHAR(255),
    lokasi VARCHAR(255),
    pendidikan VARCHAR(100),
    link_lowongan TEXT,
    portal_sumber VARCHAR(100)
);