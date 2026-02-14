from datetime import datetime, timezone
from typing import List, Dict, Any
from uuid import UUID

from app.models.schemas import (
    GenerateCodingAssignmentRequest,
    GenerateCodingAssignmentResponse,
    CodingAssignment,
    CodingAssignmentExample,
    CodingAssignmentTestCase,
    CodingAssignmentMetadata,
)
from app.prompts import CODING_ASSIGNMENT_SYSTEM_PROMPT, CODING_ASSIGNMENT_USER_PROMPT
from app.db import get_db_pool, get_mcq_db_pool
from app.db.queries import fetch_role_info_by_role_id, fetch_candidate_with_user
from app.db.coding_queries import fetch_mcq_tested_skills, store_coding_assignments
from app.services.llm_client import get_llm_client


class CodingAssignmentGenerator:
    """Service for generating tailored coding assignments."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def generate_coding_assignment(
        self, request: GenerateCodingAssignmentRequest
    ) -> GenerateCodingAssignmentResponse:
        # Validate UUIDs
        try:
            jd_uuid = UUID(request.jd_id)
            candidate_uuid = UUID(request.candidate_id)
        except ValueError:
            raise ValueError("jd_id and candidate_id must be valid UUIDs")

        pool = await get_db_pool()

        # Fetch role info and candidate from main DB
        role_info = await fetch_role_info_by_role_id(pool, jd_uuid)
        if role_info is None:
            raise ValueError(f"Role not found for jd_id: {request.jd_id}")

        candidate = await fetch_candidate_with_user(pool, candidate_uuid)
        if candidate is None:
            raise ValueError(f"Candidate not found for candidate_id: {request.candidate_id}")

        # Extract role data
        jd_details = role_info["jd_details"]
        capabilities = role_info["capabilities"] or []
        role_title = jd_details.get("title", role_info.get("role_name", "Unknown"))

        # Extract candidate data
        candidate_name = candidate.get("full_name") or " ".join(
            filter(None, [candidate.get("first_name"), candidate.get("last_name")])
        ) or "Unknown"
        candidate_skills_list = candidate.get("skills", [])

        # Smart capability selection
        mcq_pool = await get_mcq_db_pool()
        tested_skills = await fetch_mcq_tested_skills(mcq_pool, candidate_uuid, jd_uuid)

        if tested_skills:
            tested_lower = {s.lower() for s in tested_skills}
            gap = [cap for cap in capabilities if cap.lower() not in tested_lower]
            if gap:
                target_capabilities = gap
                capability_selection_reason = (
                    f"These {len(gap)} capabilities were NOT tested via MCQ "
                    f"(MCQ tested: {', '.join(tested_skills[:10])}). "
                    "Focusing on untested gaps."
                )
            else:
                target_capabilities = capabilities
                capability_selection_reason = (
                    "All capabilities were already tested via MCQ. "
                    "Using full capability list for deeper assessment."
                )
        else:
            target_capabilities = capabilities
            capability_selection_reason = (
                "No MCQ session found for this candidate+role. "
                "Using full capability list."
            )

        # Build prompts
        role_skills = jd_details.get("skills", [])
        user_prompt = CODING_ASSIGNMENT_USER_PROMPT.format(
            role_title=role_title,
            role_skills=", ".join(role_skills) if role_skills else "Not specified",
            target_capabilities=", ".join(target_capabilities) if target_capabilities else "General programming",
            capability_selection_reason=capability_selection_reason,
            candidate_name=candidate_name,
            num_assignments=request.num_assignments,
            all_role_capabilities=", ".join(capabilities) if capabilities else "Not specified",
        )

        # Call LLM
        response = await self.llm_client.get_json_response(
            system_prompt=CODING_ASSIGNMENT_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=8192,
            endpoint="generate-coding-assignment",
        )

        # Parse response into CodingAssignment objects
        assignments = self._parse_response(response)

        # Store in DB
        now = datetime.now(timezone.utc)
        assignment_dicts = []
        for a in assignments:
            assignment_dicts.append({
                "candidate_id": candidate_uuid,
                "role_id": jd_uuid,
                "assignment_number": a.assignment_id,
                "title": a.title,
                "problem_statement": a.problem_statement,
                "difficulty": a.difficulty,
                "category": a.category,
                "input_format": a.input_format,
                "output_format": a.output_format,
                "constraints": a.constraints,
                "examples": [e.model_dump() for e in a.examples],
                "test_cases": [t.model_dump() for t in a.test_cases],
                "starter_code": a.starter_code,
                "solution_approach": a.solution_approach,
                "time_complexity": a.time_complexity,
                "space_complexity": a.space_complexity,
                "skills_tested": a.skills_tested,
                "estimated_time_minutes": a.estimated_time_minutes,
                "hints": a.hints,
                "job_title": role_title,
                "metadata": {
                    "candidate_name": candidate_name,
                    "candidate_skills": candidate_skills_list,
                    "capability_selection_reason": capability_selection_reason,
                    "target_capabilities": target_capabilities,
                },
            })

        stored_ids = await store_coding_assignments(mcq_pool, assignment_dicts)

        # Assign DB UUIDs to assignment objects
        for assignment, db_id in zip(assignments, stored_ids):
            assignment.coding_assignment_id = str(db_id)

        # Build response
        total_time = sum(a.estimated_time_minutes for a in assignments)
        difficulty_dist: Dict[str, int] = {}
        all_skills: List[str] = []
        for a in assignments:
            difficulty_dist[a.difficulty] = difficulty_dist.get(a.difficulty, 0) + 1
            all_skills.extend(a.skills_tested)

        return GenerateCodingAssignmentResponse(
            success=True,
            message=f"{len(assignments)} coding assignment(s) generated",
            total_assignments=len(assignments),
            assignments=assignments,
            job_title=role_title,
            jd_source="database",
            generation_timestamp=now.isoformat(),
            metadata=CodingAssignmentMetadata(
                candidate_name=candidate_name,
                candidate_skills=candidate_skills_list,
                current_role=candidate.get("role_title"),
            ),
            total_estimated_time_minutes=total_time,
            difficulty_distribution=difficulty_dist,
            skills_coverage=list(dict.fromkeys(all_skills)),
        )

    def _parse_response(self, response: Dict[str, Any]) -> List[CodingAssignment]:
        """Parse LLM JSON response into CodingAssignment objects."""
        assignments_data = response.get("assignments", [])
        if isinstance(response, list):
            assignments_data = response

        assignments = []
        for i, a in enumerate(assignments_data):
            examples = [
                CodingAssignmentExample(
                    input=str(ex.get("input", "")),
                    output=str(ex.get("output", "")),
                    explanation=str(ex.get("explanation", "")),
                )
                for ex in a.get("examples", [])
            ]

            test_cases = [
                CodingAssignmentTestCase(
                    input=str(tc.get("input", "")),
                    expected_output=str(tc.get("expected_output", "")),
                    description=str(tc.get("description", "")),
                    is_hidden=tc.get("is_hidden", False),
                )
                for tc in a.get("test_cases", [])
            ]

            assignments.append(CodingAssignment(
                assignment_id=a.get("assignment_id", i + 1),
                title=a.get("title", ""),
                problem_statement=a.get("problem_statement", ""),
                difficulty=a.get("difficulty", "medium"),
                category=a.get("category", ""),
                input_format=str(a.get("input_format", "")),
                output_format=str(a.get("output_format", "")),
                constraints=a.get("constraints", []),
                examples=examples,
                test_cases=test_cases,
                starter_code=a.get("starter_code", {}),
                solution_approach=a.get("solution_approach", ""),
                time_complexity=a.get("time_complexity", ""),
                space_complexity=a.get("space_complexity", ""),
                skills_tested=a.get("skills_tested", []),
                estimated_time_minutes=a.get("estimated_time_minutes", 30),
                hints=a.get("hints", []),
            ))

        return assignments


# Singleton
_coding_assignment_generator = None


def get_coding_assignment_generator() -> CodingAssignmentGenerator:
    """Get or create the CodingAssignmentGenerator singleton."""
    global _coding_assignment_generator
    if _coding_assignment_generator is None:
        _coding_assignment_generator = CodingAssignmentGenerator()
    return _coding_assignment_generator
