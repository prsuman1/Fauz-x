"""
Service for capability-level CV-JD matching using DB-backed data.
"""
import json
from datetime import datetime
from typing import Dict, Any, Optional
from uuid import UUID

from app.db import get_db_pool
from app.db.queries import fetch_role_info_by_role_id, fetch_candidate_with_user
from app.prompts import MATCH_V2_SYSTEM_PROMPT, MATCH_V2_USER_PROMPT
from app.services.llm_client import get_llm_client
from app.models.schemas import (
    MatchV2Result,
    EvaluationSection,
    SkillCategory,
    CapabilityScore,
    NiceToHaves,
    NiceToHaveMatched,
    MatchV2Summary,
    HiringDecision,
)


class MatcherV2:
    """Service for capability-level matching against DB data."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def match(self, jd_id: str, candidate_id: str) -> MatchV2Result:
        """
        Fetch JD and candidate from DB, run LLM evaluation, return result.
        """
        # Validate UUIDs
        try:
            jd_uuid = UUID(jd_id)
            candidate_uuid = UUID(candidate_id)
        except ValueError:
            raise ValueError("jd_id and candidate_id must be valid UUIDs")

        pool = await get_db_pool()

        # Fetch data from DB
        role_info = await fetch_role_info_by_role_id(pool, jd_uuid)
        if role_info is None:
            raise ValueError(f"Role not found for jd_id: {jd_id}")

        candidate = await fetch_candidate_with_user(pool, candidate_uuid)
        if candidate is None:
            raise ValueError(f"Candidate not found for candidate_id: {candidate_id}")

        # Build candidate name
        candidate_name = self._build_candidate_name(candidate)

        # Format candidate data for prompt
        candidate_experience = self._format_experience(candidate.get("parsed_experience"))
        candidate_education = self._format_education(candidate.get("parsed_education"))
        candidate_projects = self._format_projects(candidate.get("parsed_projects"))
        candidate_parsed_skills = self._format_parsed_skills(candidate.get("parsed_skills"))

        # Build JD fields
        jd_details = role_info["jd_details"]
        capabilities = role_info["capabilities"]

        position = jd_details.get("title", role_info.get("role_name", "Unknown"))
        jd_skills = ", ".join(jd_details.get("skills", []))
        jd_nice_to_have = ", ".join(jd_details.get("niceToHave", [])) or "None specified"
        jd_responsibilities = "\n".join(
            f"- {r}" for r in jd_details.get("responsibilities", [])
        ) or "Not specified"
        jd_description = jd_details.get("description", "")

        # Format capabilities list
        capabilities_list = "\n".join(
            f"{i+1}. {cap}" for i, cap in enumerate(capabilities)
        ) if capabilities else "No specific capabilities defined"

        # Build prompt
        user_prompt = MATCH_V2_USER_PROMPT.format(
            position=position,
            jd_description=jd_description,
            jd_skills=jd_skills,
            jd_nice_to_have=jd_nice_to_have,
            jd_responsibilities=jd_responsibilities,
            capabilities_list=capabilities_list,
            candidate_name=candidate_name,
            candidate_role_title=candidate.get("role_title", "Not specified"),
            experience_years=candidate.get("experience_years", 0),
            candidate_skills=", ".join(candidate.get("skills", [])),
            candidate_summary=candidate.get("summary", "Not provided"),
            candidate_experience=candidate_experience,
            candidate_education=candidate_education,
            candidate_projects=candidate_projects,
            candidate_parsed_skills=candidate_parsed_skills,
        )

        # Call LLM
        response = await self.llm_client.get_json_response(
            system_prompt=MATCH_V2_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            endpoint="match",
        )

        # Parse into result model
        return self._parse_response(response, position, candidate_name)

    def _build_candidate_name(self, candidate: Dict[str, Any]) -> str:
        if candidate.get("full_name"):
            return candidate["full_name"]
        parts = []
        if candidate.get("first_name"):
            parts.append(candidate["first_name"])
        if candidate.get("last_name"):
            parts.append(candidate["last_name"])
        return " ".join(parts) or "Unknown"

    def _format_experience(self, parsed_experience: Any) -> str:
        if not parsed_experience:
            return "No work experience data available"
        lines = []
        for exp in parsed_experience:
            title = exp.get("title", "Unknown Role")
            company = exp.get("company", "Unknown Company")
            duration = exp.get("duration", "")
            desc = exp.get("description", "")
            lines.append(f"**{title}** at {company} ({duration})")
            if desc:
                lines.append(f"  {desc}")
            for resp in exp.get("responsibilities", []):
                lines.append(f"  - {resp}")
        return "\n".join(lines)

    def _format_education(self, parsed_education: Any) -> str:
        if not parsed_education:
            return "No education data available"
        lines = []
        for edu in parsed_education:
            degree = edu.get("degree", "Unknown Degree")
            institution = edu.get("institution", "Unknown Institution")
            field = edu.get("field", "")
            year = edu.get("year", "")
            line = f"{degree} — {institution}"
            if field:
                line += f" ({field})"
            if year:
                line += f" [{year}]"
            lines.append(line)
        return "\n".join(lines)

    def _format_projects(self, parsed_projects: Any) -> str:
        if not parsed_projects:
            return "No project data available"
        lines = []
        for proj in parsed_projects:
            name = proj.get("name", "Unnamed Project")
            desc = proj.get("description", "")
            techs = ", ".join(proj.get("technologies", []))
            lines.append(f"**{name}**")
            if desc:
                lines.append(f"  {desc}")
            if techs:
                lines.append(f"  Technologies: {techs}")
        return "\n".join(lines)

    def _format_parsed_skills(self, parsed_skills: Any) -> str:
        if not parsed_skills:
            return "No detailed skills breakdown available"
        lines = []
        for category, skills in parsed_skills.items():
            if skills and isinstance(skills, list) and len(skills) > 0:
                lines.append(f"- {category}: {', '.join(str(s) for s in skills)}")
        return "\n".join(lines) or "No detailed skills breakdown available"

    def _parse_response(
        self, response: Dict[str, Any], position: str, candidate_name: str
    ) -> MatchV2Result:
        """Parse LLM JSON response into MatchV2Result."""

        # Parse evaluation criteria sections
        eval_criteria_raw = response.get("evaluationCriteria", {})
        eval_criteria = {}
        for section_key, section_data in eval_criteria_raw.items():
            categories = []
            for cat_data in section_data.get("categories", []):
                capabilities = []
                for cap_data in cat_data.get("capabilities", []):
                    capabilities.append(CapabilityScore(
                        id=cap_data.get("id", 0),
                        skill=cap_data.get("skill", ""),
                        expectedLevel=cap_data.get("expectedLevel", "intermediate"),
                        candidateLevel=cap_data.get("candidateLevel", "none"),
                        score=min(max(cap_data.get("score", 0), 0), 10),
                        evidence=cap_data.get("evidence", ""),
                        meetsRequirement=cap_data.get("meetsRequirement", False),
                    ))
                categories.append(SkillCategory(
                    category=cat_data.get("category", ""),
                    score=cat_data.get("score", 0),
                    weight=cat_data.get("weight", 0),
                    capabilities=capabilities,
                ))
            eval_criteria[section_key] = EvaluationSection(
                score=section_data.get("score", 0),
                weight=section_data.get("weight", 0),
                weightedContribution=section_data.get("weightedContribution", 0),
                categories=categories,
            )

        # Parse nice-to-haves
        nth_raw = response.get("niceToHaves", {})
        nice_to_haves = NiceToHaves(
            matched=[
                NiceToHaveMatched(
                    skill=m.get("skill", ""),
                    evidence=m.get("evidence", ""),
                    bonusPoints=m.get("bonusPoints", 0),
                )
                for m in nth_raw.get("matched", [])
            ],
            missing=nth_raw.get("missing", []),
        )

        # Parse summary
        sum_raw = response.get("summary", {})
        summary = MatchV2Summary(
            totalRequirements=sum_raw.get("totalRequirements", 0),
            requirementsMetFully=sum_raw.get("requirementsMetFully", 0),
            requirementsMetPartially=sum_raw.get("requirementsMetPartially", 0),
            requirementsMissing=sum_raw.get("requirementsMissing", 0),
            matchPercentage=sum_raw.get("matchPercentage", 0),
            strengths=sum_raw.get("strengths", []),
            gaps=sum_raw.get("gaps", []),
            criticalMatches=sum_raw.get("criticalMatches", []),
            criticalGaps=sum_raw.get("criticalGaps", []),
            trainableWithin3Months=sum_raw.get("trainableWithin3Months", []),
        )

        # Parse hiring decision
        hd_raw = response.get("hiringDecision", {})
        hiring_decision = HiringDecision(
            thresholdMet=hd_raw.get("thresholdMet", False),
            scoreRange=hd_raw.get("scoreRange", ""),
            rating=hd_raw.get("rating", ""),
            recommendation=hd_raw.get("recommendation", "REJECT"),
            confidence=hd_raw.get("confidence", "medium"),
            rationale=hd_raw.get("rationale", ""),
        )

        return MatchV2Result(
            position=response.get("position", position),
            candidateName=response.get("candidateName", candidate_name),
            overallScore=response.get("overallScore", 0),
            evaluationCriteria=eval_criteria,
            niceToHaves=nice_to_haves,
            summary=summary,
            hiringDecision=hiring_decision,
            analysisTimestamp=datetime.now().isoformat(),
            domainMismatch=response.get("domainMismatch", False),
        )


# Singleton
_matcher_v2: Optional[MatcherV2] = None


def get_matcher_v2() -> MatcherV2:
    """Get or create the MatcherV2 singleton."""
    global _matcher_v2
    if _matcher_v2 is None:
        _matcher_v2 = MatcherV2()
    return _matcher_v2
