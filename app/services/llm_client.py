import json
import re
import httpx
from typing import Optional, Dict, Any

from app.config import (
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    API_TIMEOUT_SECONDS,
)


class LLMClient:
    """OpenRouter API client for LLM calls."""

    def __init__(self):
        self.api_key = OPENROUTER_API_KEY
        self.base_url = OPENROUTER_BASE_URL
        self.default_model = DEFAULT_MODEL
        self.fallback_model = FALLBACK_MODEL
        self.timeout = API_TIMEOUT_SECONDS

        if not self.api_key:
            raise ValueError("OPENROUTER_API_KEY not set in environment variables")

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://faujx.com",
            "X-Title": "FaujX JD-CV Matcher",
        }

    async def chat_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 4096,
    ) -> str:
        """
        Make a chat completion request to OpenRouter.

        Args:
            system_prompt: System message for the LLM
            user_prompt: User message for the LLM
            model: Model to use (defaults to DEFAULT_MODEL)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response

        Returns:
            The LLM response text
        """
        model = model or self.default_model

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()

                data = response.json()
                return data["choices"][0]["message"]["content"]

            except httpx.HTTPStatusError as e:
                # Try fallback model if primary fails
                if model != self.fallback_model:
                    print(f"Primary model failed ({e}), trying fallback...")
                    return await self.chat_completion(
                        system_prompt=system_prompt,
                        user_prompt=user_prompt,
                        model=self.fallback_model,
                        temperature=temperature,
                        max_tokens=max_tokens,
                    )
                raise

            except Exception as e:
                raise RuntimeError(f"LLM API call failed: {str(e)}")

    async def get_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Make a chat completion request and parse the response as JSON.

        Returns:
            Parsed JSON response as a dictionary
        """
        response_text = await self.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model=model,
            max_tokens=max_tokens,
        )

        # Clean response - remove markdown code blocks if present
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Sanitize JSON - remove invalid control characters
        # Remove control characters except newline, tab, carriage return
        cleaned = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', cleaned)

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to extract JSON object from the response
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                try:
                    extracted = json_match.group()
                    extracted = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', extracted)
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    pass

            # Try array format
            array_match = re.search(r'\[[\s\S]*\]', cleaned)
            if array_match:
                try:
                    extracted = array_match.group()
                    extracted = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', extracted)
                    return json.loads(extracted)
                except json.JSONDecodeError:
                    pass

            # Last resort: try to fix common JSON issues
            try:
                # Replace unescaped newlines in strings
                fixed = re.sub(r'(?<!\\)\n', '\\n', cleaned)
                return json.loads(fixed)
            except json.JSONDecodeError:
                pass

            raise ValueError(f"Failed to parse JSON from LLM response: {e}\nResponse: {response_text[:500]}")


# Singleton instance
_llm_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """Get or create the LLM client singleton."""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
