-- Migration 001: Add student selection status values to scholarship_selections.status ENUM
--
-- The student scholarship selection workflow requires three new status values:
--   'student_chosen' - student has selected this scholarship
--   'accepted'       - admin has accepted the student's selection
--   'rejected'       - admin has rejected the student's selection
--
-- Run this migration once against your database before deploying the new endpoints.

ALTER TABLE scholarship_selections
    MODIFY COLUMN status ENUM(
        'selected',
        'awarded',
        'pending',
        'student_chosen',
        'accepted',
        'rejected'
    ) NOT NULL DEFAULT 'pending';
