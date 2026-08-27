import pytest

from zerofold.atoms import FLAG_CONFIRMED, FLAG_EXPLICIT_USER_RULE, FLAG_HIGH_IMPORTANCE, SemanticAtom
from zerofold.cns.ledger import Ledger, roi_tokens, roi_usd, should_promote
from zerofold.cns.store import atom_to_row


def _row(**overrides):
    base = {
        "tokens_saved_total": 100,
        "production_cost_tokens": 20,
        "dedup_cost_tokens": 5,
        "retrieval_savings_usd": 0.01,
        "production_cost_usd": 0.002,
        "flags": 0,
        "reinforcement_count": 0,
    }
    base.update(overrides)
    return base


def test_roi_tokens_and_usd():
    row = _row()
    assert roi_tokens(row) == 75
    assert roi_usd(row) == pytest.approx(0.008)


def test_should_promote_on_explicit_user_rule():
    row = _row(flags=FLAG_EXPLICIT_USER_RULE)
    assert should_promote(row, promotion_reinforce_n=2)


def test_should_promote_on_enough_reinforcement():
    row = _row(reinforcement_count=2)
    assert should_promote(row, promotion_reinforce_n=2)
    row = _row(reinforcement_count=1)
    assert not should_promote(row, promotion_reinforce_n=2)


def test_should_promote_on_high_importance_and_confirmed():
    row = _row(flags=FLAG_HIGH_IMPORTANCE | FLAG_CONFIRMED)
    assert should_promote(row, promotion_reinforce_n=99)
    row = _row(flags=FLAG_HIGH_IMPORTANCE)
    assert not should_promote(row, promotion_reinforce_n=99)


@pytest.mark.asyncio
async def test_ledger_record_reinforcement_promotes_at_threshold(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5))
    await store.upsert_namespace_policy("acme", promotion_reinforce_n=2)
    ledger = Ledger(store)

    snap = await ledger.record_reinforcement(atom.object_id())
    assert snap.reinforcement_count == 1
    row = await store.get_atom(atom.object_id())
    assert row["tier"] == "episodic"

    snap = await ledger.record_reinforcement(atom.object_id())
    assert snap.reinforcement_count == 2
    row = await store.get_atom(atom.object_id())
    assert row["tier"] == "long_term"


@pytest.mark.asyncio
async def test_ledger_record_retrieval_returns_snapshot(store):
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    await store.insert_atom(atom_to_row(atom, production_cost_tokens=5, production_cost_usd=0.0))
    ledger = Ledger(store)

    snap = await ledger.record_retrieval(atom.object_id(), avoided_tokens=10, avoided_cost_usd=0.0)
    assert snap.payback_achieved is True
    assert snap.roi_tokens == 5  # 10 saved - 5 production - 0 dedup


@pytest.mark.asyncio
async def test_namespace_health_reports_rate_and_average(store):
    a = SemanticAtom(subject="user", predicate="prefers", object="a", namespace="acme")
    b = SemanticAtom(subject="user", predicate="prefers", object="b", namespace="acme")
    await store.insert_atom(atom_to_row(a, production_cost_tokens=5))
    await store.insert_atom(atom_to_row(b, production_cost_tokens=5))
    ledger = Ledger(store)
    await ledger.record_retrieval(a.object_id(), avoided_tokens=10, avoided_cost_usd=0.0)

    health = await ledger.namespace_health("acme")
    assert health["total_atoms_created"] == 2
    assert health["payback_rate"] == pytest.approx(0.5)
