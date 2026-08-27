"""
CNSStore — the persistent truth/state layer (spec section 8-9, 12).

Async, SQLite-backed (via aiosqlite), one connection per store instance.
Day-One deliberately avoids a fingerprint column, a vector index, or any
other addition to the frozen schema: candidate lookup for dedup scans a
namespace's rows in Python (`list_namespace`) and lets `zerofold.dedup`
narrow with the Bloom filter and similarity backend before doing anything
expensive. That is the documented Day-One tradeoff (see README) — a real
index is a scale-triggered upgrade, not a schema change.
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiosqlite

from zerofold.atoms import SemanticAtom
from zerofold.cns.schema import ALL_STATEMENTS


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def atom_to_row(
    atom: SemanticAtom,
    *,
    production_cost_tokens: int,
    production_cost_usd: float = 0.0,
    dedup_cost_tokens: int = 0,
    expires_at: Optional[str] = None,
    supersedes_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a fresh cns_atom row for an atom that doesn't exist yet."""
    value = {
        "subject": atom.subject,
        "predicate": atom.predicate,
        "object": atom.object,
        "polarity": atom.polarity,
        "scope": atom.scope,
        "time": atom.time,
        "confidence": atom.confidence,
    }
    return {
        "object_id": atom.object_id(),
        "namespace": atom.namespace,
        "tier": "episodic",
        "value": json.dumps(value),
        "flags": atom.flags,
        "source_refs": json.dumps(atom.source_refs),
        "retrieval_count": 0,
        "reinforcement_count": 0,
        "tokens_saved_total": 0,
        "production_cost_tokens": production_cost_tokens,
        "dedup_cost_tokens": dedup_cost_tokens,
        "production_cost_usd": production_cost_usd,
        "retrieval_savings_usd": 0.0,
        "payback_count": None,
        "payback_achieved": 0,
        "last_accessed": None,
        "last_confirmed": None,
        "expires_at": expires_at,
        "created_at": now_iso(),
        "supersedes_id": supersedes_id,
        "superseded_at": None,
    }


def row_to_atom(row: Dict[str, Any]) -> SemanticAtom:
    v = json.loads(row["value"])
    return SemanticAtom(
        subject=v["subject"],
        predicate=v["predicate"],
        object=v["object"],
        polarity=v["polarity"],
        scope=v["scope"],
        time=v.get("time"),
        confidence=v.get("confidence", 1.0),
        source_refs=json.loads(row["source_refs"]) if row.get("source_refs") else [],
        flags=row.get("flags", 0),
        namespace=row["namespace"],
    )


class CNSStore:
    def __init__(self, path: str = ":memory:") -> None:
        self.path = path
        self._conn: Optional[aiosqlite.Connection] = None
        self._lock = asyncio.Lock()

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        for stmt in ALL_STATEMENTS:
            await self._conn.execute(stmt)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("CNSStore not connected — call connect() first")
        return self._conn

    async def __aenter__(self) -> "CNSStore":
        await self.connect()
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ---------------- Atom CRUD ----------------

    async def insert_atom(self, row: Dict[str, Any]) -> None:
        cols = list(row.keys())
        placeholders = ",".join("?" for _ in cols)
        await self.conn.execute(
            f"INSERT INTO cns_atom ({','.join(cols)}) VALUES ({placeholders})",  # nosec B608 - cols are our own dict keys
            tuple(row.values()),
        )
        await self.conn.commit()

    async def get_atom(self, object_id: str) -> Optional[Dict[str, Any]]:
        async with self.conn.execute(
            "SELECT * FROM cns_atom WHERE object_id=?", (object_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def list_namespace(
        self, namespace: str, tier: Optional[str] = None, include_superseded: bool = False
    ) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM cns_atom WHERE namespace=?"
        args: List[Any] = [namespace]
        if tier is not None:
            sql += " AND tier=?"
            args.append(tier)
        if not include_superseded:
            sql += " AND superseded_at IS NULL"
        async with self.conn.execute(sql, tuple(args)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]

    # ---------------- Reinforcement / supersession ----------------

    async def reinforce(self, object_id: str) -> Optional[Dict[str, Any]]:
        await self.conn.execute(
            "UPDATE cns_atom SET reinforcement_count = reinforcement_count + 1, "
            "last_confirmed = ? WHERE object_id = ?",
            (now_iso(), object_id),
        )
        await self.conn.commit()
        return await self.get_atom(object_id)

    async def promote(self, object_id: str) -> None:
        await self.conn.execute(
            "UPDATE cns_atom SET tier='long_term' WHERE object_id=?", (object_id,)
        )
        await self.conn.commit()

    async def supersede(
        self, old_object_id: str, *, decay_seconds: int = 3600
    ) -> None:
        """Mark `old_object_id` superseded. Historical truth is not deleted
        (spec section 7) — it's flagged and given an accelerated expiry."""
        from zerofold.atoms import FLAG_SUPERSEDED

        accelerated_expiry = (
            datetime.now(timezone.utc) + timedelta(seconds=decay_seconds)
        ).isoformat()
        await self.conn.execute(
            "UPDATE cns_atom SET superseded_at=?, flags = flags | ?, expires_at=? "
            "WHERE object_id=?",
            (now_iso(), FLAG_SUPERSEDED, accelerated_expiry, old_object_id),
        )
        await self.conn.commit()

    # ---------------- Live ROI / payback (Zero Ledger substrate) ----------------

    async def record_retrieval(
        self, object_id: str, *, avoided_tokens: int, avoided_cost_usd: float
    ) -> Optional[Dict[str, Any]]:
        """Atomically bump retrieval counters and, if this call crosses the
        payback threshold for the first time, freeze `payback_count` at the
        current retrieval_count. `payback_count` is never rewritten once set
        (spec section 9)."""
        async with self._lock:
            await self.conn.execute(
                """
                UPDATE cns_atom SET
                    retrieval_count = retrieval_count + 1,
                    tokens_saved_total = tokens_saved_total + ?,
                    retrieval_savings_usd = retrieval_savings_usd + ?,
                    last_accessed = ?,
                    payback_count = CASE
                        WHEN payback_achieved = 0
                             AND (tokens_saved_total + ?) >= (production_cost_tokens + dedup_cost_tokens)
                        THEN retrieval_count + 1
                        ELSE payback_count
                    END,
                    payback_achieved = CASE
                        WHEN payback_achieved = 0
                             AND (tokens_saved_total + ?) >= (production_cost_tokens + dedup_cost_tokens)
                        THEN 1
                        ELSE payback_achieved
                    END
                WHERE object_id = ?
                """,
                (avoided_tokens, avoided_cost_usd, now_iso(), avoided_tokens, avoided_tokens, object_id),
            )
            await self.conn.commit()
        return await self.get_atom(object_id)

    # ---------------- TTL sweep ----------------

    async def sweep_expired(self) -> int:
        """Delete expired, non-long-term atoms. Returns rows removed."""
        cur = await self.conn.execute(
            "DELETE FROM cns_atom WHERE expires_at IS NOT NULL AND expires_at < ? "
            "AND tier != 'long_term'",
            (now_iso(),),
        )
        await self.conn.commit()
        return cur.rowcount or 0

    # ---------------- Namespace policy ----------------

    async def get_namespace_policy(self, namespace: str) -> Dict[str, Any]:
        async with self.conn.execute(
            "SELECT * FROM cns_namespace_policy WHERE namespace=?", (namespace,)
        ) as cur:
            row = await cur.fetchone()
        if row:
            return dict(row)
        return {
            "namespace": namespace,
            "extraction_threshold": 0.5,
            "promotion_reinforce_n": 2,
            "avg_payback_achievers": None,
            "payback_rate": None,
            "total_atoms_created": 0,
            "updated_at": None,
        }

    async def upsert_namespace_policy(self, namespace: str, **fields: Any) -> None:
        current = await self.get_namespace_policy(namespace)
        current.update(fields)
        current["updated_at"] = now_iso()
        await self.conn.execute(
            """
            INSERT INTO cns_namespace_policy
                (namespace, extraction_threshold, promotion_reinforce_n,
                 avg_payback_achievers, payback_rate, total_atoms_created, updated_at)
            VALUES (:namespace, :extraction_threshold, :promotion_reinforce_n,
                    :avg_payback_achievers, :payback_rate, :total_atoms_created, :updated_at)
            ON CONFLICT(namespace) DO UPDATE SET
                extraction_threshold = excluded.extraction_threshold,
                promotion_reinforce_n = excluded.promotion_reinforce_n,
                avg_payback_achievers = excluded.avg_payback_achievers,
                payback_rate = excluded.payback_rate,
                total_atoms_created = excluded.total_atoms_created,
                updated_at = excluded.updated_at
            """,
            current,
        )
        await self.conn.commit()

    async def recompute_namespace_policy(self, namespace: str) -> Dict[str, Any]:
        """Closed learning loop step (spec section 10): recompute
        avg_payback_achievers and payback_rate from actual atom outcomes."""
        async with self.conn.execute(
            "SELECT COUNT(*) AS total FROM cns_atom WHERE namespace=?", (namespace,)
        ) as cur:
            total_row = await cur.fetchone()
            total = total_row["total"] if total_row else 0

        async with self.conn.execute(
            "SELECT COUNT(*) AS achievers, AVG(payback_count) AS avg_payback "
            "FROM cns_atom WHERE namespace=? AND payback_achieved=1",
            (namespace,),
        ) as cur:
            row = await cur.fetchone()
            achievers = row["achievers"] if row else 0
            avg_payback = row["avg_payback"] if row else None

        payback_rate = (achievers / total) if total > 0 else None
        await self.upsert_namespace_policy(
            namespace,
            avg_payback_achievers=avg_payback,
            payback_rate=payback_rate,
            total_atoms_created=total,
        )
        return await self.get_namespace_policy(namespace)
