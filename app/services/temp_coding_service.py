"""
Temporary coding assignment service for frontend testing.
Uses pre-seeded questions (no LLM for generate, real LLM for evaluate).
"""
import json
import time
from datetime import datetime, timezone
from typing import Optional, Tuple
from uuid import UUID

from app.config import CODE_MODEL, CODE_CHECK_PASS_THRESHOLD
from app.db import get_db_pool, get_mcq_db_pool
from app.db.queries import fetch_role_info_by_role_id
from app.db.temp_coding_queries import fetch_random_temp_question, fetch_temp_question_by_id
from app.models.schemas import (
    GenerateCodingAssignmentRequest,
    GenerateCodingAssignmentResponse,
    CodingAssignment,
    CodingAssignmentExample,
    CodingAssignmentTestCase,
    CodingAssignmentMetadata,
    EvaluateCodeRequest,
    CodeEvaluationResult,
    ScoreBreakdown,
)
from app.prompts import CODE_EVALUATION_SYSTEM_PROMPT, CODE_EVALUATION_USER_PROMPT
from app.services.llm_client import get_llm_client
from app.utils.jd_parser import get_role_type
from app.utils.sandbox_fetcher import format_code_files_for_prompt


class TempCodingService:
    """Service for temp coding assignment generation and evaluation."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.model = CODE_MODEL
        self.pass_threshold = CODE_CHECK_PASS_THRESHOLD

    async def generate(
        self, request: GenerateCodingAssignmentRequest
    ) -> GenerateCodingAssignmentResponse:
        """Generate a coding assignment from pre-seeded questions (no LLM)."""

        # Validate jd_id
        try:
            jd_uuid = UUID(request.jd_id)
        except ValueError:
            raise ValueError("jd_id must be a valid UUID")

        # Fetch role info to determine job type
        pool = await get_db_pool()
        role_info = await fetch_role_info_by_role_id(pool, jd_uuid)
        if role_info is None:
            raise ValueError(f"Role not found for jd_id: {request.jd_id}")

        jd_details = role_info["jd_details"]
        role_title = jd_details.get("title", role_info.get("role_name", "Unknown"))
        job_type = get_role_type(role_title)

        # Fetch a random pre-seeded question
        mcq_pool = await get_mcq_db_pool()
        row = await fetch_random_temp_question(mcq_pool, job_type)
        if row is None:
            raise ValueError(f"No temp coding questions found for job_type: {job_type}")

        # Parse JSONB fields
        constraints = row["constraints"] if isinstance(row["constraints"], list) else json.loads(row["constraints"])
        examples_raw = row["examples"] if isinstance(row["examples"], list) else json.loads(row["examples"])
        test_cases_raw = row["test_cases"] if isinstance(row["test_cases"], list) else json.loads(row["test_cases"])
        starter_code = row["starter_code"] if isinstance(row["starter_code"], dict) else json.loads(row["starter_code"])
        skills_tested = row["skills_tested"] if isinstance(row["skills_tested"], list) else json.loads(row["skills_tested"])
        hints = row["hints"] if isinstance(row["hints"], list) else json.loads(row["hints"])

        examples = [
            CodingAssignmentExample(
                input=str(ex.get("input", "")),
                output=str(ex.get("output", "")),
                explanation=str(ex.get("explanation", "")),
            )
            for ex in examples_raw
        ]

        test_cases = [
            CodingAssignmentTestCase(
                input=str(tc.get("input", "")),
                expected_output=str(tc.get("expected_output", "")),
                description=str(tc.get("description", "")),
                is_hidden=tc.get("is_hidden", False),
            )
            for tc in test_cases_raw
        ]

        assignment = CodingAssignment(
            coding_assignment_id=str(row["id"]),
            assignment_id=1,
            title=row["title"],
            problem_statement=row["problem_statement"],
            difficulty=row["difficulty"],
            category=row["category"],
            input_format=row["input_format"] or "",
            output_format=row["output_format"] or "",
            constraints=constraints,
            examples=examples,
            test_cases=test_cases,
            starter_code=starter_code,
            solution_approach=row["solution_approach"] or "",
            skills_tested=skills_tested,
            estimated_time_minutes=row["estimated_time_minutes"] or 30,
            hints=hints,
        )

        now = datetime.now(timezone.utc)

        return GenerateCodingAssignmentResponse(
            success=True,
            message="1 coding assignment generated (pre-seeded)",
            total_assignments=1,
            assignments=[assignment],
            job_title=role_title,
            jd_source="temp_preseeded",
            generation_timestamp=now.isoformat(),
            metadata=CodingAssignmentMetadata(
                candidate_name=request.candidate_id,
                candidate_skills=[],
            ),
            total_estimated_time_minutes=assignment.estimated_time_minutes,
            difficulty_distribution={assignment.difficulty: 1},
            skills_coverage=skills_tested,
        )

    async def evaluate(
        self, request: EvaluateCodeRequest, candidate_id: str = "temp-candidate"
    ) -> Tuple[CodeEvaluationResult, str]:
        """Evaluate code against a temp coding question using real LLM."""
        start_time = time.time()

        # Validate coding_assignment_id
        try:
            question_uuid = UUID(request.coding_assignment_id)
        except ValueError:
            raise ValueError("Invalid coding_assignment_id format")

        mcq_pool = await get_mcq_db_pool()
        row = await fetch_temp_question_by_id(mcq_pool, question_uuid)

        if row is None:
            raise ValueError("Temp coding question not found")

        # Format constraints
        constraints_raw = row["constraints"]
        if isinstance(constraints_raw, str):
            constraints_raw = json.loads(constraints_raw)
        constraints_text = "\n".join(f"- {c}" for c in constraints_raw) if constraints_raw else "None specified"

        # Format examples
        examples_raw = row["examples"]
        if isinstance(examples_raw, str):
            examples_raw = json.loads(examples_raw)
        examples_text = self._format_examples(examples_raw)

        # Format code files
        formatted_code = format_code_files_for_prompt(request.files)

        # Build prompt
        user_prompt = CODE_EVALUATION_USER_PROMPT.format(
            title=row["title"],
            problem_statement=row["problem_statement"],
            input_format=row["input_format"] or "Not specified",
            output_format=row["output_format"] or "Not specified",
            constraints=constraints_text,
            examples=examples_text,
            code_files=formatted_code,
        )

        # Call LLM with CODE_MODEL (real evaluation)
        response = await self.llm_client.get_json_response(
            system_prompt=CODE_EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=self.model,
            endpoint="temp-evaluate-code",
        )

        processing_time = time.time() - start_time

        result = self._parse_evaluation_response(response, processing_time, request.max_score)
        return result, candidate_id

    @staticmethod
    def _format_examples(examples: list) -> str:
        """Format examples list into readable text blocks."""
        if not examples:
            return "None provided"

        parts = []
        for i, ex in enumerate(examples, 1):
            block = f"**Example {i}:**\n"
            block += f"  Input: {ex.get('input', 'N/A')}\n"
            block += f"  Output: {ex.get('output', 'N/A')}"
            if ex.get("explanation"):
                block += f"\n  Explanation: {ex['explanation']}"
            parts.append(block)
        return "\n\n".join(parts)

    def _parse_evaluation_response(
        self, response: dict, processing_time: float, max_score: int
    ) -> CodeEvaluationResult:
        """Parse the LLM response into a CodeEvaluationResult."""
        score_data = response.get("score_breakdown", {})
        score_breakdown = ScoreBreakdown(
            functionality=int(score_data.get("functionality", 0)),
            completeness=int(score_data.get("completeness", 0)),
            code_quality=int(score_data.get("code_quality", 0)),
            best_practices=int(score_data.get("best_practices", 0)),
            performance=int(score_data.get("performance", 0)),
        )

        overall_score = response.get("overall_score")
        if overall_score is None:
            overall_score = (
                score_breakdown.functionality * 0.30
                + score_breakdown.completeness * 0.25
                + score_breakdown.code_quality * 0.20
                + score_breakdown.best_practices * 0.15
                + score_breakdown.performance * 0.10
            )

        passed = response.get("passed")
        if passed is None:
            passed = overall_score >= self.pass_threshold

        return CodeEvaluationResult(
            passed=passed,
            summary=response.get("summary", "Evaluation completed."),
            max_score=max_score,
            overall_score=round(overall_score, 2),
            score_breakdown=score_breakdown,
            strengths=response.get("strengths", []),
            code_issues=response.get("code_issues", []),
            improvements=response.get("improvements", []),
            confidence_level=float(response.get("confidence_level", 0.75)),
            processing_time=round(processing_time, 4),
        )


# Singleton
_temp_coding_service: Optional[TempCodingService] = None


def get_temp_coding_service() -> TempCodingService:
    """Get or create the TempCodingService singleton."""
    global _temp_coding_service
    if _temp_coding_service is None:
        _temp_coding_service = TempCodingService()
    return _temp_coding_service
