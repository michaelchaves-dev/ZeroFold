"""Deterministic instruction authority and scope resolution.

This module is intentionally narrow. It does not replace retrieval or the
Conveyor. It decides whether durable instruction-like atoms are safe to inject
when a current explicit instruction may conflict with them.

Precedence is:
    source authority > scope specificity > explicitness > recency/order

Recency is only a tiebreaker after authority/scope/explicitness. A current-turn
temporary instruction can override an otherwise-active standing rule without
mutating durable history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple

from zerofold.atoms import FLAG_EXPLICIT_USER_RULE, SemanticAtom, has_flag
from zerofold.cns.store import row_to_atom

ACTIVE = "ACTIVE"
SUPERSEDED = "SUPERSEDED"
TEMPORARILY_OVERRIDDEN = "TEMPORARILY_OVERRIDDEN"
OUT_OF_SCOPE = "OUT_OF_SCOPE"
COMPATIBLE = "COMPATIBLE"
UNRESOLVED = "UNRESOLVED"

_AUTHORITY = {
    "system": 40,
    "developer": 30,
    "user": 20,
    "assistant": 10,
}

_TEMP_RE = re.compile(
    r"\b(?:for\s+)?(?:this answer|this response|this turn)\s+only\b|\bonly for this (?:answer|response|turn)\b",
    re.I,
)
_CODE_REVIEW_SCOPE_RE = re.compile(r"\b(?:for|in)\s+code reviews?\b", re.I)
_DIRECTIVE_RE = re.compile(
    r"\b(always|never|must|should|use|include|keep|answer|write|respond|avoid|ignore|explain)\b",
    re.I,
)
_LENGTH_RE = re.compile(
    r"\b(under|over|at least|at most|less than|more than)\s+(\d+)\s*[- ]?words?\b",
    re.I,
)
_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class InstructionCandidate:
    text: str
    topic: Optional[str]
    value: Optional[str]
    polarity: bool
    scope: str
    permanence: str
    source_role: str
    explicit: bool
    recency: Optional[str] = None
    order: int = 0
    object_id: Optional[str] = None


@dataclass(frozen=True)
class AuthorityState:
    object_id: str
    status: str
    reason: str
    topic: Optional[str]
    scope: str


def _normalise_scope(scope: str) -> str:
    s = (scope or "").strip().lower().replace("-", "_").replace(" ", "_")
    if s in {"", "global", "rule", "preference", "constraint"}:
        return "global"
    if s in {"code", "code_review", "code_reviews"}:
        return "code_review"
    return s


def scope_from_context(intent: str, text: str = "") -> str:
    i = (intent or "").strip().lower().replace("-", "_").replace(" ", "_")
    if i in {"code_review", "review_code", "code_reviews"}:
        return "code_review"
    if _CODE_REVIEW_SCOPE_RE.search(text or ""):
        return "code_review"
    return "global"


def _semantic_topic_value(text: str, polarity: bool) -> Tuple[Optional[str], Optional[str]]:
    t = " ".join((text or "").split()).strip().lower()

    if re.search(
        r"\b(?:word limit|words?|concise|concisely|brief|briefly|short|shorter|detail|detailed|verbose|verbosity)\b",
        t,
    ):
        if "ignore" in t and ("limit" in t or "words" in t):
            m = re.search(r"\b(\d+)\s*[- ]?word", t)
            return "response_length", "ignore_limit:%s" % (m.group(1) if m else "*")
        m = _LENGTH_RE.search(t)
        if m:
            op = {
                "less than": "under",
                "more than": "over",
                "at most": "at_most",
                "at least": "at_least",
            }.get(m.group(1).lower(), m.group(1).lower().replace(" ", "_"))
            return "response_length", "%s:%s" % (op, m.group(2))
        if re.search(r"\b(?:concise|concisely|brief|briefly|short|shorter)\b", t):
            return "response_length", "concise"
        if re.search(r"\b(?:detail|detailed|verbose|verbosity)\b", t):
            return "response_length", "detailed"
        return "response_length", None

    if re.search(r"\b(?:bullet|bullets|bullet points?|paragraph|paragraphs)\b", t):
        if re.search(r"\b(?:bullet|bullets|bullet points?)\b", t):
            return "response_format", "bullets"
        return "response_format", "paragraphs"

    if re.search(r"\b(?:source|sources|citation|citations|cite)\b", t):
        omit = bool(re.search(r"\b(?:omit|without|avoid)\b", t))
        include = bool(re.search(r"\b(?:include|cite|with)\b", t))
        if omit:
            return "sources", "include" if not polarity else "omit"
        if include:
            return "sources", "omit" if not polarity else "include"
        return "sources", None

    if re.search(r"\b(?:tone|professional|casual|natural)\b", t):
        for value in ("professional", "casual", "natural"):
            if re.search(r"\b%s\b" % value, t):
                return "tone", value
        return "tone", None

    return None, None


def _infer_polarity(text: str) -> bool:
    t = (text or "").strip().lower()
    if re.search(r"\bnever\b", t):
        return False
    if re.search(r"\b(?:do not|don't)\b", t):
        return False
    if re.match(r"^(?:please\s+)?avoid\b", t):
        return False
    return True


def extract_current_instructions(text: str, *, source_role: str = "user") -> List[InstructionCandidate]:
    """Extract explicit instruction candidates from the current message only."""
    out: List[InstructionCandidate] = []
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+|\n+", text or "") if s.strip()]
    for order, sentence in enumerate(sentences):
        if not _DIRECTIVE_RE.search(sentence):
            continue
        lower = sentence.lower().lstrip()
        stripped = re.sub(r"^(?:for|in)\s+code reviews?\s*,?\s*", "", lower)
        stripped = re.sub(
            r"^(?:for\s+)?(?:this answer|this response|this turn)\s+only\s*,?\s*",
            "",
            stripped,
        )
        stripped = re.sub(r"^please\s+", "", stripped)
        if not re.match(
            r"^(always|never|must|should|use|include|keep|answer|write|respond|avoid|ignore|explain)\b",
            stripped,
        ):
            continue

        polarity = _infer_polarity(stripped)
        topic, value = _semantic_topic_value(sentence, polarity)
        out.append(
            InstructionCandidate(
                text=sentence,
                topic=topic,
                value=value,
                polarity=polarity,
                scope="code_review" if _CODE_REVIEW_SCOPE_RE.search(sentence) else "global",
                permanence="current_turn" if _TEMP_RE.search(sentence) else "standing",
                source_role=source_role,
                explicit=True,
                order=order,
            )
        )
    return out


def profile_atom(atom: SemanticAtom, row: Optional[Dict[str, Any]] = None) -> InstructionCandidate:
    topic, value = _semantic_topic_value(atom.object, atom.polarity)
    return InstructionCandidate(
        text=atom.object,
        topic=topic,
        value=value,
        polarity=atom.polarity,
        scope=_normalise_scope(atom.scope),
        permanence="standing",
        source_role=atom.subject if atom.subject in _AUTHORITY else "assistant",
        explicit=has_flag(atom.flags, FLAG_EXPLICIT_USER_RULE) or atom.subject in {"system", "developer"},
        recency=(row or {}).get("created_at"),
        object_id=(row or {}).get("object_id"),
    )


def _token_overlap(a: str, b: str) -> float:
    aa = set(_TOKEN_RE.findall((a or "").lower()))
    bb = set(_TOKEN_RE.findall((b or "").lower()))
    if not aa or not bb:
        return 0.0
    return len(aa & bb) / float(min(len(aa), len(bb)))


def instructions_conflict(a: InstructionCandidate, b: InstructionCandidate) -> Optional[bool]:
    """Return True/False when deterministic, None when conflict is ambiguous."""
    if a.topic and b.topic and a.topic != b.topic:
        return False
    if a.topic is None or b.topic is None:
        return None if _token_overlap(a.text, b.text) >= 0.5 else False

    if a.topic == "response_length":
        if a.value == b.value and a.value is not None:
            return a.polarity != b.polarity
        if (a.value or "").startswith("ignore_limit:") or (b.value or "").startswith("ignore_limit:"):
            return True
        if {a.value, b.value} == {"concise", "detailed"}:
            return True
        ceiling_a = bool(a.value and (a.value.startswith("under:") or a.value.startswith("at_most:")))
        ceiling_b = bool(b.value and (b.value.startswith("under:") or b.value.startswith("at_most:")))
        if ((a.value == "concise" and ceiling_b) or (b.value == "concise" and ceiling_a)):
            return False if a.polarity and b.polarity else None
        if a.value and b.value and ":" in a.value and ":" in b.value:
            return None
        return None

    if a.topic == "response_format":
        if a.value == b.value and a.value is not None:
            return a.polarity != b.polarity
        if {a.value, b.value} == {"bullets", "paragraphs"}:
            return True
        return None

    if a.topic == "sources":
        if a.value == b.value and a.value is not None:
            return False
        if {a.value, b.value} == {"include", "omit"}:
            return True
        return None

    if a.topic == "tone":
        if a.value == b.value and a.value is not None:
            return False
        if {a.value, b.value} == {"professional", "casual"}:
            return True
        return None

    return None


def _authority(candidate: InstructionCandidate) -> int:
    return _AUTHORITY.get(candidate.source_role, 0)


def _scope_specificity(scope: str) -> int:
    return 0 if _normalise_scope(scope) == "global" else 10


def _recency_value(value: Optional[str]) -> float:
    if not value:
        return 0.0
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def _precedence(candidate: InstructionCandidate) -> Tuple[int, int, int, float, int]:
    return (
        _authority(candidate),
        _scope_specificity(candidate.scope),
        1 if candidate.explicit else 0,
        _recency_value(candidate.recency),
        candidate.order,
    )


def _scope_applies(rule_scope: str, current_scope: str) -> bool:
    rs = _normalise_scope(rule_scope)
    cs = _normalise_scope(current_scope)
    return rs == "global" or rs == cs


def _same_turn_unresolved(current: Sequence[InstructionCandidate], current_scope: str) -> set:
    topics = set()
    applicable = [c for c in current if _scope_applies(c.scope, current_scope)]
    for i, a in enumerate(applicable):
        for b in applicable[i + 1 :]:
            if a.scope != b.scope or not a.topic or a.topic != b.topic:
                continue
            if instructions_conflict(a, b) is True:
                topics.add(a.topic)
    return topics


def resolve_rows_for_intake(
    rows: Sequence[Dict[str, Any]],
    current: Sequence[InstructionCandidate],
    *,
    current_scope: str,
) -> Tuple[List[Dict[str, Any]], List[AuthorityState]]:
    """Classify durable instruction atoms and return only safe-to-inject rows."""
    entries = []
    unresolved_current_topics = _same_turn_unresolved(current, current_scope)

    for row in rows:
        atom = row_to_atom(row)
        profile = profile_atom(atom, row)
        is_instruction = atom.predicate == "states_rule" or profile.topic is not None
        status = ACTIVE
        reason = "active durable instruction"

        if is_instruction and not _scope_applies(profile.scope, current_scope):
            status = OUT_OF_SCOPE
            reason = "instruction scope does not apply to this request"
        elif is_instruction and profile.topic in unresolved_current_topics:
            status = UNRESOLVED
            reason = "current turn contains contradictory instructions in the same scope"
        elif is_instruction:
            saw_compatible = False
            for cur in current:
                if not _scope_applies(cur.scope, current_scope):
                    continue
                relation = instructions_conflict(profile, cur)
                if relation is False:
                    saw_compatible = True
                    continue
                if relation is None:
                    if (profile.topic and profile.topic == cur.topic) or _token_overlap(profile.text, cur.text) >= 0.5:
                        if _authority(cur) >= _authority(profile):
                            status = UNRESOLVED
                            reason = "possible conflict with current explicit instruction is ambiguous"
                            break
                    continue

                current_wins = (
                    _authority(cur) > _authority(profile)
                    or (_authority(cur) == _authority(profile) and cur.explicit)
                )
                if current_wins:
                    if cur.permanence == "current_turn":
                        status = TEMPORARILY_OVERRIDDEN
                        reason = "current-turn instruction temporarily overrides durable memory"
                    else:
                        status = SUPERSEDED
                        reason = "current explicit instruction outranks conflicting durable memory"
                    break
            else:
                if saw_compatible and current:
                    status = COMPATIBLE
                    reason = "no semantic conflict with current explicit instruction"

        entries.append([row, profile, status, reason, is_instruction])

    for i in range(len(entries)):
        row_a, a, status_a, reason_a, inst_a = entries[i]
        if not inst_a or status_a not in {ACTIVE, COMPATIBLE}:
            continue
        for j in range(i + 1, len(entries)):
            row_b, b, status_b, reason_b, inst_b = entries[j]
            if not inst_b or status_b not in {ACTIVE, COMPATIBLE}:
                continue
            if not _scope_applies(a.scope, current_scope) or not _scope_applies(b.scope, current_scope):
                continue

            relation = instructions_conflict(a, b)
            if relation is False:
                continue
            if relation is None:
                if a.topic and a.topic == b.topic:
                    entries[i][2] = UNRESOLVED
                    entries[i][3] = "durable instructions have an ambiguous semantic conflict"
                    entries[j][2] = UNRESOLVED
                    entries[j][3] = "durable instructions have an ambiguous semantic conflict"
                continue

            if _precedence(a) == _precedence(b):
                entries[i][2] = UNRESOLVED
                entries[i][3] = "equal-precedence durable instructions conflict"
                entries[j][2] = UNRESOLVED
                entries[j][3] = "equal-precedence durable instructions conflict"
                continue

            winner_i = _precedence(a) > _precedence(b)
            loser = j if winner_i else i
            winner = i if winner_i else j
            loser_profile = entries[loser][1]
            winner_profile = entries[winner][1]

            if _normalise_scope(loser_profile.scope) != _normalise_scope(winner_profile.scope):
                entries[loser][2] = TEMPORARILY_OVERRIDDEN
                entries[loser][3] = "narrower applicable scope overrides broader durable rule"
            else:
                entries[loser][2] = SUPERSEDED
                entries[loser][3] = "higher-precedence durable instruction wins"

    states: List[AuthorityState] = []
    safe_rows: List[Dict[str, Any]] = []
    for row, profile, status, reason, is_instruction in entries:
        if is_instruction:
            states.append(
                AuthorityState(
                    object_id=row["object_id"],
                    status=status,
                    reason=reason,
                    topic=profile.topic,
                    scope=profile.scope,
                )
            )
        if status in {ACTIVE, COMPATIBLE}:
            safe_rows.append(row)

    return safe_rows, states
