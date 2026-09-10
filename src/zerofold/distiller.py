"""
The dedicated Step Zero Distiller (spec section 5).

Deterministic, pattern-based extraction of facts / decisions / commitments /
constraints from already-relevant text. No model call — this is the "free
deterministic work before paid inference" conservation law applied to
memory production.

Every atom's `object` is a source span that includes the operators that
bind the claim. A regex capture that dropped "Never" while stuffing the
negation into a polarity bit used to invert the stored rule on
reconstruction; that is no longer allowed. After extraction, `semantic_diff`
compares the source against `render_claim` of the produced atoms. Failure
falls back to a single source-preserving atom rather than storing an
inverted claim. That is the spec's DETERMINISTIC FIDELITY CHECK.
"""

from __future__ import annotations

import re
from typing import List, Optional

from zerofold.atoms import (
    FLAG_EXPLICIT_USER_RULE,
    FLAG_HIGH_IMPORTANCE,
    SemanticAtom,
    render_claim,
)
from zerofold.codec import source_hash
from zerofold.fidelity import polarity_of, semantic_diff, source_has_critical_operators
from zerofold.relevance import evaluate as relevance_evaluate

_MAX_CLAUSE = 120

_NAME_RE = re.compile(r"\bmy name is ([A-Za-z][\w \-']{1,40})", re.I)

_PREF_POS_RE = re.compile(r"\bi (?:prefer|like|love) ([^.!?\n]{2,%d})" % _MAX_CLAUSE, re.I)
_PREF_NEG_RE = re.compile(
    r"\bi (?:don'?t|do not|dislike|hate) (?:like )?([^.!?\n]{2,%d})" % _MAX_CLAUSE, re.I
)

# Modal is group 1 (always kept in the object). Optional "not" rides with it
# so "must not" is one operator span, not a positive "must" plus a leftover.
_RULE_RE = re.compile(
    r"\b((?:always|never|must|should)(?:\s+not)?)\s+([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)

_DECISION_RE = re.compile(
    r"\b(?:we decided|let'?s go with|the plan is|decision:) ([^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)

_CONSTRAINT_RE = re.compile(
    r"\b((?:the deadline is|the budget is|budget is|must not exceed|"
    r"cannot exceed|can'?t exceed|constraint:)\s+[^.!?\n]{2,%d})" % _MAX_CLAUSE,
    re.I,
)


def _subject_for(role: str) -> str:
    return "user" if role == "user" else "assistant"


def _atom(
    *,
    role: str,
    predicate: str,
    obj: str,
    scope: str,
    confidence: float,
    ref: str,
    namespace: str,
    flags: int = 0,
    polarity: Optional[bool] = None,
) -> SemanticAtom:
    obj = obj.strip()
    return SemanticAtom(
        subject=_subject_for(role),
        predicate=predicate,
        object=obj,
        polarity=polarity_of(obj) if polarity is None else polarity,
        scope=scope,
        confidence=confidence,
        source_refs=[ref],
        namespace=namespace,
        flags=flags,
    )


def _source_preserving_atom(
    role: str, text: str, *, namespace: str, ref: str
) -> SemanticAtom:
    """Fail closed: store the original clause rather than a lying compression."""
    flags = FLAG_EXPLICIT_USER_RULE if role == "user" else 0
    return _atom(
        role=role,
        predicate="states_rule",
        obj=text.strip(),
        scope="rule",
        confidence=0.7,
        ref=ref,
        namespace=namespace,
        flags=flags,
    )


def _enforce_fidelity(
    role: str, text: str, atoms: List[SemanticAtom], *, namespace: str, ref: str
) -> List[SemanticAtom]:
    """Spec section 5: DETERMINISTIC FIDELITY CHECK after distillation.

    If the reconstructed atoms would change polarity/authority/scope/entity/
    quantity/temporal meaning, replace them with one source-preserving atom.
    If nothing was extracted but the source carries critical operators,
    store the source rather than silently forgetting the rule.
    """
    if atoms:
        rendered = " ".join(render_claim(a) for a in atoms)
        if semantic_diff(text, rendered).ok:
            return atoms
        fallback = _source_preserving_atom(role, text, namespace=namespace, ref=ref)
        if semantic_diff(text, render_claim(fallback)).ok:
            return [fallback]
        # Last resort: do not store an inverted claim.
        return []

    if source_has_critical_operators(text):
        fallback = _source_preserving_atom(role, text, namespace=namespace, ref=ref)
        if semantic_diff(text, render_claim(fallback)).ok:
            return [fallback]
    return []


def distill_message(
    role: str, text: str, *, namespace: str, source_ref: Optional[str] = None
) -> List[SemanticAtom]:
    """Extract candidate atoms from one message's text."""
    ref = source_ref or source_hash(text)
    atoms: List[SemanticAtom] = []
    user_rule = FLAG_EXPLICIT_USER_RULE if role == "user" else 0

    m = _NAME_RE.search(text)
    if m:
        atoms.append(_atom(
            role=role, predicate="has_name", obj=m.group(1),
            scope="identity", confidence=0.9, ref=ref, namespace=namespace,
            flags=FLAG_HIGH_IMPORTANCE, polarity=True,
        ))

    m = _PREF_POS_RE.search(text)
    if m:
        atoms.append(_atom(
            role=role, predicate="prefers", obj=m.group(1),
            scope="preference", confidence=0.75, ref=ref, namespace=namespace,
            polarity=True,
        ))

    m = _PREF_NEG_RE.search(text)
    if m:
        # Keep the thing-preferred as the object so fingerprint grouping
        # still finds contradictions ("prefer X" vs "don't like X").
        # Polarity False is the structured negation; render_claim surfaces it.
        atoms.append(_atom(
            role=role, predicate="prefers", obj=m.group(1),
            scope="preference", confidence=0.75, ref=ref, namespace=namespace,
            polarity=False,
        ))

    for m in _RULE_RE.finditer(text):
        # Keep the modal in the object. Dropping "Never" here is the
        # reproduced polarity inversion.
        span = f"{m.group(1)} {m.group(2)}".strip()
        atoms.append(_atom(
            role=role, predicate="states_rule", obj=span,
            scope="rule", confidence=0.85, ref=ref, namespace=namespace,
            flags=user_rule,
        ))

    m = _DECISION_RE.search(text)
    if m:
        atoms.append(_atom(
            role=role, predicate="decided", obj=m.group(1),
            scope="decision", confidence=0.8, ref=ref, namespace=namespace,
            polarity=True,
        ))

    m = _CONSTRAINT_RE.search(text)
    if m:
        atoms.append(_atom(
            role=role, predicate="constrains", obj=m.group(1),
            scope="constraint", confidence=0.85, ref=ref, namespace=namespace,
            flags=FLAG_HIGH_IMPORTANCE,
        ))

    return _enforce_fidelity(role, text, atoms, namespace=namespace, ref=ref)


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
