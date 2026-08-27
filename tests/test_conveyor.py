import pytest

from zerofold.conveyor import MemoryEvictionConveyor


@pytest.mark.asyncio
async def test_process_creates_atoms_from_relevant_messages(store):
    conveyor = MemoryEvictionConveyor(store)
    messages = [
        {"role": "user", "content": "Thanks for the help!"},
        {"role": "user", "content": "My name is Priya and I always want concise answers."},
        {"role": "user", "content": "The deadline is 2027-03-04."},
    ]
    report = await conveyor.process("acme", messages)
    assert report.messages_considered == 3
    assert report.messages_kept == 2
    assert report.atoms_created >= 2
    assert report.atoms_reinforced == 0
    assert report.atoms_superseded == 0

    stored = await store.list_namespace("acme")
    assert len(stored) == report.atoms_created


@pytest.mark.asyncio
async def test_process_reinforces_on_repeat_conversation(store):
    conveyor = MemoryEvictionConveyor(store)
    messages = [{"role": "user", "content": "Always keep answers under 100 words."}]

    first = await conveyor.process("acme", messages)
    assert first.atoms_created == 1

    second = await conveyor.process("acme", messages)
    assert second.atoms_created == 0
    assert second.atoms_reinforced == 1


@pytest.mark.asyncio
async def test_process_supersedes_on_contradiction(store):
    conveyor = MemoryEvictionConveyor(store)
    first = await conveyor.process("acme", [{"role": "user", "content": "I prefer dark mode."}])
    assert first.atoms_created == 1

    second = await conveyor.process("acme", [{"role": "user", "content": "I don't like dark mode."}])
    assert second.atoms_superseded == 1

    active = await store.list_namespace("acme")
    assert len(active) == 1  # old one is superseded, filtered out of the active view


@pytest.mark.asyncio
async def test_process_with_no_relevant_messages_is_a_noop(store):
    conveyor = MemoryEvictionConveyor(store)
    report = await conveyor.process("acme", [{"role": "assistant", "content": "Sure thing!"}])
    assert report.messages_kept == 0
    assert report.atoms_created == 0
    assert await store.list_namespace("acme") == []
