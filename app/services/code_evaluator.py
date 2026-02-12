"""
Service for evaluating candidate code submissions using LLM.
"""
import time
from typing import Dict, Any, Optional

from app.config import CODE_MODEL, CODE_CHECK_PASS_THRESHOLD, CODE_CHECK_MAX_SCORE
from app.models.schemas import (
    CodeEvaluationResult,
    ScoreBreakdown,
    EvaluateCodeRequest,
)
from app.prompts import CODE_EVALUATION_SYSTEM_PROMPT, CODE_EVALUATION_USER_PROMPT
from app.services.llm_client import get_llm_client
from app.utils.sandbox_fetcher import fetch_sandbox_files, format_code_files_for_prompt


class CodeEvaluator:
    """Service for evaluating code submissions."""

    def __init__(self):
        self.llm_client = get_llm_client()
        self.model = CODE_MODEL
        self.pass_threshold = CODE_CHECK_PASS_THRESHOLD
        self.max_score = CODE_CHECK_MAX_SCORE

    async def evaluate_code(
        self, request: EvaluateCodeRequest
    ) -> CodeEvaluationResult:
        """
        Evaluate a code submission.

        Args:
            request: EvaluateCodeRequest with candidate_id, question, answer_files, sandbox_link

        Returns:
            CodeEvaluationResult with detailed evaluation
        """
        start_time = time.time()

        # Merge answer_files with sandbox files if sandbox_link provided
        code_files = dict(request.answer_files)

        if request.sandbox_link:
            sandbox_files = await fetch_sandbox_files(request.sandbox_link)
            if sandbox_files:
                # Merge sandbox files (answer_files take precedence)
                for path, content in sandbox_files.items():
                    if path not in code_files:
                        code_files[path] = content

        # Format code files for the prompt
        formatted_code = format_code_files_for_prompt(code_files)

        # Build the user prompt
        user_prompt = CODE_EVALUATION_USER_PROMPT.format(
            question=request.question,
            code_files=formatted_code,
            candidate_id=request.candidate_id,
            sandbox_url=request.sandbox_link or "Not provided",
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
        return self._parse_evaluation_response(response, processing_time)

    def _parse_evaluation_response(
        self, response: Dict[str, Any], processing_time: float
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
            max_score=self.max_score,
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
