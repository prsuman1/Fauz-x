import asyncio
import time
from dataclasses import dataclass, field
from typing import List, Optional

from app.config import OPENROUTER_API_KEYS, API_KEY_COOLDOWN_SECONDS


@dataclass
class KeySlot:
    key: str
    status: str = "available"  # "available" | "rate_limited"
    rate_limited_until: float = 0.0
    request_count: int = 0


class APIKeyManager:
    """Manages multiple OpenRouter API keys with round-robin rotation and 429 failover."""

    _instance: Optional["APIKeyManager"] = None

    def __init__(self, keys: List[str], cooldown: int = 60):
        if not keys:
            raise ValueError("At least one API key is required")
        self._slots = [KeySlot(key=k) for k in keys]
        self._current_index = 0
        self._cooldown = cooldown
        self._lock = asyncio.Lock()
        print(f"[APIKeyManager] Loaded {len(self._slots)} API key(s), cooldown={cooldown}s")

    def _clear_expired(self) -> None:
        """Reset keys whose cooldown has expired."""
        now = time.time()
        for slot in self._slots:
            if slot.status == "rate_limited" and now >= slot.rate_limited_until:
                slot.status = "available"
                slot.rate_limited_until = 0.0

    async def get_next_key(self) -> str:
        """Return the next available key using round-robin. Clears expired cooldowns first."""
        async with self._lock:
            self._clear_expired()

            total = len(self._slots)
            for _ in range(total):
                slot = self._slots[self._current_index]
                self._current_index = (self._current_index + 1) % total
                if slot.status == "available":
                    slot.request_count += 1
                    return slot.key

            # All keys rate-limited — find the one that recovers soonest
            earliest_slot = min(self._slots, key=lambda s: s.rate_limited_until)
            wait_seconds = earliest_slot.rate_limited_until - time.time()
            if wait_seconds > 0:
                capped_wait = min(wait_seconds, 10.0)
                print(f"[APIKeyManager] All keys rate-limited, waiting {capped_wait:.1f}s")
                # Release lock while waiting
                self._lock.release()
                try:
                    await asyncio.sleep(capped_wait)
                finally:
                    await self._lock.acquire()
                self._clear_expired()

            # Try again after waiting
            for _ in range(total):
                slot = self._slots[self._current_index]
                self._current_index = (self._current_index + 1) % total
                if slot.status == "available":
                    slot.request_count += 1
                    return slot.key

            # Still nothing — return the earliest-recovering key anyway
            earliest_slot.status = "available"
            earliest_slot.rate_limited_until = 0.0
            earliest_slot.request_count += 1
            return earliest_slot.key

    def mark_rate_limited(self, key: str) -> None:
        """Mark a key as rate-limited with cooldown."""
        for slot in self._slots:
            if slot.key == key:
                slot.status = "rate_limited"
                slot.rate_limited_until = time.time() + self._cooldown
                masked = f"...{key[-6:]}"
                print(f"[APIKeyManager] Key {masked} rate-limited for {self._cooldown}s")
                return

    def get_status(self) -> List[dict]:
        """Return status of all keys (with masked values)."""
        self._clear_expired()
        now = time.time()
        result = []
        for i, slot in enumerate(self._slots):
            cooldown_remaining = max(0, slot.rate_limited_until - now) if slot.status == "rate_limited" else 0
            result.append({
                "index": i,
                "key_hint": f"...{slot.key[-6:]}",
                "status": slot.status,
                "cooldown_remaining_s": round(cooldown_remaining, 1),
                "request_count": slot.request_count,
            })
        return result


def get_api_key_manager() -> APIKeyManager:
    """Get or create the APIKeyManager singleton."""
    if APIKeyManager._instance is None:
        APIKeyManager._instance = APIKeyManager(
            keys=OPENROUTER_API_KEYS,
            cooldown=API_KEY_COOLDOWN_SECONDS,
        )
    return APIKeyManager._instance
