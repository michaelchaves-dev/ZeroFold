"""
Zero Codec — canonicalization and hashing.

Every piece of state ZeroFold keeps needs two independent hashes (spec
section 6):

  source_hash  — identifies the raw input a distillation came from, so the
                 same source is never reprocessed twice.
  object_id    — identifies a canonical distilled atom, so two different
                 sources that resolve to the same meaning collapse to one
                 object.

This module owns both, plus the stable JSON serialization they're built on.
No storage, no I/O — pure functions only.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def stable_json(value: Any) -> str:
    """Deterministic JSON encoding: sorted keys, no incidental whitespace."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def stable_hash(value: Any) -> str:
    """sha256 of the stable JSON encoding of `value`."""
    return hashlib.sha256(stable_json(value).encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """Canonical form used before hashing raw source text: collapse
    whitespace, trim, lowercase. This is a hashing normalization, not a
    display transform — never store this in place of the original text."""
    return " ".join(text.split()).strip().lower()


def source_hash(raw_source: str) -> str:
    """Hash of a raw source string (a message, a segment, a document chunk)
    used to detect exact reprocessing before any distillation work runs."""
    return hashlib.sha256(normalize_text(raw_source).encode("utf-8")).hexdigest()
