"""
Zero Ledger — the accounting layer over CNSStore.

`CNSStore` owns the atomic counter updates; `Ledger` owns the *decisions*
built on top of them: was this atom worth keeping (ROI), has it earned
promotion to long-term (spec section 11), and how healthy is a namespace
overall (spec section 9's payback-rate-vs-speed distinction). Nothing here
does its own SQL beyond what CNSStore exposes — this module is the policy,
not the storage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from zerofold.atoms import FLAG_CONFIRMED, FLAG_EXPLICIT_USER_RULE, FLAG_HIGH_IMPORTANCE, has_flag
from zerofold.cns.store import CNSStore


@dataclass(frozen=True)
class RoiSnapshot:
    object_id: str
    roi_tokens: int
    roi_usd: float
    payback_achieved: bool
    payback_count: Optional[int]
    retrieval_count: int
    reinforcement_count: int


def roi_tokens(row: Dict[str, Any]) -> int:
    return (
        row["tokens_saved_total"]
        - row["production_cost_tokens"]
        - row["dedup_cost_tokens"]
    )


def roi_usd(row: Dict[str, Any]) -> float:
    return row["retrieval_savings_usd"] - row["production_cost_usd"]


def snapshot(row: Dict[str, Any]) -> RoiSnapshot:
    return RoiSnapshot(
        object_id=row["object_id"],
        roi_tokens=roi_tokens(row),
        roi_usd=roi_usd(row),
        payback_achieved=bool(row["payback_achieved"]),
        payback_count=row["payback_count"],
        retrieval_count=row["retrieval_count"],
        reinforcement_count=row["reinforcement_count"],
    )


def should_promote(row: Dict[str, Any], *, promotion_reinforce_n: int) -> bool:
    """Promotion rule (spec section 11): explicit user rule, enough
    independent reinforcement, or (high importance AND confirmed)."""
    flags = row.get("flags", 0)
    if has_flag(flags, FLAG_EXPLICIT_USER_RULE):
        return True
    if row.get("reinforcement_count", 0) >= promotion_reinforce_n:
        return True
    if has_flag(flags, FLAG_HIGH_IMPORTANCE) and has_flag(flags, FLAG_CONFIRMED):
        return True
    return False


class Ledger:
    """Convenience facade: record outcomes, then apply whatever policy
    decision follows from them, in one call."""

    def __init__(self, store: CNSStore) -> None:
        self.store = store

    async def record_retrieval(
        self, object_id: str, *, avoided_tokens: int, avoided_cost_usd: float
    ) -> Optional[RoiSnapshot]:
        row = await self.store.record_retrieval(
            object_id, avoided_tokens=avoided_tokens, avoided_cost_usd=avoided_cost_usd
        )
        return snapshot(row) if row else None

    async def record_reinforcement(self, object_id: str) -> Optional[RoiSnapshot]:
        row = await self.store.reinforce(object_id)
        if row is None:
            return None
        policy = await self.store.get_namespace_policy(row["namespace"])
        if row["tier"] != "long_term" and should_promote(
            row, promotion_reinforce_n=policy["promotion_reinforce_n"]
        ):
            await self.store.promote(object_id)
            row = await self.store.get_atom(object_id)
        return snapshot(row)

    async def namespace_health(self, namespace: str) -> Dict[str, Any]:
        """A namespace with a fast average payback but a low payback rate can
        be worse than one with a slower average and a high rate (spec section
        9) — report both rather than collapsing to one number."""
        return await self.store.recompute_namespace_policy(namespace)
