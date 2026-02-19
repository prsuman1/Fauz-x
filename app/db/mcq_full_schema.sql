-- MCQ Database Full Schema (mcq_database)
-- Combined DDL for all tables needed by the FaujX app.
-- All CREATE TABLE IF NOT EXISTS — safe to re-run.
-- Run this once against the mcq_database on any new environment.

-- ============================================================
-- 1. AI_sessions
-- ============================================================
CREATE TABLE IF NOT EXISTS "AI_sessions" (
    id              UUID PRIMARY KEY,
    candidate_id    UUID NOT NULL,
    role_id         UUID NOT NULL,
    domain          VARCHAR(255) NOT NULL,
    role_title      VARCHAR(500),
    candidate_name  VARCHAR(500),
    total_questions INTEGER NOT NULL,
    difficulty_mix  JSONB NOT NULL,
    status          VARCHAR(50) NOT NULL DEFAULT 'generated',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_candidate ON "AI_sessions"(candidate_id);
CREATE INDEX IF NOT EXISTS idx_ai_sessions_role ON "AI_sessions"(role_id);

-- ============================================================
-- 2. AI_questions
-- ============================================================
CREATE TABLE IF NOT EXISTS "AI_questions" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id      UUID NOT NULL REFERENCES "AI_sessions"(id) ON DELETE CASCADE,
    question_id     INTEGER NOT NULL,
    type            VARCHAR(50) NOT NULL DEFAULT 'single_choice',
    difficulty      VARCHAR(20) NOT NULL,
    question_text   TEXT NOT NULL,
    domain          VARCHAR(255),
    source          VARCHAR(100) NOT NULL DEFAULT 'llm_generated',
    explanation     TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(session_id, question_id)
);
CREATE INDEX IF NOT EXISTS idx_ai_questions_session ON "AI_questions"(session_id);

-- ============================================================
-- 3. AI_question_options
-- ============================================================
CREATE TABLE IF NOT EXISTS "AI_question_options" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    option_label    CHAR(1) NOT NULL,
    option_text     TEXT NOT NULL,
    display_order   INTEGER NOT NULL,
    UNIQUE(question_id, option_label)
);

-- ============================================================
-- 4. AI_question_correct_answers
-- ============================================================
CREATE TABLE IF NOT EXISTS "AI_question_correct_answers" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    answer_label    CHAR(1) NOT NULL,
    UNIQUE(question_id, answer_label)
);

-- ============================================================
-- 5. AI_question_skill_tags
-- ============================================================
CREATE TABLE IF NOT EXISTS "AI_question_skill_tags" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    skill_tag       VARCHAR(255) NOT NULL,
    UNIQUE(question_id, skill_tag)
);

-- ============================================================
-- 6. AI_coding_assignments
-- ============================================================
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

-- ============================================================
-- 7. temp_coding_questions
-- ============================================================
CREATE TABLE IF NOT EXISTS temp_coding_questions (
    id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_type                TEXT NOT NULL,
    title                   TEXT NOT NULL,
    category                TEXT NOT NULL DEFAULT '',
    difficulty              TEXT NOT NULL DEFAULT 'easy',
    problem_statement       TEXT NOT NULL,
    input_format            TEXT DEFAULT '',
    output_format           TEXT DEFAULT '',
    constraints             JSONB DEFAULT '[]',
    examples                JSONB DEFAULT '[]',
    test_cases              JSONB DEFAULT '[]',
    starter_code            JSONB DEFAULT '{}',
    solution_approach       TEXT DEFAULT '',
    skills_tested           JSONB DEFAULT '[]',
    estimated_time_minutes  INT DEFAULT 30,
    hints                   JSONB DEFAULT '[]',
    created_at              TIMESTAMPTZ DEFAULT NOW()
);
