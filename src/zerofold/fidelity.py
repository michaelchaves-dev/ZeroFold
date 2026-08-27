"""
Fidelity gate — the "RelAi Race" (spec section 3).

A compression is never trusted on the compressor's own word. First a
deterministic diff checks that entities, numbers, dates, and negations
survived — free, and it can only ever fall back toward more information,
never silently accept a loss. Only once that passes does an *independent*
scorer (never the model that produced the compression) get a vote, and even
then a low score falls back to raw text rather than shipping something
uncertain. This module is not a code-comment restating the pseudocode: it
implements the flow exactly as specced.

`independent_scorer` and `recompress_fn` are both optional injected
callables so this module never depends on any particular model or provider.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

_ENTITY_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b",
    re.I,
)
_NEGATION_WORDS = {
    "not", "never", "no", "cannot", "can't", "won't", "don't", "doesn't",
    "didn't", "isn't", "aren't", "wasn't", "weren't", "none", "nobody",
}


def _signals(text: str) -> dict:
    tokens = set(re.findall(r"[a-z']+", text.lower()))
    return {
        "entities": set(_ENTITY_RE.findall(text)),
        "numbers": set(_NUMBER_RE.findall(text)),
        "dates": {m.group(0).lower() for m in _DATE_RE.finditer(text)},
        "negations": tokens & _NEGATION_WORDS,
    }


@dataclass(frozen=True)
class FidelityDiff:
    ok: bool
    missing_from_candidate: List[str] = field(default_factory=list)


def deterministic_diff(original: str, candidate: str) -> FidelityDiff:
    """Every entity/number/date/negation in `original` must survive into
    `candidate`. This never checks the other direction — a candidate is
    allowed to drop filler, just not claims."""
    o, c = _signals(original), _signals(candidate)
    missing: List[str] = []
    for key in ("entities", "numbers", "dates", "negations"):
        missing.extend(f"{key}:{v}" for v in sorted(o[key] - c[key]))
    return FidelityDiff(ok=not missing, missing_from_candidate=missing)


@dataclass(frozen=True)
class FidelityResult:
    dispatch_text: str
    used_compressed: bool
    diff: FidelityDiff
    score: Optional[float] = None
    attempts: int = 0


IndependentScorer = Callable[[str, str], float]
RecompressFn = Callable[[str, List[str]], str]


class FidelityGate:
    def __init__(self, *, threshold: float = 0.8, max_retries: int = 1) -> None:
        self.threshold = threshold
        self.max_retries = max_retries

    def evaluate(
        self,
        raw: str,
        compressed: str,
        *,
        independent_scorer: Optional[IndependentScorer] = None,
        recompress_fn: Optional[RecompressFn] = None,
    ) -> FidelityResult:
        candidate = compressed
        attempts = 0

        while True:
            diff = deterministic_diff(raw, candidate)
            if not diff.ok:
                if recompress_fn is not None and attempts < self.max_retries:
                    attempts += 1
                    candidate = recompress_fn(raw, diff.missing_from_candidate)
                    continue
                return FidelityResult(raw, False, diff, None, attempts)

            if independent_scorer is None:
                return FidelityResult(candidate, True, diff, None, attempts)

            score = independent_scorer(raw, candidate)
            if score >= self.threshold:
                return FidelityResult(candidate, True, diff, score, attempts)

            if recompress_fn is not None and attempts < self.max_retries:
                attempts += 1
                candidate = recompress_fn(raw, [f"low_fidelity_score:{score:.2f}"])
                continue

            return FidelityResult(raw, False, diff, score, attempts)
