-- ============================================================
-- Flu Dynamics Tutor — Supabase migration
-- Run once in the Supabase SQL Editor to create dedicated tables
-- for the flu tutor (independent of the Borneo tutor tables).
-- ============================================================

-- 1. Dedicated sessions table for the flu tutor
CREATE TABLE IF NOT EXISTS flu_sessions (
    id                  TEXT        PRIMARY KEY,
    student_id          TEXT        NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active         TIMESTAMPTZ NOT NULL DEFAULT now(),
    pre_assessment      JSONB,
    pre_assessment_raw  TEXT,
    session_outcome     JSONB,
    transcript          TEXT,
    cld_dot             TEXT,
    quiz_results        JSONB,
    bot_results         JSONB,
    survey_results      JSONB
);

-- 2. Dedicated turns table for the flu tutor
CREATE TABLE IF NOT EXISTS flu_turns (
    id                      BIGSERIAL   PRIMARY KEY,
    session_id              TEXT        NOT NULL REFERENCES flu_sessions(id) ON DELETE CASCADE,
    turn_number             INT         NOT NULL,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    student_input           TEXT,
    llm_scratchpad          TEXT,
    tutor_response          TEXT,
    extracted_stocks        JSONB,
    extracted_flows         JSONB,
    extracted_parameters    JSONB,
    extracted_loops         JSONB,
    guardrail_errors        JSONB,
    snapshot_stocks         JSONB,
    snapshot_flows          JSONB,
    snapshot_parameters     JSONB,
    snapshot_loops          JSONB
);

-- If the table already exists, add the new column:
ALTER TABLE flu_sessions ADD COLUMN IF NOT EXISTS bot_results JSONB;

-- 3. Indexes
CREATE INDEX IF NOT EXISTS idx_flu_sessions_student
    ON flu_sessions (student_id, last_active DESC);

CREATE INDEX IF NOT EXISTS idx_flu_turns_session
    ON flu_turns (session_id, turn_number ASC);
