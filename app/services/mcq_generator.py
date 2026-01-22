from typing import List, Dict, Any

from app.models.schemas import MCQQuestion, MCQTest, MCQResult, JDInput
from app.prompts import MCQ_SYSTEM_PROMPT, MCQ_USER_PROMPT
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

    def get_mcq_for_frontend(self, mcq_test: MCQTest) -> Dict[str, Any]:
        """
        Get MCQ test formatted for frontend (without correct answers).

        Args:
            mcq_test: The MCQ test

        Returns:
            Dict with questions (correct_answer hidden)
        """
        questions_for_frontend = []
        for q in mcq_test.questions:
            questions_for_frontend.append({
                "id": q.id,
                "skill_tested": q.skill_tested,
                "difficulty": q.difficulty,
                "question": q.question,
                "options": q.options,
                # correct_answer is NOT included
            })

        return {
            "total_questions": mcq_test.total_questions,
            "role_type": mcq_test.role_type,
            "questions": questions_for_frontend,
        }


# Singleton instance
_mcq_generator = None


def get_mcq_generator() -> MCQGenerator:
    """Get or create the MCQGenerator singleton."""
    global _mcq_generator
    if _mcq_generator is None:
        _mcq_generator = MCQGenerator()
    return _mcq_generator
