"""Dedup engine — Bloom precheck -> fingerprint candidates -> similarity ->
polarity/constraint gate (spec sections 7 and 12).

Similarity only ever generates candidates; it never merges truth by itself.
The polarity check is the hard gate: a contradiction always supersedes
rather than silently overwriting, and a same-meaning restatement always
reinforces rather than growing the table with near-duplicates.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from zerofold.atoms import SemanticAtom
from zerofold.authority import instructions_conflict, profile_atom
from zerofold.bloom import BloomFilter
from zerofold.cns.store import CNSStore, row_to_atom
from zerofold.similarity import SimilarityBackend, get_default_similarity_backend

Action = str  # "create" | "reinforce" | "supersede"


@dataclass(frozen=True)
class DedupDecision:
    action: Action
    atom: SemanticAtom
    matched_object_id: Optional[str] = None
    similarity_score: Optional[float] = None


class DedupEngine:
    def __init__(
        self,
        *,
        similarity_backend: Optional[SimilarityBackend] = None,
        similarity_candidate_threshold: float = 0.5,
        similarity_reinforce_threshold: float = 0.82,
        bloom_size_bits: int = 1 << 16,
    ) -> None:
        self.similarity = similarity_backend or get_default_similarity_backend()
        self.similarity_candidate_threshold = similarity_candidate_threshold
        self.similarity_reinforce_threshold = similarity_reinforce_threshold
        self._bloom_size_bits = bloom_size_bits
        self._bloom_cache: Dict[str, BloomFilter] = {}

    async def _bloom_for(self, store: CNSStore, namespace: str) -> BloomFilter:
        if namespace not in self._bloom_cache:
            existing = await store.list_namespace(namespace)
            fingerprints = [row_to_atom(r).fingerprint() for r in existing]
            self._bloom_cache[namespace] = BloomFilter.seeded_with(
                fingerprints, size_bits=self._bloom_size_bits
            )
        return self._bloom_cache[namespace]

    def reset_cache(self, namespace: Optional[str] = None) -> None:
        """Drop the in-memory Bloom filter(s). Safe to call any time — the
        next lookup rebuilds from CNSStore, which is always the source of
        truth (spec section 12: false positives are fine, false negatives
        are not, and a rebuild-from-store can never introduce one)."""
        if namespace is None:
            self._bloom_cache.clear()
        else:
            self._bloom_cache.pop(namespace, None)

    async def resolve(self, atom: SemanticAtom, store: CNSStore) -> DedupDecision:
        fingerprint = atom.fingerprint()
        bloom = await self._bloom_for(store, atom.namespace)

        if not bloom.might_contain(fingerprint):
            bloom.add(fingerprint)
            return DedupDecision("create", atom)

        candidates = [
            (row, row_to_atom(row))
            for row in await store.list_namespace(atom.namespace)
        ]
        same_fingerprint = [
            (row, cand) for row, cand in candidates if cand.fingerprint() == fingerprint
        ]
        if not same_fingerprint:
            bloom.add(fingerprint)
            return DedupDecision("create", atom)

        best_row, best_atom, best_score = None, None, -1.0
        for row, cand in same_fingerprint:
            score = self.similarity.similarity(atom.object, cand.object)
            if score > best_score:
                best_row, best_atom, best_score = row, cand, score

        if best_atom is None:
            bloom.add(fingerprint)
            return DedupDecision("create", atom, similarity_score=best_score)

        old_instruction = profile_atom(best_atom)
        new_instruction = profile_atom(atom)
        instruction_relation = instructions_conflict(old_instruction, new_instruction)

        # Deterministic instruction semantics outrank lexical similarity.
        if old_instruction.topic and new_instruction.topic:
            if old_instruction.topic != new_instruction.topic:
                bloom.add(fingerprint)
                return DedupDecision("create", atom, similarity_score=best_score)
            if instruction_relation is True:
                return DedupDecision(
                    "supersede", atom, matched_object_id=best_row["object_id"],
                    similarity_score=best_score,
                )
            if instruction_relation is None:
                bloom.add(fingerprint)
                return DedupDecision("create", atom, similarity_score=best_score)

        if best_score < self.similarity_candidate_threshold:
            bloom.add(fingerprint)
            return DedupDecision("create", atom, similarity_score=best_score)

        if best_atom.polarity != atom.polarity:
            return DedupDecision(
                "supersede", atom, matched_object_id=best_row["object_id"],
                similarity_score=best_score,
            )

        if best_score >= self.similarity_reinforce_threshold:
            return DedupDecision(
                "reinforce", atom, matched_object_id=best_row["object_id"],
                similarity_score=best_score,
            )

        bloom.add(fingerprint)
        return DedupDecision("create", atom, similarity_score=best_score)
