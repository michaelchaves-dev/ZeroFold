"""
Zero Conveyor — the memory eviction pipeline (spec section 5).

Turns messages that are about to fall out of active context into durable
CNS atoms instead of silently discarding them: relevance gate -> segment
distillation -> dedup resolution -> store write. Nothing here calls a
model; everything is the deterministic path described in the spec's
Day-One tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Optional

from zerofold.cns.ledger import Ledger
from zerofold.cns.store import CNSStore, atom_to_row
from zerofold.dedup import DedupEngine
from zerofold.distiller import distill_segment
from zerofold.relevance import filter_relevant
from zerofold.tokens import estimate_tokens


@dataclass(frozen=True)
class ConveyorReport:
    messages_considered: int
    messages_kept: int
    atoms_created: int
    atoms_reinforced: int
    atoms_superseded: int
    created_object_ids: List[str] = field(default_factory=list)


class MemoryEvictionConveyor:
    def __init__(
        self,
        store: CNSStore,
        *,
        dedup: Optional[DedupEngine] = None,
        ledger: Optional[Ledger] = None,
        estimate_tokens_fn: Callable[[str], int] = estimate_tokens,
    ) -> None:
        self.store = store
        self.dedup = dedup or DedupEngine()
        self.ledger = ledger or Ledger(store)
        self.estimate_tokens = estimate_tokens_fn

    async def process(self, namespace: str, messages: List[dict]) -> ConveyorReport:
        relevant = filter_relevant(messages)
        if not relevant:
            return ConveyorReport(len(messages), 0, 0, 0, 0)

        atoms = distill_segment(relevant, namespace=namespace)
        created = reinforced = superseded = 0
        created_ids: List[str] = []

        for atom in atoms:
            decision = await self.dedup.resolve(atom, self.store)

            if decision.action == "reinforce":
                await self.ledger.record_reinforcement(decision.matched_object_id)
                reinforced += 1
                continue

            # "create" and "supersede" both write a brand-new row for this
            # atom; free deterministic distillation means production cost is
            # zero USD (no model call), which makes the atom's first
            # retrieval the payback-crossing event.
            row = atom_to_row(
                atom,
                production_cost_tokens=self.estimate_tokens(atom.object),
                production_cost_usd=0.0,
                dedup_cost_tokens=0,
                supersedes_id=decision.matched_object_id if decision.action == "supersede" else None,
            )
            await self.store.insert_atom(row)
            created_ids.append(atom.object_id())

            if decision.action == "supersede":
                await self.store.supersede(decision.matched_object_id)
                superseded += 1
            else:
                created += 1

        return ConveyorReport(
            messages_considered=len(messages),
            messages_kept=len(relevant),
            atoms_created=created,
            atoms_reinforced=reinforced,
            atoms_superseded=superseded,
            created_object_ids=created_ids,
        )
