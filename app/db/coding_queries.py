import json
from typing import Any, Dict, List, Optional
from uuid import UUID

import asyncpg


async def fetch_mcq_tested_skills(
    pool: asyncpg.Pool,
    candidate_id: UUID,
    role_id: UUID,
) -> List[str]:
    """
    Find distinct skill tags already tested via MCQ for this candidate+role pair.

    Joins AI_sessions -> AI_questions -> AI_question_skill_tags.
    """
    rows = await pool.fetch(
        """
        SELECT DISTINCT st.skill_tag
        FROM "AI_sessions" s
        JOIN "AI_questions" q ON q.session_id = s.id
        JOIN "AI_question_skill_tags" st ON st.question_id = q.id
        WHERE s.candidate_id = $1 AND s.role_id = $2
        """,
        candidate_id,
        role_id,
    )
    return [row["skill_tag"] for row in rows]


async def fetch_coding_assignment_by_id(
    pool: asyncpg.Pool,
    assignment_id: UUID,
) -> Any:
    """
    Fetch a single coding assignment by its UUID primary key.
    Returns the row as an asyncpg.Record or None.
    """
    return await pool.fetchrow(
        """
        SELECT id, candidate_id, role_id, assignment_number, title, problem_statement,
               difficulty, category, input_format, output_format, constraints,
               examples, test_cases, starter_code, solution_approach,
               time_complexity, space_complexity, skills_tested,
               estimated_time_minutes, hints, job_title, metadata
        FROM "AI_coding_assignments"
        WHERE id = $1
        """,
        assignment_id,
    )


async def store_coding_assignment(
    pool: asyncpg.Pool,
    assignment: Dict[str, Any],
) -> UUID:
    """
    Insert a single coding assignment into AI_coding_assignments.
    Returns the generated UUID.
    """
    return await pool.fetchval(
        """
        INSERT INTO "AI_coding_assignments"
            (candidate_id, role_id, assignment_number, title, problem_statement,
             difficulty, category, input_format, output_format, constraints,
             examples, test_cases, starter_code, solution_approach,
             time_complexity, space_complexity, skills_tested,
             estimated_time_minutes, hints, job_title, metadata)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
        RETURNING id
        """,
        assignment["candidate_id"],
        assignment["role_id"],
        assignment["assignment_number"],
        assignment["title"],
        assignment["problem_statement"],
        assignment["difficulty"],
        assignment.get("category", ""),
        assignment.get("input_format", ""),
        assignment.get("output_format", ""),
        json.dumps(assignment.get("constraints", [])),
        json.dumps(assignment.get("examples", [])),
        json.dumps(assignment.get("test_cases", [])),
        json.dumps(assignment.get("starter_code", {})),
        assignment.get("solution_approach", ""),
        assignment.get("time_complexity", ""),
        assignment.get("space_complexity", ""),
        json.dumps(assignment.get("skills_tested", [])),
        assignment.get("estimated_time_minutes", 30),
        json.dumps(assignment.get("hints", [])),
        assignment.get("job_title", ""),
        json.dumps(assignment.get("metadata", {})),
    )


async def store_coding_assignments(
    pool: asyncpg.Pool,
    assignments: List[Dict[str, Any]],
) -> List[UUID]:
    """Batch insert coding assignments in a transaction. Returns list of generated UUIDs."""
    ids = []
    async with pool.acquire() as conn:
        async with conn.transaction():
            for a in assignments:
                uid = await conn.fetchval(
                    """
                    INSERT INTO "AI_coding_assignments"
                        (candidate_id, role_id, assignment_number, title, problem_statement,
                         difficulty, category, input_format, output_format, constraints,
                         examples, test_cases, starter_code, solution_approach,
                         time_complexity, space_complexity, skills_tested,
                         estimated_time_minutes, hints, job_title, metadata)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10,
                            $11, $12, $13, $14, $15, $16, $17, $18, $19, $20, $21)
                    RETURNING id
                    """,
                    a["candidate_id"],
                    a["role_id"],
                    a["assignment_number"],
                    a["title"],
                    a["problem_statement"],
                    a["difficulty"],
                    a.get("category", ""),
                    a.get("input_format", ""),
                    a.get("output_format", ""),
                    json.dumps(a.get("constraints", [])),
                    json.dumps(a.get("examples", [])),
                    json.dumps(a.get("test_cases", [])),
                    json.dumps(a.get("starter_code", {})),
                    a.get("solution_approach", ""),
                    a.get("time_complexity", ""),
                    a.get("space_complexity", ""),
                    json.dumps(a.get("skills_tested", [])),
                    a.get("estimated_time_minutes", 30),
                    json.dumps(a.get("hints", [])),
                    a.get("job_title", ""),
                    json.dumps(a.get("metadata", {})),
                )
                ids.append(uid)
    return ids
