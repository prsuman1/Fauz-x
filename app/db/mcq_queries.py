import json
from typing import Dict, Any, List, Optional
from uuid import UUID

import asyncpg


async def create_mcq_session(
    pool: asyncpg.Pool,
    session_id: UUID,
    candidate_id: UUID,
    role_id: UUID,
    domain: str,
    role_title: str,
    candidate_name: str,
    total_questions: int,
    difficulty_mix: Dict[str, float],
) -> None:
    """Insert a new MCQ session into AI_sessions."""
    await pool.execute(
        """
        INSERT INTO "AI_sessions"
            (id, candidate_id, role_id, domain, role_title, candidate_name,
             total_questions, difficulty_mix, status)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, 'generated')
        """,
        session_id,
        candidate_id,
        role_id,
        domain,
        role_title,
        candidate_name,
        total_questions,
        json.dumps(difficulty_mix),
    )


async def store_mcq_questions(
    pool: asyncpg.Pool,
    session_id: UUID,
    questions: List[Dict[str, Any]],
) -> None:
    """
    Batch-insert questions, options, correct answers, and skill tags in a transaction.

    Each question dict should have:
        question_id, type, difficulty, question, domain, source, explanation,
        options (list of 4 strings), correct_answers (list of labels), skill_tags (list)
    """
    async with pool.acquire() as conn:
        async with conn.transaction():
            for q in questions:
                labels = ["A", "B", "C", "D"]

                # Insert question row, get back its UUID
                q_uuid = await conn.fetchval(
                    """
                    INSERT INTO "AI_questions"
                        (session_id, question_id, type, difficulty, question_text,
                         domain, source, explanation)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                    RETURNING id
                    """,
                    session_id,
                    q["question_id"],
                    q.get("type", "single_choice"),
                    q["difficulty"],
                    q["question"],
                    q.get("domain", ""),
                    q.get("source", "llm_generated"),
                    q.get("explanation"),
                )

                # Insert options
                options = q.get("options", [])
                for idx, opt_text in enumerate(options[:4]):
                    await conn.execute(
                        """
                        INSERT INTO "AI_question_options"
                            (question_id, option_label, option_text, display_order)
                        VALUES ($1, $2, $3, $4)
                        """,
                        q_uuid,
                        labels[idx],
                        opt_text,
                        idx,
                    )

                # Insert correct answers
                for ans_label in q.get("correct_answers", []):
                    await conn.execute(
                        """
                        INSERT INTO "AI_question_correct_answers"
                            (question_id, answer_label)
                        VALUES ($1, $2)
                        """,
                        q_uuid,
                        ans_label,
                    )

                # Insert skill tags
                for tag in q.get("skill_tags", []):
                    await conn.execute(
                        """
                        INSERT INTO "AI_question_skill_tags"
                            (question_id, skill_tag)
                        VALUES ($1, $2)
                        """,
                        q_uuid,
                        tag,
                    )


async def fetch_mcq_answers_by_session(
    pool: asyncpg.Pool,
    session_id: UUID,
) -> Optional[List[Dict[str, Any]]]:
    """
    Fetch questions with their correct answers for a session.

    Returns list of dicts with question_id, question, correct_answers, explanation, type.
    Returns None if no session/questions found.
    """
    rows = await pool.fetch(
        """
        SELECT q.question_id, q.question_text, q.type, q.explanation,
               array_agg(ca.answer_label ORDER BY ca.answer_label) AS correct_answers
        FROM "AI_questions" q
        JOIN "AI_question_correct_answers" ca ON ca.question_id = q.id
        WHERE q.session_id = $1
        GROUP BY q.question_id, q.question_text, q.type, q.explanation
        ORDER BY q.question_id
        """,
        session_id,
    )

    if not rows:
        return None

    results = []
    for row in rows:
        correct_answers = list(row["correct_answers"])
        results.append({
            "question_id": row["question_id"],
            "question": row["question_text"],
            "correct_answers": correct_answers,
            "correct_answer": correct_answers[0] if correct_answers else "",
            "explanation": row["explanation"] or "",
            "type": row["type"],
        })

    return results
