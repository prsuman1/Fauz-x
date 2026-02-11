-- MCQ Database Schema (mcq_database)
-- All tables are AI_-prefixed for namespace isolation.
-- Run this once against the mcq_database.

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

CREATE TABLE IF NOT EXISTS "AI_question_options" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    option_label    CHAR(1) NOT NULL,
    option_text     TEXT NOT NULL,
    display_order   INTEGER NOT NULL,
    UNIQUE(question_id, option_label)
);

CREATE TABLE IF NOT EXISTS "AI_question_correct_answers" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    answer_label    CHAR(1) NOT NULL,
    UNIQUE(question_id, answer_label)
);

CREATE TABLE IF NOT EXISTS "AI_question_skill_tags" (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    question_id     UUID NOT NULL REFERENCES "AI_questions"(id) ON DELETE CASCADE,
    skill_tag       VARCHAR(255) NOT NULL,
    UNIQUE(question_id, skill_tag)
);
