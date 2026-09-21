-- Migration 002: Add missing columns to applications table and fix ENUM values

-- Add selected_scholarship_id column if it doesn't exist
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS selected_scholarship_id INT(11) DEFAULT NULL;

-- Add is_locked column if it doesn't exist
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS is_locked TINYINT(1) DEFAULT 0;

-- Expand status ENUM to include awaiting_approval
ALTER TABLE applications
    MODIFY COLUMN status ENUM(
        'pending',
        'approved',
        'denied',
        'evaluated',
        'returned',
        'awaiting_approval'
    ) DEFAULT 'pending';
