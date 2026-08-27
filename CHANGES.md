# Changes

## v0.1.0 — initial release

Day-One implementation of the frozen Zero Supervisor specification
(`docs/spec.html`), scoped to the load-bearing pieces called out in spec
section 20:

- **Zero Atoms + Zero Codec** (`zerofold.atoms`, `zerofold.codec`) — the
  canonical subject/predicate/object shape, stable hashing, and the
  fingerprint/object_id split that lets contradictions be found without
  being confused for duplicates.
- **Zero Language** (`zerofold.language`) — a reference-interning fold/unfold
  codec so repeated terms are never stored twice.
- **Navigation layer** (`zerofold.bloom`, `zerofold.similarity`) — a
  dependency-free Bloom filter and a pluggable similarity backend (defaults
  to pure-Python TF-cosine; swap in an embedding model without touching
  call sites).
- **CNS** (`zerofold.cns.store`) — the frozen `cns_atom` / `cns_namespace_policy`
  schema, async SQLite-backed, with atomic payback-crossing updates,
  supersession, TTL sweep, and namespace policy recompute.
- **Zero Ledger** (`zerofold.cns.ledger`) — ROI computation and the
  promotion rule (explicit user rule / reinforcement threshold / high
  importance + confirmed).
- **Relevance gate + Step Zero Distiller** (`zerofold.relevance`,
  `zerofold.distiller`) — deterministic, no-model-call extraction of facts,
  decisions, preferences, and constraints.
- **Fidelity gate** (`zerofold.fidelity`) — the RelAi Race: deterministic
  diff first, optional independent scorer second, fallback to raw on any
  failure.
- **Dedup engine** (`zerofold.dedup`) — Bloom precheck → fingerprint
  candidates → similarity → polarity gate → create/reinforce/supersede.
- **Zero Conveyor** (`zerofold.conveyor`) — the memory eviction pipeline
  tying the above together.
- **Complexity floor, output contracts, outbound validator**
  (`zerofold.complexity`, `zerofold.contracts`, `zerofold.outbound`) — a
  routing-tier estimate and post-response validation (completion,
  repetition, format, budget, unsupported-claim checks).
- **Zero Supervisor** (`zerofold.supervisor`) — the public facade:
  `intake()` / `evict()` / `outbound()`.

Explicitly deferred to scale-triggered follow-up work (spec section 20):
shared zstd dictionaries, string pool interning beyond Zero Language's
per-codec dictionary, a real trie, vector/ANN infrastructure, and any schema
migration that would add an indexed fingerprint column.

101 tests, `pytest -q` green on Python 3.9–3.12.
