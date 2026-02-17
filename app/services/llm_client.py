import json
import re
import time
import httpx
from datetime import datetime, timezone
from typing import Optional, Dict, Any

from app.config import (
    OPENROUTER_API_KEYS,
    OPENROUTER_BASE_URL,
    DEFAULT_MODEL,
    FALLBACK_MODEL,
    API_TIMEOUT_SECONDS,
)
from app.services.api_key_manager import get_api_key_manager


async def _log_key_usage(api_key: str, started: float, status_code: Optional[int], model: Optional[str], endpoint: Optional[str] = None) -> None:
    """Fire-and-forget: DB insert for key usage. Non-blocking, failures silently dropped."""
    try:
        from app.db import get_db_pool
        from app.db.key_usage_queries import insert_key_usage

        finished = time.time()
        duration = finished - started
        key_hint = f"...{api_key[-6:]}"
        started_dt = datetime.fromtimestamp(started, tz=timezone.utc)
        finished_dt = datetime.fromtimestamp(finished, tz=timezone.utc)

        pool = await get_db_pool()
        await insert_key_usage(
            pool=pool,
            key_hint=key_hint,
            started_at=started_dt,
            finished_at=finished_dt,
            duration_s=round(duration, 3),
            status_code=status_code,
            model=model,
            endpoint=endpoint,
        )
    except Exception:
        pass  # silently drop — DB logging must never break LLM calls


class LLMClient:
    """OpenRouter API client for LLM calls with multi-key rotation."""

    def __init__(self):
        self.key_manager = get_api_key_manager()
        self.base_url = OPENROUTER_BASE_URL
        self.default_model = DEFAULT_MODEL
        self.fallback_model = FALLBACK_MODEL
        self.timeout = API_TIMEOUT_SECONDS

        if not OPENROUTER_API_KEYS:
            raise ValueError("No OPENROUTER_API_KEY* set in environment variables")

    def _get_headers(self, api_key: str) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {api_key}",
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
        endpoint: Optional[str] = None,
    ) -> str:
        """
        Make a chat completion request to OpenRouter.
        Uses acquire/release for in-flight tracking.
        Rotates API keys on 429 rate-limit errors.
        """
        model = model or self.default_model
        total_keys = len(OPENROUTER_API_KEYS)

        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        # Disable thinking/reasoning for Gemini models to reduce latency
        if model and "gemini" in model.lower():
            payload["reasoning"] = {"effort": "none"}

        last_error = None

        for attempt in range(total_keys + 1):
            api_key = await self.key_manager.acquire_key()
            masked = f"...{api_key[-6:]}"
            started = time.time()
            status_code = None

            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    try:
                        response = await client.post(
                            f"{self.base_url}/chat/completions",
                            headers=self._get_headers(api_key),
                            json=payload,
                        )
                        status_code = response.status_code

                        if response.status_code == 429:
                            self.key_manager.mark_rate_limited(api_key)
                            print(f"[LLMClient] 429 on key {masked}, attempt {attempt + 1}/{total_keys + 1}")
                            last_error = f"429 Rate Limited (key {masked})"
                            continue

                        response.raise_for_status()
                        data = response.json()
                        return data["choices"][0]["message"]["content"]

                    except httpx.HTTPStatusError as e:
                        status_code = e.response.status_code
                        if e.response.status_code == 429:
                            self.key_manager.mark_rate_limited(api_key)
                            print(f"[LLMClient] 429 on key {masked}, attempt {attempt + 1}/{total_keys + 1}")
                            last_error = f"429 Rate Limited (key {masked})"
                            continue

                        # Non-429 error: try fallback model
                        if model != self.fallback_model:
                            print(f"[LLMClient] Primary model failed (HTTP {e.response.status_code}), trying fallback...")
                            return await self.chat_completion(
                                system_prompt=system_prompt,
                                user_prompt=user_prompt,
                                model=self.fallback_model,
                                temperature=temperature,
                                max_tokens=max_tokens,
                                endpoint=endpoint,
                            )
                        raise

                    except httpx.TimeoutException:
                        print(f"[LLMClient] Timeout on key {masked}, attempt {attempt + 1}/{total_keys + 1}")
                        last_error = f"Timeout after {self.timeout}s (key {masked})"
                        continue

                    except Exception as e:
                        err_msg = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                        raise RuntimeError(f"LLM API call failed: {err_msg}")

            finally:
                await self.key_manager.release_key(api_key)
                await _log_key_usage(api_key, started, status_code, model, endpoint)

        # All retries exhausted — try fallback model if we haven't already
        if model != self.fallback_model:
            print(f"[LLMClient] All keys exhausted ({last_error}), trying fallback model...")
            return await self.chat_completion(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=self.fallback_model,
                temperature=temperature,
                max_tokens=max_tokens,
                endpoint=endpoint,
            )
        raise RuntimeError(f"All {total_keys} API keys exhausted. Last error: {last_error}")

    async def get_json_response(
        self,
        system_prompt: str,
        user_prompt: str,
        model: Optional[str] = None,
        max_tokens: int = 4096,
        endpoint: Optional[str] = None,
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
            endpoint=endpoint,
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
