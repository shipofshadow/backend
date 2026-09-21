-- Migration 003: Expand scholarship_selections status ENUM for student selection workflow

ALTER TABLE scholarship_selections
    MODIFY COLUMN status ENUM(
        'selected',
        'awarded',
        'cancelled',
        'pending',
        'student_chosen',
        'accepted',
        'rejected'
    ) DEFAULT 'selected';
