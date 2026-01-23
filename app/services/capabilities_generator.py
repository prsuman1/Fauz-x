"""
Service for generating capabilities from JD Details using LLM.
"""
import json
from typing import Dict, Any, List

from app.models.schemas import JDDetailsForCapabilities
from app.prompts import CAPABILITIES_SYSTEM_PROMPT, CAPABILITIES_USER_PROMPT
from app.services.llm_client import get_llm_client


class CapabilitiesGenerator:
    """Service for generating capabilities from JD Details."""

    def __init__(self):
        self.llm_client = get_llm_client()

    async def generate_capabilities(
        self, jd_details: JDDetailsForCapabilities
    ) -> Dict[str, Any]:
        """
        Generate capabilities from JD Details.

        Args:
            jd_details: JD Details without capabilities

        Returns:
            Dict with role_type and capabilities list
        """
        # Build the user prompt
        user_prompt = CAPABILITIES_USER_PROMPT.format(
            title=jd_details.title,
            skills=", ".join(jd_details.skills),
            nice_to_have=", ".join(jd_details.niceToHave or []) or "None specified",
            description=jd_details.description or "Not provided",
            responsibilities=", ".join(jd_details.responsibilities or []) or "Not specified",
        )

        # Get LLM response
        response = await self.llm_client.get_json_response(
            system_prompt=CAPABILITIES_SYSTEM_PROMPT,
            user_prompt=user_prompt,
        )

        # Parse and validate the response
        return self._parse_capabilities_response(response, jd_details.title)

    def _parse_capabilities_response(
        self, response: Dict[str, Any], jd_title: str
    ) -> Dict[str, Any]:
        """Parse the LLM response into capabilities data."""

        # Extract role type
        role_type = response.get("role_type", "other")

        # Extract capabilities
        capabilities = response.get("capabilities", [])

        # Ensure capabilities is a list
        if not isinstance(capabilities, list):
            capabilities = []

        # Clean up capabilities (remove empty strings, duplicates)
        capabilities = list(dict.fromkeys([
            cap.strip() for cap in capabilities
            if cap and isinstance(cap, str) and cap.strip()
        ]))

        return {
            "jd_title": jd_title,
            "role_type": role_type,
            "capabilities": capabilities,
        }


# Singleton instance
_capabilities_generator = None


def get_capabilities_generator() -> CapabilitiesGenerator:
    """Get or create the CapabilitiesGenerator singleton."""
    global _capabilities_generator
    if _capabilities_generator is None:
        _capabilities_generator = CapabilitiesGenerator()
    return _capabilities_generator
