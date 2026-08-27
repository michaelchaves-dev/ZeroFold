"""
Local similarity — candidate generation for the Navigation Layer.

This is deliberately swappable. Day-One ships a pure-Python, dependency-free
term-frequency cosine similarity so ZeroFold never forces an embedding model
or a vector database on a caller who just wants dedup working. A real
embedding backend is a drop-in replacement: implement `SimilarityBackend`
and pass it to `DedupEngine` — nothing else in the pipeline changes.

Similarity is a *candidate generator*, never a truth decision (spec section
7/12): it ranks plausible matches, and the polarity/constraint gate in
dedup.py is what actually decides reinforce/supersede/create.
"""

from __future__ import annotations

import re
from typing import Dict, List, Protocol

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


def _term_freq(tokens: List[str]) -> Dict[str, float]:
    tf: Dict[str, float] = {}
    for t in tokens:
        tf[t] = tf.get(t, 0.0) + 1.0
    return tf


def cosine_similarity(a: str, b: str) -> float:
    """Cosine similarity over raw term-frequency vectors, in [0.0, 1.0].
    Two empty strings are defined as similarity 0.0 (nothing to match)."""
    ta, tb = tokenize(a), tokenize(b)
    if not ta or not tb:
        return 0.0
    fa, fb = _term_freq(ta), _term_freq(tb)
    shared = set(fa) & set(fb)
    dot = sum(fa[t] * fb[t] for t in shared)
    if dot == 0.0:
        return 0.0
    mag_a = sum(v * v for v in fa.values()) ** 0.5
    mag_b = sum(v * v for v in fb.values()) ** 0.5
    # Clamp: floating-point rounding can push an identical-vector score
    # fractionally past 1.0, which would violate the documented [0.0, 1.0] range.
    return min(1.0, dot / (mag_a * mag_b))


class SimilarityBackend(Protocol):
    def similarity(self, a: str, b: str) -> float:
        """Return a similarity score in [0.0, 1.0]. Higher = more similar."""
        ...


class LocalTextSimilarity:
    """Default `SimilarityBackend`: term-frequency cosine similarity.
    No model, no network call, no external dependency."""

    def similarity(self, a: str, b: str) -> float:
        return cosine_similarity(a, b)


def get_default_similarity_backend() -> SimilarityBackend:
    return LocalTextSimilarity()
