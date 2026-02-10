import json
from typing import Dict, Any, Optional

import asyncpg


async def fetch_role_info_by_role_id(
    pool: asyncpg.Pool, role_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch role info (JD details + capabilities) by role_id.

    Returns:
        Dict with role_name, department, seniority_level, jd_details, capabilities
        or None if not found.
    """
    query = """
        SELECT r.role_name, r.department, r.seniority_level,
               ri.jd_details, ri.capabilities
        FROM role_info ri
        JOIN roles r ON ri.role_id = r.id
        WHERE ri.role_id = $1
    """
    row = await pool.fetchrow(query, role_id)
    if row is None:
        return None

    jd_details = row["jd_details"]
    if isinstance(jd_details, str):
        jd_details = json.loads(jd_details)

    capabilities = row["capabilities"]
    if isinstance(capabilities, str):
        capabilities = json.loads(capabilities)

    return {
        "role_name": row["role_name"],
        "department": row["department"],
        "seniority_level": row["seniority_level"],
        "jd_details": jd_details,
        "capabilities": capabilities,
    }


async def fetch_candidate_with_user(
    pool: asyncpg.Pool, candidate_id: str
) -> Optional[Dict[str, Any]]:
    """
    Fetch candidate profile with user name info.

    Returns:
        Dict with candidate fields + full_name, first_name, last_name
        or None if not found.
    """
    query = """
        SELECT c.skills, c.experience_years, c.role_title, c.summary,
               c.parsed_education, c.parsed_experience, c.parsed_projects, c.parsed_skills,
               u.full_name, u.first_name, u.last_name
        FROM candidates c
        JOIN users u ON c.user_id = u.id
        WHERE c.id = $1
    """
    row = await pool.fetchrow(query, candidate_id)
    if row is None:
        return None

    def _parse_jsonb(val):
        if val is None:
            return None
        if isinstance(val, str):
            return json.loads(val)
        return val

    return {
        "skills": list(row["skills"]) if row["skills"] else [],
        "experience_years": row["experience_years"],
        "role_title": row["role_title"],
        "summary": row["summary"],
        "parsed_education": _parse_jsonb(row["parsed_education"]),
        "parsed_experience": _parse_jsonb(row["parsed_experience"]),
        "parsed_projects": _parse_jsonb(row["parsed_projects"]),
        "parsed_skills": _parse_jsonb(row["parsed_skills"]),
        "full_name": row["full_name"],
        "first_name": row["first_name"],
        "last_name": row["last_name"],
    }
