"""
Zero Supervisor — the public facade (spec sections 3, 4, 15).

Wraps the rest of ZeroFold behind three calls a host application actually
needs:

  intake()   — before sending a request, get a minimum-capability floor for
               routing and a compact context snippet distilled from prior
               durable atoms (spec's "compact atom retrieval -> cheaper
               future inference").
  evict()    — hand it messages that are about to fall out of active
               context; it runs them through the Conveyor so they become
               reusable atoms instead of disappearing.
  outbound() — validate a model's response against an output contract.

None of this calls a model. Where the spec calls for an independent LLM
score (fidelity) or a corrective regeneration (outbound), those are the
host's job — ZeroFold hands back exactly what decision to make and why.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional, Sequence

from zerofold.cns.ledger import Ledger
from zerofold.cns.store import CNSStore, row_to_atom
from zerofold.complexity import ComplexityInputs, complexity_score, min_quality_tier
from zerofold.contracts import OutputContract
from zerofold.conveyor import ConveyorReport, MemoryEvictionConveyor
from zerofold.dedup import DedupEngine
from zerofold.outbound import OutboundResult, OutboundSupervisor
from zerofold.similarity import SimilarityBackend, get_default_similarity_backend
from zerofold.tokens import estimate_tokens


@dataclass(frozen=True)
class IntakeEnrichment:
    min_quality_tier: int
    complexity_score: float
    context_snippet: Optional[str]
    context_atom_ids: List[str] = field(default_factory=list)


class ZeroSupervisor:
    def __init__(
        self,
        store: CNSStore,
        *,
        dedup: Optional[DedupEngine] = None,
        ledger: Optional[Ledger] = None,
        conveyor: Optional[MemoryEvictionConveyor] = None,
        outbound: Optional[OutboundSupervisor] = None,
        similarity_backend: Optional[SimilarityBackend] = None,
        context_atom_limit: int = 5,
        context_token_budget: int = 300,
        context_similarity_floor: float = 0.15,
    ) -> None:
        self.store = store
        self.dedup = dedup or DedupEngine()
        self.ledger = ledger or Ledger(store)
        self.conveyor = conveyor or MemoryEvictionConveyor(store, dedup=self.dedup, ledger=self.ledger)
        self.outbound_supervisor = outbound or OutboundSupervisor()
        self.similarity = similarity_backend or get_default_similarity_backend()
        self.context_atom_limit = context_atom_limit
        self.context_token_budget = context_token_budget
        self.context_similarity_floor = context_similarity_floor

    async def evict(self, namespace: str, messages: List[dict]) -> ConveyorReport:
        """Run messages falling out of active context through the Conveyor."""
        return await self.conveyor.process(namespace, messages)

    async def intake(
        self,
        namespace: str,
        messages: List[dict],
        *,
        intent: str = "chat",
        risk_flags: Sequence[str] = (),
        avoided_cost_per_token_usd: float = 0.0,
    ) -> IntakeEnrichment:
        """Compute a routing floor and pull in relevant durable context."""
        context_tokens = sum(estimate_tokens(m.get("content", "")) for m in messages)
        score = complexity_score(
            ComplexityInputs(intent=intent, context_tokens=context_tokens, risk_flags=risk_flags)
        )
        tier = min_quality_tier(score)

        latest_user_text = next(
            (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"), ""
        )

        snippet, used_ids = None, []
        if latest_user_text:
            candidates = await self.store.list_namespace(namespace, tier="long_term")
            scored = []
            for row in candidates:
                atom = row_to_atom(row)
                text = f"{atom.subject} {atom.predicate} {atom.object}"
                s = self.similarity.similarity(latest_user_text, text)
                if s >= self.context_similarity_floor:
                    scored.append((s, row, atom))
            scored.sort(key=lambda t: -t[0])

            lines: List[str] = []
            budget = self.context_token_budget
            for _, row, atom in scored[: self.context_atom_limit]:
                line = f"- {atom.subject} {atom.predicate.replace('_', ' ')} {atom.object}"
                cost = estimate_tokens(line)
                if cost > budget:
                    break
                lines.append(line)
                used_ids.append(row["object_id"])
                budget -= cost
                avoided = estimate_tokens(latest_user_text)
                await self.ledger.record_retrieval(
                    row["object_id"],
                    avoided_tokens=avoided,
                    avoided_cost_usd=avoided * avoided_cost_per_token_usd,
                )

            if lines:
                snippet = "Known context:\n" + "\n".join(lines)

        return IntakeEnrichment(
            min_quality_tier=tier,
            complexity_score=score,
            context_snippet=snippet,
            context_atom_ids=used_ids,
        )

    def outbound(self, text: str, contract: OutputContract) -> OutboundResult:
        return self.outbound_supervisor.validate(text, contract)
