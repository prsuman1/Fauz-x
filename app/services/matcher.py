from typing import Dict, Any

from app.models.schemas import (
    MatchResult,
    MatchGrade,
    SkillAnalysis,
    ExperienceAnalysis,
    EducationAnalysis,
    RiskAssessment,
    JDInput,
)
from app.prompts import MATCHING_SYSTEM_PROMPT, MATCHING_USER_PROMPT
from app.services.llm_client import get_llm_client
from app.utils.jd_parser import format_jd_for_prompt
from app.config import REJECT_THRESHOLD, SHORTLIST_THRESHOLD


class Matcher:
    """Service for matching CVs against JDs."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def analyze_match(self, cv_text: str, jd_input: JDInput) -> MatchResult:
        """
        Analyze the match between a CV and JD.

        Args:
            cv_text: Extracted text from the CV
            jd_input: Parsed JD input with details and capabilities

        Returns:
            MatchResult with score, grade, and detailed analysis
        """
        # Format JD for prompt
        jd_data = format_jd_for_prompt(jd_input)

        # Build the user prompt
        user_prompt = MATCHING_USER_PROMPT.format(
            jd_title=jd_data["jd_title"],
            jd_description=jd_data["jd_description"],
            jd_skills=jd_data["jd_skills"],
            jd_nice_to_have=jd_data["jd_nice_to_have"],
            jd_responsibilities=jd_data["jd_responsibilities"],
            cv_text=cv_text,
        )

        # Get LLM response
        response = await self.llm_client.get_json_response(
            system_prompt=MATCHING_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Parse and validate the response
        return self._parse_match_response(response)

    def _parse_match_response(self, response: Dict[str, Any]) -> MatchResult:
        """Parse the LLM response into a MatchResult object."""

        # Extract score and determine grade
        score = int(response.get("match_score", 0))
        grade = self._determine_grade(score)

        # Parse skill analysis
        skill_data = response.get("skill_analysis", {})
        skill_analysis = SkillAnalysis(
            matched_required=skill_data.get("matched_required", []),
            missing_required=skill_data.get("missing_required", []),
            matched_preferred=skill_data.get("matched_preferred", []),
            missing_preferred=skill_data.get("missing_preferred", []),
            additional_relevant=skill_data.get("additional_relevant", []),
            skill_match_percentage=float(skill_data.get("skill_match_percentage", 0)),
            transferable_skills_note=skill_data.get("transferable_skills_note"),
            skill_concerns=skill_data.get("skill_concerns"),
        )

        # Parse experience analysis
        exp_data = response.get("experience_analysis", {})
        experience_analysis = ExperienceAnalysis(
            total_years=float(exp_data.get("total_years", 0)),
            relevant_years=float(exp_data.get("relevant_years", 0)),
            relevance_score=float(exp_data.get("relevance_score", 0)),
            experience_type=exp_data.get("experience_type", "fresher"),
            key_experiences=exp_data.get("key_experiences", []),
            experience_quality=exp_data.get("experience_quality", "medium"),
            domain_match=exp_data.get("domain_match", "partial"),
            notes=exp_data.get("notes"),
        )

        # Parse education analysis
        edu_data = response.get("education_analysis", {})
        education_analysis = EducationAnalysis(
            requirement_met=edu_data.get("requirement_met", True),
            degree=edu_data.get("degree"),
            relevance=edu_data.get("relevance", "medium"),
            notes=edu_data.get("notes"),
        )

        # Parse risk assessment
        risk_data = response.get("risk_assessment", {})
        risk_assessment = RiskAssessment(
            risk_level=risk_data.get("risk_level", "medium"),
            primary_risk=risk_data.get("primary_risk"),
            secondary_risks=risk_data.get("secondary_risks", []),
            mitigation=risk_data.get("mitigation"),
            hiring_risk_score=int(risk_data.get("hiring_risk_score", 5)),
        )

        # Build the final result
        return MatchResult(
            score=score,
            grade=grade,
            summary=response.get("summary", ""),
            skill_analysis=skill_analysis,
            experience_analysis=experience_analysis,
            education_analysis=education_analysis,
            strengths=response.get("strengths", []),
            gaps=response.get("gaps", []),
            red_flags=response.get("red_flags", []),
            risk_assessment=risk_assessment,
            recommendation=self._map_recommendation(grade),
            recommendation_reason=response.get("recommendation_reason", ""),
            confidence_level=response.get("confidence_level", "medium"),
            interview_focus_areas=response.get("interview_focus_areas", []),
            onboarding_suggestions=response.get("onboarding_suggestions", []),
            final_verdict=response.get("final_verdict", ""),
        )

    def _determine_grade(self, score: int) -> MatchGrade:
        """Determine the grade based on score using updated thresholds."""
        if score >= SHORTLIST_THRESHOLD:  # 90+
            return MatchGrade.STRONG_HIRE
        elif score >= REJECT_THRESHOLD:  # 80-89
            return MatchGrade.SHORTLIST
        else:  # <80
            return MatchGrade.REJECT

    def _map_recommendation(self, grade: MatchGrade) -> str:
        """Map grade to recommendation string."""
        return grade.value


# Singleton instance
_matcher = None


def get_matcher() -> Matcher:
    """Get or create the Matcher singleton."""
    global _matcher
    if _matcher is None:
        _matcher = Matcher()
    return _matcher
