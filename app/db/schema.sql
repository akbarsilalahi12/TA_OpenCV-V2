-- =========================================================
-- Database
-- =========================================================
CREATE DATABASE IF NOT EXISTS parking_db
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

USE parking_db;

-- =========================================================
-- Tabel: slots
-- Master polygon slot parkir
-- =========================================================
CREATE TABLE IF NOT EXISTS slots (
    id            INT AUTO_INCREMENT PRIMARY KEY,
    slot_code     VARCHAR(20)  NOT NULL UNIQUE,
    polygon_json  JSON         NOT NULL,
    is_active     TINYINT(1)   NOT NULL DEFAULT 1,
    created_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: slot_status
-- Status terkini tiap slot
-- =========================================================
CREATE TABLE IF NOT EXISTS slot_status (
    slot_id     INT PRIMARY KEY,
    status      ENUM('FREE','FULL') NOT NULL,
    ratio       DECIMAL(5,3) NULL,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                          ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_status_slot
        FOREIGN KEY (slot_id) REFERENCES slots(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: occupancy_log
-- Log historis perubahan status (insert hanya saat status BERUBAH)
-- =========================================================
CREATE TABLE IF NOT EXISTS occupancy_log (
    id            BIGINT AUTO_INCREMENT PRIMARY KEY,
    slot_id       INT NOT NULL,
    status        ENUM('FREE','FULL') NOT NULL,
    ratio         DECIMAL(5,3) NULL,
    detected_at   DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_slot_time (slot_id, detected_at),
    INDEX idx_time (detected_at),
    CONSTRAINT fk_log_slot
        FOREIGN KEY (slot_id) REFERENCES slots(id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: occupancy_summary
-- Snapshot agregat (untuk chart dashboard)
-- =========================================================
CREATE TABLE IF NOT EXISTS occupancy_summary (
    id           BIGINT AUTO_INCREMENT PRIMARY KEY,
    snapshot_at  DATETIME NOT NULL,
    total_slot   INT NOT NULL,
    free_slot    INT NOT NULL,
    full_slot    INT NOT NULL,
    INDEX idx_time (snapshot_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- =========================================================
-- Tabel: system_event
-- Audit event sistem
-- =========================================================
CREATE TABLE IF NOT EXISTS system_event (
    id          BIGINT AUTO_INCREMENT PRIMARY KEY,
    event_type  VARCHAR(40) NOT NULL,
    message     TEXT,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_type_time (event_type, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
