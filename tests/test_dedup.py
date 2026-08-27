import pytest

from zerofold.atoms import SemanticAtom
from zerofold.cns.store import atom_to_row
from zerofold.dedup import DedupEngine


@pytest.mark.asyncio
async def test_new_fact_creates(store):
    engine = DedupEngine()
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    decision = await engine.resolve(atom, store)
    assert decision.action == "create"


@pytest.mark.asyncio
async def test_restating_the_same_fact_reinforces(store):
    engine = DedupEngine()
    first = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(first, production_cost_tokens=3))

    # Trivial rephrasing (case/whitespace only) — same meaning, near-1.0 similarity.
    restated = SemanticAtom(subject="user", predicate="prefers", object="Dark Mode", namespace="acme")
    decision = await engine.resolve(restated, store)
    assert decision.action == "reinforce"
    assert decision.matched_object_id == first.object_id()


@pytest.mark.asyncio
async def test_contradiction_supersedes(store):
    engine = DedupEngine()
    original = SemanticAtom(
        subject="user", predicate="prefers", object="dark mode", polarity=True, namespace="acme"
    )
    await store.insert_atom(atom_to_row(original, production_cost_tokens=3))

    contradiction = SemanticAtom(
        subject="user", predicate="prefers", object="dark mode", polarity=False, namespace="acme"
    )
    decision = await engine.resolve(contradiction, store)
    assert decision.action == "supersede"
    assert decision.matched_object_id == original.object_id()


@pytest.mark.asyncio
async def test_different_meaning_same_fingerprint_creates(store):
    engine = DedupEngine(similarity_candidate_threshold=0.9, similarity_reinforce_threshold=0.95)
    original = SemanticAtom(subject="user", predicate="likes", object="pizza", namespace="acme")
    await store.insert_atom(atom_to_row(original, production_cost_tokens=3))

    unrelated_same_fp = SemanticAtom(subject="user", predicate="likes", object="rock climbing", namespace="acme")
    decision = await engine.resolve(unrelated_same_fp, store)
    assert decision.action == "create"


@pytest.mark.asyncio
async def test_different_namespace_never_matches(store):
    engine = DedupEngine()
    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="tenant-a")
    await store.insert_atom(atom_to_row(a, production_cost_tokens=3))

    b = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="tenant-b")
    decision = await engine.resolve(b, store)
    assert decision.action == "create"


@pytest.mark.asyncio
async def test_bloom_cache_reset_forces_rebuild_from_store(store):
    engine = DedupEngine()

    # Prime the cache while the namespace is still empty (simulates a
    # process whose in-memory Bloom filter predates a write made elsewhere).
    await engine._bloom_for(store, "acme")

    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(a, production_cost_tokens=3))

    b = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")

    # Stale cache doesn't know about `a` yet -> wrongly creates instead of reinforcing.
    decision = await engine.resolve(b, store)
    assert decision.action == "create"

    engine.reset_cache("acme")
    decision = await engine.resolve(b, store)
    assert decision.action == "reinforce"
    assert decision.matched_object_id == a.object_id()
