import pytest

from zerofold.atoms import SemanticAtom
from zerofold.cns.store import atom_to_row, row_to_atom
from zerofold.supervisor import ZeroSupervisor


async def _persist_and_promote(supervisor, store, namespace, text, *, role="user"):
    report = await supervisor.evict(namespace, [{"role": role, "content": text}])
    assert report.created_object_ids
    object_id = report.created_object_ids[-1]
    await store.promote(object_id)
    return object_id


def _state(enrichment, object_id):
    return next(s for s in enrichment.authority_states if s.object_id == object_id)


@pytest.mark.asyncio
async def test_a_current_direct_reversal_blocks_old_then_persists_supersession(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "authority-a"
    old_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )

    current = await supervisor.intake(
        ns, [{"role": "user", "content": "Never keep responses under 100 words."}]
    )
    assert old_id not in current.context_atom_ids
    assert _state(current, old_id).status == "SUPERSEDED"

    report = await supervisor.evict(
        ns, [{"role": "user", "content": "Never keep responses under 100 words."}]
    )
    assert report.atoms_superseded == 1
    history = await store.list_namespace(ns, include_superseded=True)
    assert len(history) == 2
    assert (await store.get_atom(old_id))["superseded_at"] is not None
    active = await store.list_namespace(ns)
    assert len(active) == 1
    assert row_to_atom(active[0]).polarity is False


@pytest.mark.asyncio
async def test_b_preference_change_supersedes_low_similarity_old_instruction(store):
    supervisor = ZeroSupervisor(store)
    ns = "authority-b"
    old_id = await _persist_and_promote(supervisor, store, ns, "Use bullet points.")

    report = await supervisor.evict(
        ns, [{"role": "user", "content": "Use paragraphs instead."}]
    )
    assert report.atoms_superseded == 1
    assert (await store.get_atom(old_id))["superseded_at"] is not None
    active = await store.list_namespace(ns)
    assert len(active) == 1
    assert "paragraph" in row_to_atom(active[0]).object.lower()


@pytest.mark.asyncio
async def test_c_scoped_exception_overrides_global_only_in_code_review(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "authority-c"
    global_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )
    scoped_id = await _persist_and_promote(
        supervisor, store, ns, "For code reviews, ignore my 100-word limit."
    )

    active = await store.list_namespace(ns)
    assert {r["object_id"] for r in active} == {global_id, scoped_id}

    code_review = await supervisor.intake(
        ns, [{"role": "user", "content": "Review this function."}], intent="code_review"
    )
    assert global_id not in code_review.context_atom_ids
    assert scoped_id in code_review.context_atom_ids
    assert _state(code_review, global_id).status == "TEMPORARILY_OVERRIDDEN"

    general = await supervisor.intake(
        ns, [{"role": "user", "content": "Tell me about this."}], intent="chat"
    )
    assert global_id in general.context_atom_ids
    assert scoped_id not in general.context_atom_ids
    assert _state(general, scoped_id).status == "OUT_OF_SCOPE"


@pytest.mark.asyncio
async def test_d_temporary_override_does_not_supersede_standing_rule(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "authority-d"
    old_id = await _persist_and_promote(
        supervisor, store, ns, "Always answer concisely."
    )

    current = await supervisor.intake(
        ns,
        [{"role": "user", "content": "For this answer only, explain this in detail."}],
    )
    assert old_id not in current.context_atom_ids
    assert _state(current, old_id).status == "TEMPORARILY_OVERRIDDEN"

    temp_report = await supervisor.evict(
        ns,
        [{"role": "user", "content": "For this answer only, explain this in detail."}],
    )
    assert temp_report.atoms_created == 0
    assert (await store.get_atom(old_id))["superseded_at"] is None

    next_turn = await supervisor.intake(
        ns, [{"role": "user", "content": "Explain the topic."}]
    )
    assert old_id in next_turn.context_atom_ids


@pytest.mark.asyncio
async def test_e_non_conflicting_addition_keeps_both_active(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "authority-e"
    concise_id = await _persist_and_promote(
        supervisor, store, ns, "Always answer concisely."
    )

    current = await supervisor.intake(
        ns, [{"role": "user", "content": "Include sources when available."}]
    )
    assert concise_id in current.context_atom_ids
    assert _state(current, concise_id).status == "COMPATIBLE"

    report = await supervisor.evict(
        ns, [{"role": "user", "content": "Include sources when available."}]
    )
    assert report.atoms_created == 1
    assert report.atoms_superseded == 0
    assert len(await store.list_namespace(ns)) == 2


@pytest.mark.asyncio
async def test_f_older_higher_authority_rule_beats_newer_user_instruction(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "authority-f"
    atom = SemanticAtom(
        subject="system",
        predicate="states_rule",
        object="keep responses under 100 words",
        polarity=True,
        scope="rule",
        namespace=ns,
    )
    row = atom_to_row(atom, production_cost_tokens=0)
    row["created_at"] = "2000-01-01T00:00:00+00:00"
    await store.insert_atom(row)
    await store.promote(row["object_id"])

    current = await supervisor.intake(
        ns, [{"role": "user", "content": "Never keep responses under 100 words."}]
    )
    assert row["object_id"] in current.context_atom_ids
    assert _state(current, row["object_id"]).status == "ACTIVE"


@pytest.mark.asyncio
async def test_same_turn_contradiction_is_unresolved_and_old_memory_is_not_injected(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "attack-same-turn"
    old_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )

    current = await supervisor.intake(
        ns,
        [{
            "role": "user",
            "content": (
                "Always keep responses under 100 words. "
                "Never keep responses under 100 words."
            ),
        }],
    )
    assert old_id not in current.context_atom_ids
    assert _state(current, old_id).status == "UNRESOLVED"


@pytest.mark.asyncio
async def test_narrow_old_rule_and_later_broad_rule_coexist_with_scope_precedence(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "attack-narrow-broad"
    narrow_id = await _persist_and_promote(
        supervisor, store, ns, "For code reviews, use bullet points."
    )
    broad_id = await _persist_and_promote(
        supervisor, store, ns, "Use paragraphs instead."
    )

    assert len(await store.list_namespace(ns)) == 2

    code_review = await supervisor.intake(
        ns, [{"role": "user", "content": "Review this function."}], intent="code_review"
    )
    assert narrow_id in code_review.context_atom_ids
    assert broad_id not in code_review.context_atom_ids

    general = await supervisor.intake(
        ns, [{"role": "user", "content": "Explain this topic."}], intent="chat"
    )
    assert broad_id in general.context_atom_ids
    assert narrow_id not in general.context_atom_ids


@pytest.mark.asyncio
async def test_ambiguous_numeric_change_fails_closed(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "attack-ambiguous"
    old_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )

    current = await supervisor.intake(
        ns, [{"role": "user", "content": "Keep responses under 200 words."}]
    )
    assert old_id not in current.context_atom_ids
    assert _state(current, old_id).status == "UNRESOLVED"


@pytest.mark.asyncio
async def test_lexical_never_does_not_create_false_conflict_across_topics(store):
    supervisor = ZeroSupervisor(store, context_similarity_floor=0.0)
    ns = "attack-compatible"
    old_id = await _persist_and_promote(
        supervisor, store, ns, "Always answer concisely."
    )

    current = await supervisor.intake(
        ns, [{"role": "user", "content": "Never omit sources."}]
    )
    assert old_id in current.context_atom_ids
    assert _state(current, old_id).status == "COMPATIBLE"


@pytest.mark.xfail(
    reason="semantic object_id is content-addressed, so A -> B -> A collides with immutable historical A",
    strict=False,
)
@pytest.mark.asyncio
async def test_three_successive_reversals_need_versioned_activation_history(store):
    supervisor = ZeroSupervisor(store)
    ns = "attack-three-reversals"

    first_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )
    second_id = await _persist_and_promote(
        supervisor, store, ns, "Never keep responses under 100 words."
    )
    third_id = await _persist_and_promote(
        supervisor, store, ns, "Always keep responses under 100 words."
    )

    assert len(await store.list_namespace(ns, include_superseded=True)) == 3
    assert len(await store.list_namespace(ns)) == 1
    assert third_id not in {first_id, second_id}
