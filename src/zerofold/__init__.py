"""
ZeroFold — fold information to its minimum useful state. Unfold only what
intelligence requires.

A conservation and memory layer for LLM systems: durable facts survive
context eviction as Zero Atoms in CNS (the persistent truth/state store),
duplicates and contradictions are resolved deterministically, memory proves
its own ROI before it's trusted, and a router gets a minimum-capability
floor instead of guessing from price alone.

ZeroFold never calls a model itself. It hands back atoms, decisions, and
scores; a host application (e.g. SubtracToken, or any other LLM pipeline)
supplies the model calls and the routing/economics around them.

Quick start::

    from zerofold import CNSStore, ZeroSupervisor

    store = CNSStore("cns.db")
    await store.connect()
    supervisor = ZeroSupervisor(store)

    enrichment = await supervisor.intake("customer-42", messages, intent="qa")
    # enrichment.min_quality_tier -> feed into your router's model floor
    # enrichment.context_snippet  -> prepend as a system message

    report = await supervisor.evict("customer-42", messages_falling_out_of_context)
    # report.atoms_created / .atoms_reinforced / .atoms_superseded

    result = supervisor.outbound(model_response_text, contract)
    # result.passed, result.violations
"""

from __future__ import annotations

from zerofold.atoms import (
    FLAG_CONFIRMED,
    FLAG_EXPLICIT_USER_RULE,
    FLAG_HIGH_IMPORTANCE,
    FLAG_SUPERSEDED,
    SemanticAtom,
)
from zerofold.cns.ledger import Ledger, RoiSnapshot
from zerofold.cns.store import CNSStore
from zerofold.complexity import ComplexityInputs, complexity_score, min_quality_tier
from zerofold.contracts import OutputContract, contract_from_intent
from zerofold.conveyor import ConveyorReport, MemoryEvictionConveyor
from zerofold.dedup import DedupDecision, DedupEngine
from zerofold.fidelity import FidelityDiff, FidelityGate, FidelityResult, deterministic_diff
from zerofold.outbound import OutboundResult, OutboundSupervisor, OutboundViolation
from zerofold.supervisor import IntakeEnrichment, ZeroSupervisor

__version__ = "0.1.0"

__all__ = [
    "__version__",
    "SemanticAtom",
    "FLAG_EXPLICIT_USER_RULE",
    "FLAG_CONFIRMED",
    "FLAG_HIGH_IMPORTANCE",
    "FLAG_SUPERSEDED",
    "CNSStore",
    "Ledger",
    "RoiSnapshot",
    "DedupEngine",
    "DedupDecision",
    "FidelityGate",
    "FidelityResult",
    "FidelityDiff",
    "deterministic_diff",
    "MemoryEvictionConveyor",
    "ConveyorReport",
    "ComplexityInputs",
    "complexity_score",
    "min_quality_tier",
    "OutputContract",
    "contract_from_intent",
    "OutboundSupervisor",
    "OutboundResult",
    "OutboundViolation",
    "ZeroSupervisor",
    "IntakeEnrichment",
]
