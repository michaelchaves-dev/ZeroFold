"""
Output contract — what the outbound validator checks a response against
(spec section 16). The point is to prevent unnecessary tokens from being
generated in the first place, not to generate a bloated answer and compress
it after the fact.
"""

from __future__ import annotations

from dataclasses import dataclass

_LOW_EVIDENCE_INTENTS = {"classification", "extraction", "code"}


@dataclass(frozen=True)
class OutputContract:
    detail: int = 2
    repeat: int = 0
    preface: int = 0
    evidence: str = "required"   # "required" | "optional"
    max_tokens: int = 800
    format: str = "text"         # "text" | "json"


def contract_from_intent(
    intent: str, recommended_max_tokens: int, *, format: str = "text"
) -> OutputContract:
    evidence = "optional" if intent in _LOW_EVIDENCE_INTENTS else "required"
    return OutputContract(
        evidence=evidence,
        max_tokens=max(1, recommended_max_tokens),
        format=format,
    )
