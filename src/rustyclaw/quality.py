"""Degraded response detection with 4 heuristics."""
from __future__ import annotations

from enum import Enum


class DegradedReason(str, Enum):
    """Reason a response is considered degraded."""

    EMPTY_CONTENT = "empty_content"
    KNOWN_ERROR_PHRASE = "known_error_phrase"
    REPETITIVE_LOOP = "repetitive_loop"
    TRUNCATED_MID_WORD = "truncated_mid_word"


_ERROR_PHRASES = [
    "i cannot",
    "as an ai",
    "i'm sorry, but i",
]


def check_degraded(content: str) -> DegradedReason | None:
    """Check if response content is degraded. Returns reason or None if OK."""
    # 1. Empty/whitespace
    if not content or not content.strip():
        return DegradedReason.EMPTY_CONTENT

    # 2. Known error phrases (case-insensitive)
    lower = content.lower()
    for phrase in _ERROR_PHRASES:
        if phrase in lower:
            return DegradedReason.KNOWN_ERROR_PHRASE

    # 3. Repetitive 3-word phrases (any trigram appears 5+ times)
    words = content.split()
    if len(words) >= 15:
        trigram_counts: dict[str, int] = {}
        for i in range(len(words) - 2):
            trigram = f"{words[i]} {words[i + 1]} {words[i + 2]}"
            trigram_counts[trigram] = trigram_counts.get(trigram, 0) + 1
            if trigram_counts[trigram] >= 5:
                return DegradedReason.REPETITIVE_LOOP

    # 4. Truncated mid-word (>100 chars, ends with alphanumeric)
    if len(content) > 100 and content[-1].isalnum():
        return DegradedReason.TRUNCATED_MID_WORD

    return None
