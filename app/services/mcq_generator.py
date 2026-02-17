import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from uuid import UUID

from app.models.schemas import (
    GenerateMCQV2Request,
    MCQV2Question,
)
from app.prompts import MCQ_V2_SYSTEM_PROMPT, MCQ_V2_USER_PROMPT
from app.db import get_db_pool, get_mcq_db_pool
from app.db.queries import fetch_role_info_by_role_id, fetch_candidate_with_user
from app.db.mcq_queries import create_mcq_session, store_mcq_questions
from app.services.llm_client import get_llm_client


class MCQGenerator:
    """Service for generating and evaluating MCQ tests."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def generate_mcq_v2(
        self, request: GenerateMCQV2Request
    ) -> Tuple[List[MCQV2Question], str, str, str, List[str]]:
        """
        Generate MCQ questions from DB-backed role and candidate data.
        Stores session + questions in mcq_database.

        Returns:
            Tuple of (questions, role_title, session_id, candidate_name, role_skills_list)
        """
        # Validate UUIDs
        try:
            jd_uuid = UUID(request.jd_id)
            candidate_uuid = UUID(request.candidate_id)
        except ValueError:
            raise ValueError("jd_id and candidate_id must be valid UUIDs")

        pool = await get_db_pool()

        # Fetch role info and candidate from DB
        role_info = await fetch_role_info_by_role_id(pool, jd_uuid)
        if role_info is None:
            raise ValueError(f"Role not found for jd_id: {request.jd_id}")

        candidate = await fetch_candidate_with_user(pool, candidate_uuid)
        if candidate is None:
            raise ValueError(f"Candidate not found for candidate_id: {request.candidate_id}")

        # Extract role data
        jd_details = role_info["jd_details"]
        capabilities = role_info["capabilities"]
        role_title = jd_details.get("title", role_info.get("role_name", "Unknown"))
        role_skills_list = jd_details.get("skills", [])
        role_skills = ", ".join(role_skills_list)
        role_capabilities = "\n".join(
            f"- {cap}" for cap in capabilities
        ) if capabilities else "None specified"
        role_nice_to_have = ", ".join(jd_details.get("niceToHave", [])) or "None specified"
        role_responsibilities = "\n".join(
            f"- {r}" for r in jd_details.get("responsibilities", [])
        ) or "Not specified"

        # Extract candidate data
        candidate_name = candidate.get("full_name") or " ".join(
            filter(None, [candidate.get("first_name"), candidate.get("last_name")])
        ) or "Unknown"
        candidate_skills = ", ".join(candidate.get("skills", [])) or "Not available"
        candidate_parsed_skills = self._format_parsed_skills_for_prompt(
            candidate.get("parsed_skills")
        )

        # Build difficulty breakdown string
        difficulty_breakdown = self._build_difficulty_info(
            request.num_questions, request.difficulty_mix
        )

        # Build user prompt
        user_prompt = MCQ_V2_USER_PROMPT.format(
            role_title=role_title,
            domain=request.domain,
            role_skills=role_skills,
            role_capabilities=role_capabilities,
            role_nice_to_have=role_nice_to_have,
            role_responsibilities=role_responsibilities,
            candidate_name=candidate_name,
            candidate_skills=candidate_skills,
            candidate_parsed_skills=candidate_parsed_skills,
            num_questions=request.num_questions,
            difficulty_breakdown=difficulty_breakdown,
        )

        # Use DEFAULT_MODEL for all MCQ generation
        # Increase max_tokens for larger question sets
        max_tokens = 8192 if request.num_questions <= 10 else 16384
        response = await self.llm_client.get_json_response(
            system_prompt=MCQ_V2_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=max_tokens,
            endpoint="generate-mcq",
        )

        # Parse response
        questions = self._parse_mcq_v2_response(response, request.domain)

        # Generate deterministic session_id
        now = datetime.now(timezone.utc).isoformat()
        session_id = uuid.uuid5(
            uuid.NAMESPACE_DNS,
            f"{request.candidate_id}-{request.jd_id}-{now}",
        )

        # Store in mcq_database
        mcq_pool = await get_mcq_db_pool()

        await create_mcq_session(
            pool=mcq_pool,
            session_id=session_id,
            candidate_id=candidate_uuid,
            role_id=jd_uuid,
            domain=request.domain,
            role_title=role_title,
            candidate_name=candidate_name,
            total_questions=len(questions),
            difficulty_mix=request.difficulty_mix,
        )

        # Prepare question dicts for storage
        q_dicts = []
        for q in questions:
            q_dicts.append({
                "question_id": q.question_id,
                "type": q.type,
                "difficulty": q.difficulty,
                "question": q.question,
                "domain": q.domain,
                "source": q.source,
                "explanation": q.explanation,
                "options": q.options,
                "correct_answers": q.correct_answers,
                "skill_tags": q.skill_tags,
            })

        await store_mcq_questions(
            pool=mcq_pool,
            session_id=session_id,
            questions=q_dicts,
        )

        return questions, role_title, str(session_id), candidate_name, role_skills_list

    def _format_parsed_skills_for_prompt(self, parsed_skills: Any) -> str:
        """Format JSONB parsed_skills into readable text for the prompt."""
        if not parsed_skills:
            return "No detailed skills breakdown available"
        lines = []
        for category, skills in parsed_skills.items():
            if skills and isinstance(skills, list) and len(skills) > 0:
                lines.append(f"- {category}: {', '.join(str(s) for s in skills)}")
        return "\n".join(lines) or "No detailed skills breakdown available"

    def _build_difficulty_info(self, num_questions: int, difficulty_mix: Dict[str, float]) -> str:
        """Compute per-difficulty counts and return a readable breakdown string."""
        counts = {}
        remaining = num_questions
        items = list(difficulty_mix.items())
        for i, (level, ratio) in enumerate(items):
            if i == len(items) - 1:
                counts[level] = remaining
            else:
                count = round(num_questions * ratio)
                counts[level] = count
                remaining -= count
        parts = [f"{level}: {count} questions" for level, count in counts.items()]
        return ", ".join(parts)

    def _parse_mcq_v2_response(self, response: Dict[str, Any], domain: str) -> List[MCQV2Question]:
        """Parse LLM JSON response into a list of MCQV2Question objects."""
        questions_data = response.get("questions", [])
        if isinstance(response, list):
            questions_data = response

        questions = []
        for i, q in enumerate(questions_data):
            # Handle options: could be list or dict
            raw_options = q.get("options", [])
            if isinstance(raw_options, dict):
                options = [raw_options.get(k, "") for k in ["A", "B", "C", "D"]]
            elif isinstance(raw_options, list):
                options = raw_options[:4]
            else:
                options = []

            # Parse correct_answers (new format) with fallback to correct_answer (old)
            correct_answers = q.get("correct_answers", [])
            if not correct_answers:
                # Fallback: derive from old single correct_answer field
                old_answer = q.get("correct_answer", "A")
                correct_answers = [old_answer]

            # Derive primary correct_answer from the list
            correct_answer = correct_answers[0] if correct_answers else "A"

            # Determine type — only allow single_choice or multiple_choice
            q_type = q.get("type", "single_choice")
            if q_type not in ("single_choice", "multiple_choice"):
                q_type = "single_choice"
            if len(correct_answers) > 1:
                q_type = "multiple_choice"

            questions.append(MCQV2Question(
                question_id=q.get("question_id", i + 1),
                type=q_type,
                difficulty=q.get("difficulty", "medium"),
                question=q.get("question", ""),
                domain=q.get("domain", domain),
                skill_tags=q.get("skill_tags", []),
                options=options,
                correct_answer=correct_answer,
                correct_answers=correct_answers,
                explanation=q.get("explanation", ""),
                source=q.get("source", "llm_generated"),
            ))

        return questions


# Singleton instance
_mcq_generator = None


def get_mcq_generator() -> MCQGenerator:
    """Get or create the MCQGenerator singleton."""
    global _mcq_generator
    if _mcq_generator is None:
        _mcq_generator = MCQGenerator()
    return _mcq_generator
