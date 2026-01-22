import json
import re
from pathlib import Path
from typing import Union, Tuple, List

from app.models.schemas import JDDetails, JDInput


def parse_jd(jd_text: str) -> JDInput:
    """
    Parse JD text content with two sections: JD Details and Capabilities.

    Expected format:
    JD Details
    {"icon": "...", "title": "...", "skills": [...], ...}

    Capabilities
    ["skill1", "skill2", ...]
    """
    lines = jd_text.strip().split("\n")

    jd_details_json = None
    capabilities_json = None

    current_section = None

    for line in lines:
        line_stripped = line.strip()

        # Check for section headers
        if line_stripped.lower().startswith("jd details"):
            current_section = "details"
            continue
        elif line_stripped.lower().startswith("capabilities"):
            current_section = "capabilities"
            continue

        # Skip empty lines
        if not line_stripped:
            continue

        # Try to parse JSON content
        if current_section == "details" and line_stripped.startswith("{"):
            try:
                jd_details_json = json.loads(line_stripped)
            except json.JSONDecodeError:
                # Try to find JSON in the line
                match = re.search(r'\{.*\}', line_stripped)
                if match:
                    try:
                        jd_details_json = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

        elif current_section == "capabilities" and line_stripped.startswith("["):
            try:
                capabilities_json = json.loads(line_stripped)
            except json.JSONDecodeError:
                # Try to find JSON array in the line
                match = re.search(r'\[.*\]', line_stripped)
                if match:
                    try:
                        capabilities_json = json.loads(match.group())
                    except json.JSONDecodeError:
                        pass

    if not jd_details_json:
        raise ValueError("Could not parse JD Details JSON from the provided text")

    if not capabilities_json:
        capabilities_json = []

    # Create JDDetails object
    jd_details = JDDetails(
        icon=jd_details_json.get("icon"),
        title=jd_details_json.get("title", "Unknown Position"),
        skills=jd_details_json.get("skills", []),
        niceToHave=jd_details_json.get("niceToHave", []),
        demandLevel=jd_details_json.get("demandLevel"),
        description=jd_details_json.get("description", ""),
        responsibilities=jd_details_json.get("responsibilities", [])
    )

    return JDInput(details=jd_details, capabilities=capabilities_json)


def parse_jd_file(file_path: Union[str, Path]) -> JDInput:
    """
    Parse JD from a text file.

    Args:
        file_path: Path to the JD text file

    Returns:
        JDInput object with details and capabilities
    """
    file_path = Path(file_path)

    if not file_path.exists():
        raise FileNotFoundError(f"JD file not found: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        jd_text = f.read()

    return parse_jd(jd_text)


def get_role_type(jd_title: str) -> str:
    """
    Determine the role type from JD title for MCQ generation.

    Returns one of: frontend, backend, fullstack, ai_ml, devops, other
    """
    title_lower = jd_title.lower()

    # AI/ML roles
    if any(kw in title_lower for kw in ["ai", "ml", "machine learning", "data scientist", "deep learning"]):
        return "ai_ml"

    # DevOps roles
    if any(kw in title_lower for kw in ["devops", "sre", "platform", "infrastructure", "cloud engineer"]):
        return "devops"

    # Fullstack roles
    if any(kw in title_lower for kw in ["fullstack", "full stack", "full-stack"]):
        return "fullstack"

    # Frontend roles
    if any(kw in title_lower for kw in ["frontend", "front end", "front-end", "ui developer", "react developer"]):
        return "frontend"

    # Backend roles
    if any(kw in title_lower for kw in ["backend", "back end", "back-end", "api developer", "server"]):
        return "backend"

    return "other"


def get_all_skills_from_jd(jd_input: JDInput) -> List[str]:
    """
    Extract all unique skills from JD (skills + niceToHave + capabilities).
    """
    all_skills = set()

    # Add required skills
    all_skills.update(jd_input.details.skills)

    # Add nice-to-have skills
    if jd_input.details.niceToHave:
        all_skills.update(jd_input.details.niceToHave)

    # Add capabilities
    all_skills.update(jd_input.capabilities)

    return list(all_skills)


def format_jd_for_prompt(jd_input: JDInput) -> dict:
    """
    Format JD data for use in matching prompt.
    """
    return {
        "jd_title": jd_input.details.title,
        "jd_description": jd_input.details.description,
        "jd_skills": ", ".join(jd_input.details.skills),
        "jd_nice_to_have": ", ".join(jd_input.details.niceToHave) if jd_input.details.niceToHave else "None specified",
        "jd_responsibilities": "\n".join(f"- {r}" for r in jd_input.details.responsibilities)
    }
