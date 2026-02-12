import uuid
from datetime import datetime, timezone
from typing import List, Dict, Any, Tuple
from uuid import UUID

from app.models.schemas import (
    MCQQuestion,
    MCQTest,
    MCQResult,
    JDInput,
    MCQQuestionForFrontend,
    MCQTestForFrontend,
    GenerateMCQV2Request,
    MCQV2Question,
)
from app.prompts import MCQ_SYSTEM_PROMPT, MCQ_USER_PROMPT, MCQ_V2_SYSTEM_PROMPT, MCQ_V2_USER_PROMPT
from app.db import get_db_pool, get_mcq_db_pool
from app.db.queries import fetch_role_info_by_role_id, fetch_candidate_with_user
from app.db.mcq_queries import create_mcq_session, store_mcq_questions
from app.services.llm_client import get_llm_client
from app.utils.jd_parser import get_role_type, get_all_skills_from_jd
from app.config import MIN_MCQ_QUESTIONS, MCQ_PASS_PERCENTAGE


class MCQGenerator:
    """Service for generating and evaluating MCQ tests."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def generate_mcq_test(
        self,
        jd_input: JDInput,
        cv_skills: List[str],
    ) -> MCQTest:
        """
        Generate MCQ test based on JD and CV skills.

        Args:
            jd_input: Parsed JD input
            cv_skills: List of skills extracted from CV

        Returns:
            MCQTest with questions
        """
        # Determine role type
        role_type = get_role_type(jd_input.details.title)

        # Get all skills from JD
        jd_skills = get_all_skills_from_jd(jd_input)

        # Combine all skills (union)
        all_skills = list(set(jd_skills + cv_skills))

        # Build the user prompt
        user_prompt = MCQ_USER_PROMPT.format(
            role_type=role_type,
            jd_title=jd_input.details.title,
            jd_skills=", ".join(jd_input.details.skills),
            capabilities=", ".join(jd_input.capabilities),
            cv_skills=", ".join(cv_skills) if cv_skills else "Not extracted",
            all_skills=", ".join(all_skills),
        )

        # Get LLM response
        response = await self.llm_client.get_json_response(
            system_prompt=MCQ_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_tokens=100000,
            endpoint="generate-mcq",
        )

        # Parse the response
        return self._parse_mcq_response(response, role_type)

    def _parse_mcq_response(self, response: Dict[str, Any], role_type: str) -> MCQTest:
        """Parse the LLM response into an MCQTest object."""

        questions_data = response.get("questions", [])

        # Handle case where response is just an array
        if isinstance(response, list):
            questions_data = response

        questions = []
        for i, q in enumerate(questions_data):
            question = MCQQuestion(
                id=q.get("id", i + 1),
                skill_tested=q.get("skill_tested", "General"),
                difficulty=q.get("difficulty", "medium"),
                question=q.get("question", ""),
                options=q.get("options", {}),
                correct_answer=q.get("correct_answer", "A"),
            )
            questions.append(question)

        # Ensure minimum questions
        if len(questions) < MIN_MCQ_QUESTIONS:
            # The LLM should generate enough, but log a warning
            print(f"Warning: Only {len(questions)} questions generated, minimum is {MIN_MCQ_QUESTIONS}")

        return MCQTest(
            total_questions=len(questions),
            role_type=role_type,
            questions=questions,
        )

    def evaluate_mcq(self, mcq_test: MCQTest, answers: Dict[int, str]) -> MCQResult:
        """
        Evaluate candidate's MCQ answers.

        Args:
            mcq_test: The MCQ test with correct answers
            answers: Dict mapping question_id to selected option

        Returns:
            MCQResult with score and details
        """
        correct_count = 0
        wrong_count = 0
        details = []

        for question in mcq_test.questions:
            user_answer = answers.get(question.id, "")
            is_correct = user_answer.upper() == question.correct_answer.upper()

            if is_correct:
                correct_count += 1
            else:
                wrong_count += 1

            details.append({
                "question_id": question.id,
                "skill_tested": question.skill_tested,
                "question": question.question,
                "user_answer": user_answer,
                "correct_answer": question.correct_answer,
                "is_correct": is_correct,
                "options": question.options,
            })

        total = mcq_test.total_questions
        score_percentage = (correct_count / total * 100) if total > 0 else 0
        passed = score_percentage >= MCQ_PASS_PERCENTAGE

        return MCQResult(
            total_questions=total,
            correct_answers=correct_count,
            wrong_answers=wrong_count,
            score_percentage=round(score_percentage, 2),
            passed=passed,
            details=details,
        )

    def get_mcq_for_frontend(self, mcq_test: MCQTest) -> MCQTestForFrontend:
        """
        Get MCQ test formatted for frontend (without correct answers).

        Args:
            mcq_test: The MCQ test

        Returns:
            MCQTestForFrontend without correct_answer in questions
        """
        questions_for_frontend = []
        for q in mcq_test.questions:
            questions_for_frontend.append(
                MCQQuestionForFrontend(
                    id=q.id,
                    skill_tested=q.skill_tested,
                    difficulty=q.difficulty,
                    question=q.question,
                    options=q.options,
                )
            )

        return MCQTestForFrontend(
            total_questions=mcq_test.total_questions,
            role_type=mcq_test.role_type,
            questions=questions_for_frontend,
        )

    # ============================
    # MCQ V2 Methods (DB-backed)
    # ============================

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

        # Call LLM — Claude-3-Haiku caps at 4096 output tokens which is too small
        # for 20 questions with explanations, so use fallback model for large sets
        from app.config import FALLBACK_MODEL
        model = FALLBACK_MODEL if request.num_questions > 10 else None
        response = await self.llm_client.get_json_response(
            system_prompt=MCQ_V2_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=model,
            max_tokens=8192,
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

            # Determine type based on number of correct answers
            q_type = q.get("type", "single_choice")
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
