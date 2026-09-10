"""
The dedicated Step Zero Distiller (spec section 5).

Deterministic, pattern-based extraction of facts / decisions / commitments /
constraints from already-relevant text. No model call — this is the "free
deterministic work before paid inference" conservation law applied to
memory production. Because every atom's `object` text is a direct
regex-captured substring of the source, distillation cannot introduce a
claim the source didn't make; that's what stands in for the "deterministic
fidelity check" step in the conveyor diagram at this stage.

This is intentionally a floor, not a ceiling: a host that wants richer
extraction can pass its own `atoms` list straight to `dedup`/`Ledger`
instead of calling this module at all, or layer an LLM-backed distiller in
front of it and merge results.
"""

from __future__ import annotations

import re
from typing import List, Optional

from zerofold.atoms import FLAG_EXPLICIT_USER_RULE, FLAG_HIGH_IMPORTANCE, SemanticAtom
from zerofold.codec import source_hash
from zerofold.relevance import evaluate as relevance_evaluate

_MAX_CLAUSE = 120

_NAME_RE = re.compile(r"\bmy name is ([A-Za-z][\w \-']{1,40})", re.I)

_PREF_POS_RE = re.compile(r"\bi (?:prefer|like|love) ([^.!?\n]{2,%d})" % _MAX_CLAUSE, re.I)
_PREF_NEG_RE = re.compile(
    r"\bi (?:don'?t|do not|dislike|hate) (?:like )?([^.!?\n]{2,%d})" % _MAX_CLAUSE, re.I
)

_RULE_RE = re.compile(
    r"\b(always|never|must|should) ([^.!?\n]{2,%d})" % _MAX_CLAUSE, re.I
)

_SCOPED_DIRECTIVE_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+)for code reviews?,\s*"
    r"(use|include|keep|answer|write|respond|avoid|ignore|explain)\s+"
    r"([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)
_DIRECTIVE_RE = re.compile(
    r"(?:^|(?<=[.!?])\s+)"
    r"(use|include|keep|answer|write|respond|avoid|ignore|explain)\s+"
    r"([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)

_DECISION_RE = re.compile(
    r"\b(?:we decided|let'?s go with|the plan is|decision:) ([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)

_CONSTRAINT_RE = re.compile(
    r"\b(?:the deadline is|budget is|must not exceed|cannot exceed|can'?t exceed|constraint:) "
    r"([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)


def _subject_for(role: str) -> str:
    return role if role in {"user", "assistant", "system", "developer"} else "assistant"


def distill_message(
    role: str, text: str, *, namespace: str, source_ref: Optional[str] = None
) -> List[SemanticAtom]:
    """Extract candidate atoms from one message's text."""
    ref = source_ref or source_hash(text)
    subject = _subject_for(role)
    atoms: List[SemanticAtom] = []

    m = _NAME_RE.search(text)
    if m:
        atoms.append(SemanticAtom(
            subject=subject, predicate="has_name", object=m.group(1).strip(),
            polarity=True, scope="identity", confidence=0.9,
            source_refs=[ref], namespace=namespace,
            flags=FLAG_HIGH_IMPORTANCE,
        ))

    m = _PREF_POS_RE.search(text)
    if m:
        atoms.append(SemanticAtom(
            subject=subject, predicate="prefers", object=m.group(1).strip(),
            polarity=True, scope="preference", confidence=0.75,
            source_refs=[ref], namespace=namespace,
        ))

    m = _PREF_NEG_RE.search(text)
    if m:
        atoms.append(SemanticAtom(
            subject=subject, predicate="prefers", object=m.group(1).strip(),
            polarity=False, scope="preference", confidence=0.75,
            source_refs=[ref], namespace=namespace,
        ))

    m = _RULE_RE.search(text)
    if m:
        keyword, clause = m.group(1).lower(), m.group(2).strip()
        atoms.append(SemanticAtom(
            subject=subject, predicate="states_rule", object=clause,
            polarity=(keyword != "never"), scope="rule", confidence=0.85,
            source_refs=[ref], namespace=namespace,
            flags=FLAG_EXPLICIT_USER_RULE if role == "user" else 0,
        ))

    # Minimal imperative support for instruction forms the original floor
    # could not persist. Anchoring intentionally keeps "this answer only"
    # instructions transient instead of turning them into standing memory.
    m = _SCOPED_DIRECTIVE_RE.search(text)
    if m:
        verb, clause = m.group(1), m.group(2)
        atoms.append(SemanticAtom(
            subject=subject, predicate="states_rule",
            object=f"{verb} {clause}".strip(),
            polarity=(verb.lower() != "avoid"), scope="code_review", confidence=0.85,
            source_refs=[ref], namespace=namespace,
            flags=FLAG_EXPLICIT_USER_RULE if role == "user" else 0,
        ))
    else:
        m = _DIRECTIVE_RE.search(text)
        if m:
            verb, clause = m.group(1), m.group(2)
            atoms.append(SemanticAtom(
                subject=subject, predicate="states_rule",
                object=f"{verb} {clause}".strip(),
                polarity=(verb.lower() != "avoid"), scope="rule", confidence=0.85,
                source_refs=[ref], namespace=namespace,
                flags=FLAG_EXPLICIT_USER_RULE if role == "user" else 0,
            ))

    m = _DECISION_RE.search(text)
    if m:
        atoms.append(SemanticAtom(
            subject=subject, predicate="decided", object=m.group(1).strip(),
            polarity=True, scope="decision", confidence=0.8,
            source_refs=[ref], namespace=namespace,
        ))

    m = _CONSTRAINT_RE.search(text)
    if m:
        atoms.append(SemanticAtom(
            subject=subject, predicate="constrains", object=m.group(1).strip(),
            polarity=True, scope="constraint", confidence=0.85,
            source_refs=[ref], namespace=namespace,
            flags=FLAG_HIGH_IMPORTANCE,
        ))

    return atoms


def distill_segment(messages: List[dict], *, namespace: str) -> List[SemanticAtom]:
    """Merge a segment of already-relevant messages into candidate atoms,
    deduplicating identical extractions within this one batch (cross-batch
    dedup against CNS happens later, in `zerofold.dedup`)."""
    seen_object_ids: set = set()
    out: List[SemanticAtom] = []
    for m in messages:
        text = m.get("content", "")
        if not relevance_evaluate(text).keep:
            continue
        for atom in distill_message(m.get("role", "user"), text, namespace=namespace):
            oid = atom.object_id()
            if oid in seen_object_ids:
                continue
            seen_object_ids.add(oid)
            out.append(atom)
    return out
