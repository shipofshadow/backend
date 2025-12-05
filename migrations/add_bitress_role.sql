-- Migration: Add bitress super admin role
-- Run this ONCE before deployment

-- 1. Modify users table to include bitress role
ALTER TABLE `users` 
MODIFY COLUMN `role` enum('bitress','admin','student') NOT NULL DEFAULT 'student';

-- 2. Create bitress super admin user
-- Password should be set securely (this is a placeholder hash for 'bitress123')
INSERT INTO `users` (`id`, `username`, `password`, `role`, `is_active`, `created_at`, `updated_at`) 
VALUES (-999, 'bitress', '$argon2id$v=19$m=65536,t=3,p=4$YWJjZGVmZ2hpamts$kH2J8K1X9Q0Z3Y5M7N6L4W2R1T3V5U8O', 'bitress', 1, NOW(), NOW())
ON DUPLICATE KEY UPDATE role = 'bitress';

-- 3. Create user details for bitress
INSERT INTO `user_details` (`user_id`, `first_name`, `last_name`, `email`, `avatar`) 
VALUES (-999, 'System', 'Administrator', 'admin@ischolar.xyz', NULL)
ON DUPLICATE KEY UPDATE first_name = 'System', last_name = 'Administrator';
