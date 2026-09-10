"""
Zero Atoms — the canonical semantic unit ZeroFold stores and reasons about.

An atom is the smallest fact-shaped thing worth keeping: a subject-predicate-
object claim, with enough provenance and metadata to judge whether it's true,
current, and worth its storage cost. Human-readable fields are an interface,
not a storage requirement — a future Zero Language encoding can pack the same
atom into a compact reference without changing this shape.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional

# ---- Bitpacked flags (frozen shape — see cns/schema.py) ----
FLAG_EXPLICIT_USER_RULE = 1 << 0
FLAG_CONFIRMED = 1 << 1
FLAG_HIGH_IMPORTANCE = 1 << 2
FLAG_SUPERSEDED = 1 << 3

# Surface operators that already mark a claim as negated. `render_claim`
# must not prefix another "not" on top of these or it reverses meaning —
# including when the operator is mid-clause ("You must not share…").
_NEGATION_TOKENS = {
    "never", "not", "no", "none", "neither", "nor", "don't", "doesn't",
    "didn't", "cannot", "can't", "won't", "mustn't", "shouldn't",
    "wouldn't", "couldn't", "isn't", "aren't", "wasn't", "weren't",
    "without", "forbidden", "prohibited", "banned", "disallowed",
}
_TOKEN_RE = re.compile(r"[a-z']+")


def has_flag(flags: int, flag: int) -> bool:
    return bool(flags & flag)


def set_flag(flags: int, flag: int) -> int:
    return flags | flag


def clear_flag(flags: int, flag: int) -> int:
    return flags & ~flag


def _norm(text: str) -> str:
    """Whitespace/case normalization used for hashing and fingerprinting.
    Not a display transform — callers keep the original-case fields."""
    return " ".join(text.split()).strip().lower()


@dataclass(frozen=True)
class SemanticAtom:
    """The canonical shape (spec section 6). Immutable — a change in meaning
    is a new atom that supersedes this one, never a mutation in place."""

    subject: str
    predicate: str
    object: str
    polarity: bool = True          # True = asserts, False = negates
    scope: str = "global"
    time: Optional[str] = None     # ISO timestamp or free-form temporal scope
    confidence: float = 1.0
    source_refs: List[str] = field(default_factory=list)
    flags: int = 0
    namespace: str = "default"

    def __post_init__(self) -> None:
        if not self.subject.strip() or not self.predicate.strip() or not self.object.strip():
            raise ValueError("subject, predicate, and object must be non-empty")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be in [0.0, 1.0]")

    def canonical_dict(self) -> dict:
        """Stable, order-independent representation used for hashing."""
        return {
            "subject": _norm(self.subject),
            "predicate": _norm(self.predicate),
            "object": _norm(self.object),
            "polarity": self.polarity,
            "scope": _norm(self.scope),
            "time": self.time,
            "namespace": self.namespace,
        }

    def fingerprint(self) -> str:
        """Identity ignoring polarity/object — groups atoms that talk about the
        same (subject, predicate, scope) so contradictions and duplicates are
        found as candidates, not accidentally treated as unrelated facts."""
        from zerofold.codec import stable_hash

        return stable_hash({
            "subject": _norm(self.subject),
            "predicate": _norm(self.predicate),
            "scope": _norm(self.scope),
            "namespace": self.namespace,
        })

    def object_id(self) -> str:
        """The full-identity hash — includes polarity/object, so a
        contradiction produces a *different* object_id than the fact it
        supersedes (spec section 6: 'two hashes')."""
        from zerofold.codec import stable_hash

        return stable_hash(self.canonical_dict())

    def with_flag(self, flag: int) -> "SemanticAtom":
        return SemanticAtom(**{**self.__dict__, "flags": set_flag(self.flags, flag)})


def render_claim(atom: SemanticAtom) -> str:
    """Canonical reconstruction of an atom into a claim string.

    The polarity bit is a structured field for dedup, not a second copy of
    the operator. If the object already carries a negation anywhere in the
    span ("Never use…", "You must not…"), we must not prefix another "not"
    — that reverses the stored rule. If polarity is False and the object
    has no operator, we MUST surface one, otherwise retrieval injects the
    opposite instruction.
    """
    pred = atom.predicate.replace("_", " ")
    obj = atom.object.strip()
    if atom.polarity is False:
        tokens = set(_TOKEN_RE.findall(obj.lower()))
        if not (tokens & _NEGATION_TOKENS):
            obj = f"not {obj}"
    return f"{atom.subject} {pred} {obj}"
