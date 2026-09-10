"""
Fidelity gate — the "RelAi Race" (spec section 3).

A compression is never trusted on the compressor's own word. First a
deterministic diff checks that entities, numbers, dates, and meaning-bearing
operators survived — free, and it can only ever fall back toward more
information, never silently accept a loss. Only once that passes does an
*independent* scorer (never the model that produced the compression) get a
vote, and even then a low score falls back to raw text rather than shipping
something uncertain.

Semantic fidelity is a hard invariant, not a scoring hint: reconstructed
content may be shorter, but it cannot change polarity, authority, scope,
entity, quantity, or temporal meaning. The distiller and any compressor
must pass `semantic_diff` before a candidate is stored or dispatched.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

_ENTITY_RE = re.compile(r"\b[A-Z][a-zA-Z]{2,}\b")
_NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)*")
_DATE_RE = re.compile(
    r"\b\d{4}-\d{2}-\d{2}\b"
    r"|\b\d{1,2}/\d{1,2}/\d{2,4}\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?,?\s+\d{2,4}\b",
    re.I,
)
_TOKEN_RE = re.compile(r"[a-z0-9']+")

# Polarity family: substitution within the family is allowed (never ↔ not)
# as long as the *count* of polarity tokens does not drop, and we never
# introduce a negation into an affirmative. Sets are not enough — "never
# say never" collapsing to one "never" would otherwise look identical.
_NEGATION_WORDS = {
    "not", "never", "no", "none", "nobody", "nothing", "neither", "nor",
    "cannot", "can't", "won't", "don't", "doesn't", "didn't", "isn't",
    "aren't", "wasn't", "weren't", "mustn't", "shouldn't", "wouldn't",
    "couldn't", "without", "forbidden", "prohibited", "banned", "disallowed",
}
_AUTHORITY_WORDS = {
    "always", "must", "shall", "should", "required", "mandatory",
}
_PERMISSION_WORDS = {
    "may", "allowed", "permitted", "optional",
}
_SCOPE_WORDS = {
    "only", "except", "unless", "excluding", "solely", "exclusively",
}
_TEMPORAL_WORDS = {
    "after", "before", "until", "since", "during",
    "today", "tomorrow", "yesterday", "deadline",
}
_QUANTITY_WORDS = {
    "zero", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "dozen", "hundred", "thousand", "million",
}

# Fallback storage is for rules whose operators we might otherwise invert
# or forget. Chat words like "today" and bare numbers must not force us
# to store the whole utterance as a rule.
_FALLBACK_OPERATORS = (
    _NEGATION_WORDS | _AUTHORITY_WORDS | _PERMISSION_WORDS | _SCOPE_WORDS
)

# Capitalized operators are not people. Sentence-initial "Never" used to
# be counted as an entity, which hid lowercase never-drops and rejected
# legitimate never→not paraphrases.
_OPERATOR_LOWER = (
    _NEGATION_WORDS | _AUTHORITY_WORDS | _PERMISSION_WORDS | _SCOPE_WORDS | _TEMPORAL_WORDS
)

_DIMENSION_KEYS = (
    "entities", "numbers", "dates", "authority", "permission",
    "scope", "temporal", "quantities",
)


def _tokens(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _entity_counts(text: str) -> Counter:
    return Counter(
        e for e in _ENTITY_RE.findall(text) if e.lower() not in _OPERATOR_LOWER
    )


def _signals(text: str) -> Dict[str, Counter]:
    tokens = _tokens(text)
    counts = Counter(tokens)
    return {
        "entities": _entity_counts(text),
        "numbers": Counter(_NUMBER_RE.findall(text)),
        "dates": Counter(m.group(0).lower() for m in _DATE_RE.finditer(text)),
        "negations": Counter({w: counts[w] for w in _NEGATION_WORDS if counts[w]}),
        "authority": Counter({w: counts[w] for w in _AUTHORITY_WORDS if counts[w]}),
        "permission": Counter({w: counts[w] for w in _PERMISSION_WORDS if counts[w]}),
        "scope": Counter({w: counts[w] for w in _SCOPE_WORDS if counts[w]}),
        "temporal": Counter({w: counts[w] for w in _TEMPORAL_WORDS if counts[w]}),
        "quantities": Counter({w: counts[w] for w in _QUANTITY_WORDS if counts[w]}),
    }


def source_has_critical_operators(text: str) -> bool:
    """True when the source carries polarity/authority/permission/scope
    operators the invariant must not let disappear — even if no extractor
    pattern matched. Temporal words and bare numbers are checked when an
    atom exists; they do not by themselves justify storing the utterance."""
    return bool(set(_tokens(text)) & _FALLBACK_OPERATORS)


def polarity_of(text: str) -> bool:
    """True = asserts, False = negates. Any polarity-family token in the
    surface form makes the claim negative. Double negation is *not*
    interpreted: the object text is the source of truth, this bit is only
    the structured view used by dedup."""
    return sum(1 for t in _tokens(text) if t in _NEGATION_WORDS) == 0


@dataclass(frozen=True)
class FidelityDiff:
    ok: bool
    missing_from_candidate: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class SemanticDiff:
    """Hard semantic-fidelity verdict. `ok` means every meaning dimension
    in `original` survived into `candidate` (candidate may be shorter)."""
    ok: bool
    missing_from_candidate: List[str] = field(default_factory=list)
    dimensions: Dict[str, str] = field(default_factory=dict)


def semantic_diff(original: str, candidate: str) -> SemanticDiff:
    """Meaning-preservation invariant.

    Reconstructed content may drop filler. It may not:
      - drop a polarity operator instance (never/not/don't/…)
      - introduce a polarity operator into an affirmative
      - drop authority / permission / scope / temporal / quantity tokens
      - drop an entity, number, or date

    Polarity is compared as a *family count*, not a token set: "never" may
    become "not", but "never say never" (2) may not collapse to one "never".
    """
    o, c = _signals(original), _signals(candidate)
    missing: List[str] = []
    dimensions: Dict[str, str] = {}

    o_neg = sum(o["negations"].values())
    c_neg = sum(c["negations"].values())
    if o_neg == 0 and c_neg > 0:
        missing.append("negations:introduced")
        dimensions["polarity"] = "changed"
    elif o_neg > c_neg:
        missing.append("negations:dropped")
        dropped = o["negations"] - c["negations"]
        missing.extend(f"negations:{tok}" for tok in sorted(dropped))
        dimensions["polarity"] = "changed"
    else:
        dimensions["polarity"] = "preserved"

    for key in _DIMENSION_KEYS:
        dropped = o[key] - c[key]
        if dropped:
            missing.extend(f"{key}:{tok}" for tok in sorted(dropped))
            dimensions[key] = "changed"
        else:
            dimensions[key] = "preserved"

    return SemanticDiff(ok=not missing, missing_from_candidate=missing, dimensions=dimensions)


def deterministic_diff(original: str, candidate: str) -> FidelityDiff:
    """Every entity/number/date/operator in `original` must survive into
    `candidate`. This never checks the other direction — a candidate is
    allowed to drop filler, just not claims."""
    verdict = semantic_diff(original, candidate)
    return FidelityDiff(ok=verdict.ok, missing_from_candidate=verdict.missing_from_candidate)


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
