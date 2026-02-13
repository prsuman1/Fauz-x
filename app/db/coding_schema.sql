-- Coding Assignments Schema (mcq_database)
-- AI_-prefixed for namespace isolation.
-- Run this once against the mcq_database.

CREATE TABLE IF NOT EXISTS "AI_coding_assignments" (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id            UUID NOT NULL,
    role_id                 UUID NOT NULL,
    assignment_number       INTEGER NOT NULL,
    title                   VARCHAR(500) NOT NULL,
    problem_statement       TEXT NOT NULL,
    difficulty              VARCHAR(20) NOT NULL,
    category                VARCHAR(255),
    input_format            TEXT,
    output_format           TEXT,
    constraints             JSONB,
    examples                JSONB,
    test_cases              JSONB,
    starter_code            JSONB,
    solution_approach       TEXT,
    time_complexity         TEXT,
    space_complexity        TEXT,
    skills_tested           JSONB,
    estimated_time_minutes  INTEGER,
    hints                   JSONB,
    job_title               VARCHAR(500),
    generation_timestamp    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata                JSONB,
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_coding_assignments_candidate
    ON "AI_coding_assignments"(candidate_id);
CREATE INDEX IF NOT EXISTS idx_ai_coding_assignments_role
    ON "AI_coding_assignments"(role_id);
CREATE INDEX IF NOT EXISTS idx_ai_coding_assignments_candidate_role
    ON "AI_coding_assignments"(candidate_id, role_id);
