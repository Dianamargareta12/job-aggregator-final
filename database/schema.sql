-- Struktur database final: 4 tabel.
-- Jalankan hanya untuk membuat tabel yang belum tersedia.

CREATE TABLE IF NOT EXISTS admins (
    id INT AUTO_INCREMENT PRIMARY KEY,
    nama_lengkap VARCHAR(150) NOT NULL,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS jobs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    judul_posisi VARCHAR(255) NULL,
    nama_perusahaan VARCHAR(255) NULL,
    lokasi TEXT NULL,
    pendidikan VARCHAR(100) NULL,
    deskripsi LONGTEXT NULL,
    kualifikasi LONGTEXT NULL,
    link_lowongan TEXT NULL,
    portal_sumber VARCHAR(100) NULL,
    keyword_sumber VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_jobs_portal (portal_sumber),
    INDEX idx_jobs_pendidikan (pendidikan),
    INDEX idx_jobs_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS scraping_runs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    status VARCHAR(20) NOT NULL DEFAULT 'running',
    started_at DATETIME NOT NULL,
    finished_at DATETIME NULL,
    raw_glints INT DEFAULT 0,
    raw_jobstreet INT DEFAULT 0,
    raw_lokerid INT DEFAULT 0,
    total_raw INT DEFAULT 0,
    empty_data INT DEFAULT 0,
    duplicate_data INT DEFAULT 0,
    invalid_url INT DEFAULT 0,
    education_not_detected INT DEFAULT 0,
    total_rejected INT DEFAULT 0,
    total_clean INT DEFAULT 0,
    clean_csv_path VARCHAR(255) NULL,
    message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS raw_jobs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    scraping_run_id INT NOT NULL,
    portal_sumber VARCHAR(50) NOT NULL,
    judul_posisi TEXT NULL,
    nama_perusahaan TEXT NULL,
    lokasi TEXT NULL,
    pendidikan TEXT NULL,
    deskripsi LONGTEXT NULL,
    link_lowongan TEXT NULL,
    validation_status VARCHAR(20) DEFAULT 'raw',
    rejection_reason VARCHAR(255) NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_raw_run (scraping_run_id),
    INDEX idx_raw_portal (portal_sumber),
    INDEX idx_raw_status (validation_status),
    CONSTRAINT fk_raw_jobs_run FOREIGN KEY (scraping_run_id)
        REFERENCES scraping_runs(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
