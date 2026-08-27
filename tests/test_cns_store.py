import pytest

from zerofold.atoms import SemanticAtom
from zerofold.cns.store import atom_to_row, row_to_atom


@pytest.mark.asyncio
async def test_insert_and_get_atom(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    row = atom_to_row(atom, production_cost_tokens=5)
    await store.insert_atom(row)

    fetched = await store.get_atom(atom.object_id())
    assert fetched is not None
    assert fetched["namespace"] == "acme"
    assert fetched["tier"] == "episodic"
    restored = row_to_atom(fetched)
    assert restored.object == "dark mode"


@pytest.mark.asyncio
async def test_get_missing_atom_returns_none(store):
    assert await store.get_atom("does-not-exist") is None


@pytest.mark.asyncio
async def test_list_namespace_excludes_superseded_by_default(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5))
    await store.supersede(atom.object_id())

    active = await store.list_namespace("acme")
    assert active == []
    everything = await store.list_namespace("acme", include_superseded=True)
    assert len(everything) == 1


@pytest.mark.asyncio
async def test_reinforce_increments_counter(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5))
    row = await store.reinforce(atom.object_id())
    assert row["reinforcement_count"] == 1
    row = await store.reinforce(atom.object_id())
    assert row["reinforcement_count"] == 2


@pytest.mark.asyncio
async def test_promote_sets_long_term_tier(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5))
    await store.promote(atom.object_id())
    row = await store.get_atom(atom.object_id())
    assert row["tier"] == "long_term"


@pytest.mark.asyncio
async def test_record_retrieval_accumulates_and_crosses_payback(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    # production cost of 10 tokens; each retrieval avoids 6 tokens
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=10, production_cost_usd=0.001))

    row = await store.record_retrieval(atom.object_id(), avoided_tokens=6, avoided_cost_usd=0.0006)
    assert row["tokens_saved_total"] == 6
    assert row["payback_achieved"] == 0
    assert row["payback_count"] is None

    row = await store.record_retrieval(atom.object_id(), avoided_tokens=6, avoided_cost_usd=0.0006)
    assert row["tokens_saved_total"] == 12
    assert row["payback_achieved"] == 1
    assert row["payback_count"] == 2  # frozen at the retrieval_count that crossed


@pytest.mark.asyncio
async def test_payback_count_never_rewritten_after_crossing(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5, production_cost_usd=0.0))

    await store.record_retrieval(atom.object_id(), avoided_tokens=10, avoided_cost_usd=0.0)
    row = await store.get_atom(atom.object_id())
    assert row["payback_achieved"] == 1
    assert row["payback_count"] == 1

    # Further retrievals must not change payback_count.
    for _ in range(3):
        row = await store.record_retrieval(atom.object_id(), avoided_tokens=1, avoided_cost_usd=0.0)
    assert row["payback_count"] == 1
    assert row["retrieval_count"] == 4


@pytest.mark.asyncio
async def test_sweep_expired_removes_only_expired_non_long_term(store):
    from datetime import datetime, timedelta, timezone

    past = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    expired_atom = SemanticAtom(subject="user", predicate="prefers", object="a", namespace="acme")
    fresh_atom = SemanticAtom(subject="user", predicate="prefers", object="b", namespace="acme")
    long_term_atom = SemanticAtom(subject="user", predicate="prefers", object="c", namespace="acme")

    await store.insert_atom(atom_to_row(expired_atom, production_cost_tokens=1, expires_at=past))
    await store.insert_atom(atom_to_row(fresh_atom, production_cost_tokens=1, expires_at=future))
    await store.insert_atom(atom_to_row(long_term_atom, production_cost_tokens=1, expires_at=past))
    await store.promote(long_term_atom.object_id())

    removed = await store.sweep_expired()
    assert removed == 1
    assert await store.get_atom(expired_atom.object_id()) is None
    assert await store.get_atom(fresh_atom.object_id()) is not None
    assert await store.get_atom(long_term_atom.object_id()) is not None


@pytest.mark.asyncio
async def test_namespace_policy_defaults_when_absent(store):
    policy = await store.get_namespace_policy("brand-new-namespace")
    assert policy["extraction_threshold"] == 0.5
    assert policy["promotion_reinforce_n"] == 2
    assert policy["total_atoms_created"] == 0


@pytest.mark.asyncio
async def test_recompute_namespace_policy_reflects_payback_outcomes(store):
    a = SemanticAtom(subject="user", predicate="prefers", object="a", namespace="acme")
    b = SemanticAtom(subject="user", predicate="prefers", object="b", namespace="acme")
    await store.insert_atom(atom_to_row(a, production_cost_tokens=5))
    await store.insert_atom(atom_to_row(b, production_cost_tokens=5))
    await store.record_retrieval(a.object_id(), avoided_tokens=10, avoided_cost_usd=0.0)

    policy = await store.recompute_namespace_policy("acme")
    assert policy["total_atoms_created"] == 2
    assert policy["payback_rate"] == pytest.approx(0.5)
    assert policy["avg_payback_achievers"] == pytest.approx(1.0)
