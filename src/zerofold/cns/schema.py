"""
Frozen CNS schema (spec section 8). This table shape is a contract other
modules hash-check against implicitly (there is no fingerprint column by
design — see cns/store.py for why). Change it only with a migration, never
in place.
"""

from __future__ import annotations

CNS_ATOM_TABLE = """
CREATE TABLE IF NOT EXISTS cns_atom (
    object_id               TEXT PRIMARY KEY,
    namespace               TEXT NOT NULL,
    tier                    TEXT DEFAULT 'episodic',
    value                   BLOB,
    flags                   INTEGER DEFAULT 0,
    source_refs             TEXT,

    retrieval_count         INTEGER DEFAULT 0,
    reinforcement_count     INTEGER DEFAULT 0,

    tokens_saved_total      INTEGER DEFAULT 0,
    production_cost_tokens  INTEGER,
    dedup_cost_tokens       INTEGER DEFAULT 0,

    production_cost_usd     REAL,
    retrieval_savings_usd   REAL DEFAULT 0,

    payback_count           INTEGER,
    payback_achieved        INTEGER DEFAULT 0,

    last_accessed           TEXT,
    last_confirmed          TEXT,

    expires_at              TEXT,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP,

    supersedes_id           TEXT REFERENCES cns_atom(object_id),
    superseded_at           TEXT
)
"""

CNS_ATOM_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_atom_namespace ON cns_atom(namespace)",
    "CREATE INDEX IF NOT EXISTS idx_atom_tier ON cns_atom(tier)",
    "CREATE INDEX IF NOT EXISTS idx_atom_expires ON cns_atom(expires_at)",
    "CREATE INDEX IF NOT EXISTS idx_atom_supersedes ON cns_atom(supersedes_id)",
]

CNS_NAMESPACE_POLICY_TABLE = """
CREATE TABLE IF NOT EXISTS cns_namespace_policy (
    namespace               TEXT PRIMARY KEY,
    extraction_threshold    REAL DEFAULT 0.5,
    promotion_reinforce_n   INTEGER DEFAULT 2,
    avg_payback_achievers   REAL,
    payback_rate            REAL,
    total_atoms_created     INTEGER DEFAULT 0,
    updated_at              TEXT
)
"""

ALL_STATEMENTS = [CNS_ATOM_TABLE, *CNS_ATOM_INDEXES, CNS_NAMESPACE_POLICY_TABLE]

# Bitpacked flags — mirrored from zerofold.atoms for callers that only need
# the schema module (e.g. raw SQL tooling) without importing the dataclass.
FLAG_EXPLICIT_USER_RULE = 1 << 0
FLAG_CONFIRMED = 1 << 1
FLAG_HIGH_IMPORTANCE = 1 << 2
FLAG_SUPERSEDED = 1 << 3
