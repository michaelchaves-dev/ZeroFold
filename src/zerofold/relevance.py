"""
Relevance gate — deterministic, no model call (spec section 5).

Decides whether a piece of conversation is worth the distiller's attention
before anything gets extracted. Pleasantries, acknowledgements, and
dead-end retries are discarded for free; anything with a durable-sounding
signal is kept. This errs toward keeping when unsure, per the standing
invariant: preserve more information under ambiguity rather than guess.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

_DISCARD_PHRASES = {
    "ok", "okay", "thanks", "thank you", "thanks!", "sounds good", "got it",
    "cool", "great", "np", "no problem", "sure", "yep", "yeah", "yes", "no",
    "hi", "hello", "hey", "bye", "goodbye", "np thanks", "will do", "perfect",
}

_RETRY_MARKERS = (
    "nevermind", "never mind", "ignore that", "scratch that", "forget it",
    "disregard that", "disregard the above",
)

_KEEP_MARKERS = (
    "always", "never", "must", "should", "remember that", "remember,",
    "note that", "my name is", "i am ", "i'm ", "i prefer", "i like",
    "i don't like", "i dislike", "we decided", "let's go with",
    "the plan is", "the deadline is", "budget is", "must not",
    "cannot exceed", "can't exceed", "rule:", "constraint:", "decision:",
)

_DIRECTIVE_START = re.compile(
    r"^(?:(?:for|in) code reviews?,\s*|(?:for )?(?:this answer|this response|this turn) only,\s*)?"
    r"(?:use|include|keep|answer|write|respond|avoid|ignore|explain)\b",
    re.I,
)
_HAS_DIGIT_OR_AT = re.compile(r"\d|@")


@dataclass(frozen=True)
class RelevanceDecision:
    keep: bool
    reason: str
    signals: List[str] = field(default_factory=list)


def evaluate(text: str) -> RelevanceDecision:
    norm = text.strip().lower()
    if not norm:
        return RelevanceDecision(False, "empty")

    if any(marker in norm for marker in _RETRY_MARKERS):
        return RelevanceDecision(False, "retry_or_dead_end")

    if norm.strip(" .!?") in _DISCARD_PHRASES:
        return RelevanceDecision(False, "pleasantry")

    if _DIRECTIVE_START.search(norm):
        return RelevanceDecision(True, "explicit_directive", ["directive"])

    signals = [m for m in _KEEP_MARKERS if m in norm]
    if signals:
        return RelevanceDecision(True, "durable_signal", signals)

    word_count = len(norm.split())
    if word_count <= 2 and not _HAS_DIGIT_OR_AT.search(norm):
        return RelevanceDecision(False, "too_short")

    if _HAS_DIGIT_OR_AT.search(norm):
        return RelevanceDecision(True, "contains_data", ["number_or_contact"])

    # Long enough to plausibly state something durable even without a
    # keyword hit — keep conservatively rather than silently drop it.
    if word_count >= 8:
        return RelevanceDecision(True, "long_enough_uncertain")

    return RelevanceDecision(False, "no_durable_signal")


def filter_relevant(messages: List[dict]) -> List[dict]:
    """Keep only messages whose content clears the relevance gate."""
    return [m for m in messages if evaluate(m.get("content", "")).keep]
