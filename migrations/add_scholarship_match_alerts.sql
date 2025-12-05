-- Migration: Add scholarship_match_alerts table for smart matching notifications
-- This table stores alerts when new scholarships match student profiles

CREATE TABLE IF NOT EXISTS `scholarship_match_alerts` (
    `id` INT AUTO_INCREMENT PRIMARY KEY,
    `student_id` INT NOT NULL,
    `scholarship_id` INT NOT NULL,
    `match_score` DECIMAL(5,2) NOT NULL,
    `match_summary` TEXT NULL,
    `top_factors` JSON NULL,
    `alert_sent` BOOLEAN DEFAULT FALSE,
    `alert_sent_at` TIMESTAMP NULL,
    `is_read` BOOLEAN DEFAULT FALSE,
    `read_at` TIMESTAMP NULL,
    `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT `fk_alerts_student` FOREIGN KEY (`student_id`) REFERENCES `students`(`user_id`) ON DELETE CASCADE,
    CONSTRAINT `fk_alerts_scholarship` FOREIGN KEY (`scholarship_id`) REFERENCES `scholarships`(`id`) ON DELETE CASCADE,
    UNIQUE KEY `unique_alert` (`student_id`, `scholarship_id`),
    INDEX `idx_alert_sent` (`alert_sent`),
    INDEX `idx_student_alerts` (`student_id`, `is_read`),
    INDEX `idx_scholarship_alerts` (`scholarship_id`),
    INDEX `idx_match_score` (`match_score`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Add notification type for scholarship match alerts
-- Note: This assumes notification types are stored in code, not in database.
-- The notification_service.py will be updated to include 'scholarship_match_alert' type.
