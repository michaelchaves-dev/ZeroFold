"""
A runnable sketch of how a router (e.g. SubtracToken) would use ZeroFold.

This has no dependency on any specific router codebase — it stands in a
`fake_call_model()` function where a real router would call its provider
adapters. The point is to show the three integration points:

  1. before routing: ask ZeroSupervisor.intake() for a complexity floor and
     any durable context worth injecting;
  2. after the response comes back: validate it with ZeroSupervisor.outbound();
  3. whenever messages age out of the active context window: hand them to
     ZeroSupervisor.evict() so they become durable atoms instead of vanishing.

Run it with: python3 examples/router_integration_sketch.py
"""

from __future__ import annotations

import asyncio

from zerofold import CNSStore, ZeroSupervisor, contract_from_intent


def fake_call_model(messages: list[dict], min_quality_tier: int) -> str:
    """Stand-in for a real router's provider call. A real integration would
    filter its model catalog by `quality_tier >= min_quality_tier` before
    picking the cheapest option, then send `messages` (with any injected
    context) to that model."""
    return "Sure — I will keep future replies under 100 words, as requested."


async def handle_request(supervisor: ZeroSupervisor, namespace: str, messages: list[dict]) -> str:
    intent = "chat"  # a real router already has an intent classifier for this

    enrichment = await supervisor.intake(namespace, messages, intent=intent)
    if enrichment.context_snippet:
        messages = [{"role": "system", "content": enrichment.context_snippet}] + messages

    response_text = fake_call_model(messages, enrichment.min_quality_tier)

    contract = contract_from_intent(intent, recommended_max_tokens=200)
    outcome = supervisor.outbound(response_text, contract)
    if not outcome.passed:
        # A real integration would issue one targeted corrective call here,
        # e.g. re-prompting with `FIX:{violation.code}` — never a full regenerate.
        print("outbound violations:", outcome.violations)

    return response_text


async def main() -> None:
    store = CNSStore("zerofold_example.db")
    await store.connect()
    supervisor = ZeroSupervisor(store)
    namespace = "customer-42"

    conversation = [
        {"role": "user", "content": "Always keep your replies under 100 words for me."},
    ]
    reply = await handle_request(supervisor, namespace, conversation)
    print("assistant:", reply)

    # Later, once this conversation ages out of the active context window:
    report = await supervisor.evict(namespace, conversation)
    print("conveyor report:", report)

    # A later conversation now benefits from the durable rule, once it's
    # been reinforced enough to promote to long-term (see README for the
    # promotion policy).
    await store.close()


if __name__ == "__main__":
    asyncio.run(main())
