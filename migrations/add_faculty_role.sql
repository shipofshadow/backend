-- Migration: Add FACULTY role with campus scope
-- Run this migration to add the FACULTY role for campus-scoped admin actions
-- 
-- IMPORTANT: The FACULTY role allows admin-like actions but only within the user's assigned campus.
-- ADMIN and bitress roles remain unrestricted across all campuses.

-- 1. Modify users table to include faculty role in the enum
ALTER TABLE `users` 
MODIFY COLUMN `role` enum('bitress','admin','faculty','student') NOT NULL DEFAULT 'student';

-- 2. Add campus_id column to users table for FACULTY role association
-- This allows FACULTY users to be associated with a specific campus
ALTER TABLE `users`
ADD COLUMN `campus_id` INT NULL DEFAULT NULL AFTER `role`,
ADD CONSTRAINT `fk_users_campus` FOREIGN KEY (`campus_id`) REFERENCES `campuses`(`campus_id`) ON DELETE SET NULL ON UPDATE CASCADE;

-- 3. Create index for faster campus-based queries
CREATE INDEX `idx_users_campus_role` ON `users` (`campus_id`, `role`);
