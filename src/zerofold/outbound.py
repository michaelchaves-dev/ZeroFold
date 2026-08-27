"""
Outbound Supervisor — post-response validation against the output contract
(spec section 15).

On failure, the spec calls for "targeted delta correction only... do not
regenerate the entire answer when one local defect can be repaired." This
module reports exactly which check(s) failed (`OutboundViolation.code` is
meant to be fed straight into a corrective prompt, e.g.
`FIX:repetition`), but it does not itself call a model to regenerate
anything — same provider-agnostic boundary as the rest of ZeroFold.

Violations are split into `blocking` and informational. `budget_exceeded`
and `unsupported_claim` are surfaced but non-blocking: token overshoot is
often tolerable and the unsupported-claim heuristic is too coarse to justify
a hard failure on its own.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import List

from zerofold.contracts import OutputContract
from zerofold.tokens import estimate_tokens

_COMPLETION_ENDINGS = ".!?\"')]}"

_UNSUPPORTED_CLAIM_MARKERS = (
    "studies show", "it is proven", "guaranteed", "100% effective",
    "always works", "never fails", "scientifically proven",
)
_EVIDENCE_MARKERS = ("according to", "source:", "http://", "https://", "citation")


@dataclass(frozen=True)
class OutboundViolation:
    code: str
    detail: str
    blocking: bool


@dataclass(frozen=True)
class OutboundResult:
    passed: bool
    violations: List[OutboundViolation] = field(default_factory=list)


class OutboundSupervisor:
    def __init__(
        self,
        *,
        repetition_ratio_threshold: float = 0.3,
        token_budget_slack: float = 1.15,
        shingle_size: int = 5,
    ) -> None:
        self.repetition_ratio_threshold = repetition_ratio_threshold
        self.token_budget_slack = token_budget_slack
        self.shingle_size = shingle_size

    def _repetition_ratio(self, text: str) -> float:
        words = text.lower().split()
        if len(words) < self.shingle_size * 2:
            return 0.0
        shingles = [
            tuple(words[i : i + self.shingle_size])
            for i in range(len(words) - self.shingle_size + 1)
        ]
        if not shingles:
            return 0.0
        return 1.0 - (len(set(shingles)) / len(shingles))

    def _has_unsupported_claim(self, text: str) -> bool:
        lower = text.lower()
        has_marker = any(m in lower for m in _UNSUPPORTED_CLAIM_MARKERS)
        has_evidence = any(e in lower for e in _EVIDENCE_MARKERS)
        return has_marker and not has_evidence

    def validate(self, text: str, contract: OutputContract) -> OutboundResult:
        stripped = text.strip()
        violations: List[OutboundViolation] = []

        if not stripped:
            return OutboundResult(False, [OutboundViolation("empty", "response is empty", True)])

        tokens = estimate_tokens(stripped)

        if stripped[-1] not in _COMPLETION_ENDINGS and tokens >= contract.max_tokens * 0.9:
            violations.append(OutboundViolation(
                "incomplete",
                "response ends without terminal punctuation near the token budget",
                True,
            ))

        ratio = self._repetition_ratio(stripped)
        if ratio > self.repetition_ratio_threshold:
            violations.append(OutboundViolation(
                "repetition", f"{ratio:.0%} of {self.shingle_size}-word shingles repeat", True
            ))

        if contract.format == "json":
            try:
                json.loads(stripped)
            except (json.JSONDecodeError, ValueError):
                violations.append(OutboundViolation(
                    "format_mismatch", "response is not valid JSON as the contract requires", True
                ))

        if tokens > contract.max_tokens * self.token_budget_slack:
            violations.append(OutboundViolation(
                "budget_exceeded",
                f"~{tokens} tokens exceeds max_tokens={contract.max_tokens} contract",
                False,
            ))

        if contract.evidence == "required" and self._has_unsupported_claim(stripped):
            violations.append(OutboundViolation(
                "unsupported_claim", "absolute claim without cited evidence", False
            ))

        passed = not any(v.blocking for v in violations)
        return OutboundResult(passed, violations)
