-- Migration 004: Add slot quota columns to scholarships table
-- total_slots = NULL means unlimited (no cap)
-- filled_slots = count of approved applications for this scholarship

ALTER TABLE scholarships
    ADD COLUMN IF NOT EXISTS total_slots INT UNSIGNED NULL DEFAULT NULL
        COMMENT 'Maximum number of scholars. NULL = unlimited.',
    ADD COLUMN IF NOT EXISTS filled_slots INT UNSIGNED NOT NULL DEFAULT 0
        COMMENT 'Number of approved applications for this scholarship.';
