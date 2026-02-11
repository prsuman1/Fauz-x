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
    in_flight_count: int = 0
    first_in_flight_since: float = 0.0  # timestamp of oldest active request


class APIKeyManager:
    """Manages multiple OpenRouter API keys with smart routing and in-flight tracking."""

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

    async def acquire_key(self) -> str:
        """
        Smart 3-tier key selection:
          Tier 1: Idle + available (in_flight_count == 0). Round-robin among these.
          Tier 2: Busy but available. Pick lowest in_flight_count, ties broken by
                  oldest first_in_flight_since (busy longest = most likely to finish soon).
          Tier 3: All rate-limited. Wait for earliest recovery, then retry.
        """
        async with self._lock:
            self._clear_expired()

            # --- Tier 1: idle + available ---
            total = len(self._slots)
            start = self._current_index
            for i in range(total):
                idx = (start + i) % total
                slot = self._slots[idx]
                if slot.status == "available" and slot.in_flight_count == 0:
                    self._current_index = (idx + 1) % total
                    slot.request_count += 1
                    slot.in_flight_count += 1
                    slot.first_in_flight_since = time.time()
                    return slot.key

            # --- Tier 2: busy but available (lowest load) ---
            available = [s for s in self._slots if s.status == "available"]
            if available:
                # Sort by in_flight_count ASC, then first_in_flight_since ASC (oldest busy first)
                best = min(available, key=lambda s: (s.in_flight_count, s.first_in_flight_since))
                best.request_count += 1
                best.in_flight_count += 1
                if best.in_flight_count == 1:
                    best.first_in_flight_since = time.time()
                return best.key

            # --- Tier 3: all rate-limited — wait for earliest recovery ---
            earliest_slot = min(self._slots, key=lambda s: s.rate_limited_until)
            wait_seconds = earliest_slot.rate_limited_until - time.time()
            if wait_seconds > 0:
                capped_wait = min(wait_seconds, 10.0)
                print(f"[APIKeyManager] All keys rate-limited, waiting {capped_wait:.1f}s")
                self._lock.release()
                try:
                    await asyncio.sleep(capped_wait)
                finally:
                    await self._lock.acquire()
                self._clear_expired()

            # Try again after waiting — pick any available
            for i in range(total):
                idx = (self._current_index + i) % total
                slot = self._slots[idx]
                if slot.status == "available":
                    self._current_index = (idx + 1) % total
                    slot.request_count += 1
                    slot.in_flight_count += 1
                    if slot.in_flight_count == 1:
                        slot.first_in_flight_since = time.time()
                    return slot.key

            # Still nothing — force the earliest-recovering key
            earliest_slot.status = "available"
            earliest_slot.rate_limited_until = 0.0
            earliest_slot.request_count += 1
            earliest_slot.in_flight_count += 1
            earliest_slot.first_in_flight_since = time.time()
            return earliest_slot.key

    async def release_key(self, key: str) -> None:
        """Decrement in-flight count for a key. Reset timestamp when count hits 0."""
        async with self._lock:
            for slot in self._slots:
                if slot.key == key:
                    slot.in_flight_count = max(0, slot.in_flight_count - 1)
                    if slot.in_flight_count == 0:
                        slot.first_in_flight_since = 0.0
                    return

    async def get_next_key(self) -> str:
        """Backward-compatible alias for acquire_key()."""
        return await self.acquire_key()

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
        """Return status of all keys (with masked values) including in-flight info."""
        self._clear_expired()
        now = time.time()
        result = []
        for i, slot in enumerate(self._slots):
            cooldown_remaining = max(0, slot.rate_limited_until - now) if slot.status == "rate_limited" else 0
            in_flight_duration = round(now - slot.first_in_flight_since, 1) if slot.in_flight_count > 0 else 0
            result.append({
                "index": i,
                "key_hint": f"...{slot.key[-6:]}",
                "status": slot.status,
                "cooldown_remaining_s": round(cooldown_remaining, 1),
                "request_count": slot.request_count,
                "in_flight_count": slot.in_flight_count,
                "in_flight_duration_s": in_flight_duration,
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
