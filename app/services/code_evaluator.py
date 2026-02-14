"""
Service for evaluating candidate code submissions using LLM.
"""
import json
import time
from typing import Dict, Any, Optional, Tuple
from uuid import UUID

from app.config import CODE_MODEL, CODE_CHECK_PASS_THRESHOLD
from app.db import get_mcq_db_pool
from app.db.coding_queries import fetch_coding_assignment_by_id
from app.models.schemas import (
    CodeEvaluationResult,
    ScoreBreakdown,
    EvaluateCodeRequest,
)
from app.prompts import CODE_EVALUATION_SYSTEM_PROMPT, CODE_EVALUATION_USER_PROMPT
from app.services.llm_client import get_llm_client
from app.utils.sandbox_fetcher import format_code_files_for_prompt


class CodeEvaluator:
    """Service for evaluating code submissions."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.model = CODE_MODEL
        self.pass_threshold = CODE_CHECK_PASS_THRESHOLD

    async def evaluate_code(
        self, request: EvaluateCodeRequest
    ) -> Tuple[CodeEvaluationResult, str]:
        """
        Evaluate a code submission.

        Args:
            request: EvaluateCodeRequest with coding_assignment_id, files, max_score

        Returns:
            Tuple of (CodeEvaluationResult, candidate_id)
        """
        start_time = time.time()

        # Fetch the coding assignment from DB
        try:
            assignment_uuid = UUID(request.coding_assignment_id)
        except ValueError:
            raise ValueError("Invalid coding_assignment_id format")

        pool = await get_mcq_db_pool()
        row = await fetch_coding_assignment_by_id(pool, assignment_uuid)

        if row is None:
            raise ValueError("Coding assignment not found")

        candidate_id = str(row["candidate_id"])

        # Format constraints (JSON list → bullet points)
        constraints_raw = row["constraints"]
        if isinstance(constraints_raw, str):
            constraints_raw = json.loads(constraints_raw)
        constraints_text = "\n".join(f"- {c}" for c in constraints_raw) if constraints_raw else "None specified"

        # Format examples (JSON list of dicts → formatted blocks)
        examples_raw = row["examples"]
        if isinstance(examples_raw, str):
            examples_raw = json.loads(examples_raw)
        examples_text = self._format_examples(examples_raw)

        # Format code files for the prompt
        formatted_code = format_code_files_for_prompt(request.files)

        # Build the user prompt
        user_prompt = CODE_EVALUATION_USER_PROMPT.format(
            title=row["title"],
            problem_statement=row["problem_statement"],
            input_format=row["input_format"] or "Not specified",
            output_format=row["output_format"] or "Not specified",
            constraints=constraints_text,
            examples=examples_text,
            code_files=formatted_code,
        )

        # Get LLM response using CODE_MODEL
        response = await self.llm_client.get_json_response(
            system_prompt=CODE_EVALUATION_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            model=self.model,
            endpoint="evaluate-code",
        )

        processing_time = time.time() - start_time

        # Parse and validate the response
        result = self._parse_evaluation_response(
            response, processing_time, request.max_score
        )
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
        self, response: Dict[str, Any], processing_time: float, max_score: int
    ) -> CodeEvaluationResult:
        """Parse the LLM response into a CodeEvaluationResult."""

        # Extract score breakdown
        score_data = response.get("score_breakdown", {})
        score_breakdown = ScoreBreakdown(
            functionality=int(score_data.get("functionality", 0)),
            completeness=int(score_data.get("completeness", 0)),
            code_quality=int(score_data.get("code_quality", 0)),
            best_practices=int(score_data.get("best_practices", 0)),
            performance=int(score_data.get("performance", 0)),
        )

        # Calculate overall score if not provided
        overall_score = response.get("overall_score")
        if overall_score is None:
            overall_score = (
                score_breakdown.functionality * 0.30 +
                score_breakdown.completeness * 0.25 +
                score_breakdown.code_quality * 0.20 +
                score_breakdown.best_practices * 0.15 +
                score_breakdown.performance * 0.10
            )

        # Determine if passed
        passed = response.get("passed")
        if passed is None:
            passed = overall_score >= self.pass_threshold

        # Build the result
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


# Singleton instance
_code_evaluator: Optional[CodeEvaluator] = None


def get_code_evaluator() -> CodeEvaluator:
    """Get or create the CodeEvaluator singleton."""
    global _code_evaluator
    if _code_evaluator is None:
        _code_evaluator = CodeEvaluator()
    return _code_evaluator
