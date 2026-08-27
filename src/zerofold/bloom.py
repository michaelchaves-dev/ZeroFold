"""
Bloom filter — a membership *pre-check*, not a candidate retrieval system
(spec section 12).

False positives are acceptable and expected; false negatives are not. That
asymmetry is exactly the safe failure direction for dedup: "maybe present"
just means "go do the real lookup," while "definitely absent" means a write
can skip that lookup entirely.

Pure Python, no external dependencies — sized for the tens-of-thousands of
atoms a single namespace holds Day-One, not for web-scale sets.
"""

from __future__ import annotations

import hashlib
from typing import Iterable


class BloomFilter:
    def __init__(self, size_bits: int = 1 << 16, num_hashes: int = 4) -> None:
        if size_bits <= 0:
            raise ValueError("size_bits must be positive")
        if num_hashes <= 0:
            raise ValueError("num_hashes must be positive")
        self.size_bits = size_bits
        self.num_hashes = num_hashes
        self._bits = bytearray(-(-size_bits // 8))  # ceil division
        self._count = 0

    def __len__(self) -> int:
        """Number of `add()` calls made — not the true set cardinality."""
        return self._count

    def _slots(self, item: str) -> Iterable[int]:
        # Kirsch-Mitzenmacher: derive k hash values from two independent
        # hashes instead of running k separate hash functions.
        digest = hashlib.sha256(item.encode("utf-8")).digest()
        h1 = int.from_bytes(digest[:8], "big")
        h2 = int.from_bytes(digest[8:16], "big")
        for i in range(self.num_hashes):
            yield (h1 + i * h2) % self.size_bits

    def add(self, item: str) -> None:
        for bit in self._slots(item):
            self._bits[bit // 8] |= 1 << (bit % 8)
        self._count += 1

    def might_contain(self, item: str) -> bool:
        return all(self._bits[bit // 8] & (1 << (bit % 8)) for bit in self._slots(item))

    @classmethod
    def seeded_with(cls, items: Iterable[str], **kwargs) -> "BloomFilter":
        bf = cls(**kwargs)
        for item in items:
            bf.add(item)
        return bf
