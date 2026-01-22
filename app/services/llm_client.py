import json
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

        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            # Try to extract JSON from the response
            import re
            json_match = re.search(r'\{[\s\S]*\}', cleaned)
            if json_match:
                try:
                    return json.loads(json_match.group())
                except json.JSONDecodeError:
                    pass

            # Try array format
            array_match = re.search(r'\[[\s\S]*\]', cleaned)
            if array_match:
                try:
                    return json.loads(array_match.group())
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
