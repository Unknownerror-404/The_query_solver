"""Small anti-spam policies for the civic-map prototype.

This module is intentionally storage-independent. Production deployments should
move counters and fingerprints to Redis or the database so limits work across
multiple server processes.
"""

from __future__ import annotations

import hashlib
import re
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SpamDecision:
    allowed: bool
    message: str = ""


class SpamGuard:
    """Rate-limit actions and reject obvious low-effort automated submissions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._actions: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self._fingerprints: dict[str, deque[tuple[float, str]]] = defaultdict(deque)

    def check_submission(self, user: str, source: str, payload: dict[str, Any], kind: str) -> SpamDecision:
        title = str(payload.get("title", "")).strip()
        description = str(payload.get("description", "")).strip()
        if len(title) < 4 or len(description) < 10:
            return SpamDecision(False, "Please provide a meaningful title and description.")
        combined = f"{title} {description}"
        if _has_control_characters(combined):
            return SpamDecision(False, "The submission contains unsupported characters.")
        if _link_count(combined) > 2:
            return SpamDecision(False, "Please remove excessive links from the submission.")
        if _repeated_character_ratio(combined) > 0.55:
            return SpamDecision(False, "The submission appears to contain repeated filler text.")
        identity = user or source
        rate = self._rate_limit(identity, kind, limit=3 if kind == "issue" else 5, window_seconds=300)
        if not rate.allowed:
            return rate
        fingerprint = hashlib.sha256(_normalise(combined).encode("utf-8")).hexdigest()
        with self._lock:
            recent = self._fingerprints[kind]
            now = time.monotonic()
            while recent and now - recent[0][0] > 3600:
                recent.popleft()
            if any(existing == fingerprint for _, existing in recent):
                return SpamDecision(False, "A very similar submission was recently received.")
            recent.append((now, fingerprint))
        return SpamDecision(True)

    def check_action(self, user: str, source: str, kind: str) -> SpamDecision:
        return self._rate_limit(user or source, kind, limit=20, window_seconds=60)

    def _rate_limit(self, identity: str, kind: str, limit: int, window_seconds: int) -> SpamDecision:
        now = time.monotonic()
        with self._lock:
            actions = self._actions[(identity, kind)]
            while actions and now - actions[0] > window_seconds:
                actions.popleft()
            if len(actions) >= limit:
                return SpamDecision(False, "Too many requests. Please wait before trying again.")
            actions.append(now)
        return SpamDecision(True)


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def _has_control_characters(value: str) -> bool:
    return any(ord(character) < 32 and character not in "\n\r\t" for character in value)


def _link_count(value: str) -> int:
    return len(re.findall(r"(?:https?://|www\.)\S+", value.casefold()))


def _repeated_character_ratio(value: str) -> float:
    letters = [character.casefold() for character in value if not character.isspace()]
    if len(letters) < 12:
        return 0.0
    repeated = sum(first == second == third for first, second, third in zip(letters, letters[1:], letters[2:]))
    return repeated / max(1, len(letters) - 2)


SPAM_GUARD = SpamGuard()
