-- Migration 005: Add explanation column to evaluations table
-- Stores the fuzzy logic breakdown (memberships + fired_rules) as JSON
-- so students can see why they received their eligibility score.

ALTER TABLE evaluations
    ADD COLUMN IF NOT EXISTS explanation JSON NULL
        COMMENT 'Fuzzy logic breakdown: memberships and fired_rules for student display';
