"""
Complexity floor — the minimum-capability estimate a router can use to pick
the cheapest model that can still do the job (spec section 4).

ZeroFold does not route requests itself (that's SubtracToken's job); it
produces a `min_quality_tier` on the same 1/2/3 scale most model catalogs
already use (1 = cheap/small, 2 = mid, 3 = premium) so a router can filter
its candidate pool before ranking by price.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

_INTENT_WEIGHT = {
    "code": 0.6,
    "longform": 0.5,
    "qa": 0.3,
    "summary": 0.2,
    "extraction": 0.2,
    "classification": 0.15,
    "chat": 0.15,
}

_LARGE_CONTEXT_TOKENS = 4000
_LARGE_CONTEXT_BONUS = 0.2
_RISK_FLAG_WEIGHT = 0.25
_MAX_RISK_BONUS = 0.5


@dataclass(frozen=True)
class ComplexityInputs:
    intent: str = "chat"
    context_tokens: int = 0
    risk_flags: Sequence[str] = field(default_factory=tuple)


def complexity_score(inputs: ComplexityInputs) -> float:
    score = _INTENT_WEIGHT.get(inputs.intent, _INTENT_WEIGHT["chat"])
    if inputs.context_tokens > _LARGE_CONTEXT_TOKENS:
        score += _LARGE_CONTEXT_BONUS
    score += min(_MAX_RISK_BONUS, _RISK_FLAG_WEIGHT * len(inputs.risk_flags))
    return min(1.0, score)


def min_quality_tier(score: float) -> int:
    """Maps a 0..1 complexity score to a 1/2/3 model quality tier floor."""
    if score >= 0.6:
        return 3
    if score >= 0.3:
        return 2
    return 1
