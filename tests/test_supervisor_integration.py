import pytest

from zerofold.contracts import contract_from_intent
from zerofold.supervisor import ZeroSupervisor


@pytest.mark.asyncio
async def test_full_lifecycle_eviction_promotion_context_injection_outbound(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.05)
    namespace = "acme-customer-42"

    conversation = [
        {"role": "user", "content": "Always keep responses under 100 words for me."},
        {"role": "assistant", "content": "Understood."},
    ]

    # 1. The conversation ages out of active context -> Conveyor distills it.
    report = await supervisor.evict(namespace, conversation)
    assert report.atoms_created == 1

    # An episodic atom with only one mention isn't durable context yet.
    enrichment = await supervisor.intake(
        namespace, [{"role": "user", "content": "keep responses short please"}], intent="chat"
    )
    assert enrichment.context_snippet is None

    # 2. The same rule gets restated in a later conversation -> reinforcement.
    report2 = await supervisor.evict(
        namespace, [{"role": "user", "content": "Always keep responses under 100 words for me."}]
    )
    assert report2.atoms_reinforced == 1

    # promotion_reinforce_n defaults to 2; two reinforcements needed after
    # the initial create (reinforcement_count starts at 0 on creation).
    await supervisor.evict(
        namespace, [{"role": "user", "content": "Always keep responses under 100 words for me."}]
    )

    # 3. Now that it's long-term, intake should surface it as context.
    enrichment = await supervisor.intake(
        namespace,
        [{"role": "user", "content": "keep responses short please"}],
        intent="chat",
    )
    assert enrichment.context_snippet is not None
    assert "under 100 words" in enrichment.context_snippet
    assert len(enrichment.context_atom_ids) == 1
    assert enrichment.min_quality_tier in (1, 2, 3)

    # Retrieval should have recorded ROI on the ledger.
    atom_id = enrichment.context_atom_ids[0]
    row = await store.get_atom(atom_id)
    assert row["retrieval_count"] == 1
    assert row["tokens_saved_total"] > 0

    # 4. Outbound validation against a contract built from the same intent.
    contract = contract_from_intent("chat", 50)
    result = supervisor.outbound("Sure, I will keep it brief.", contract)
    assert result.passed


@pytest.mark.asyncio
async def test_intake_complexity_floor_rises_with_intent_and_context_size(store):
    supervisor = ZeroSupervisor(store)
    short_chat = await supervisor.intake("ns", [{"role": "user", "content": "hi"}], intent="chat")
    big_code_review = await supervisor.intake(
        "ns",
        [{"role": "user", "content": "x" * 20_000}],
        intent="code",
        risk_flags=["destructive_action"],
    )
    assert big_code_review.min_quality_tier >= short_chat.min_quality_tier
    assert big_code_review.complexity_score > short_chat.complexity_score


@pytest.mark.asyncio
async def test_contradiction_across_sessions_supersedes_not_duplicates(store):
    supervisor = ZeroSupervisor(store)
    namespace = "acme"

    await supervisor.evict(namespace, [{"role": "user", "content": "I prefer email notifications."}])
    await supervisor.evict(namespace, [{"role": "user", "content": "I don't like email notifications."}])

    active = await store.list_namespace(namespace)
    assert len(active) == 1
    everything = await store.list_namespace(namespace, include_superseded=True)
    assert len(everything) == 2
