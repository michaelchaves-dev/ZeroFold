"""Shared, provider-agnostic token estimate. Deliberately crude (chars/4) —
ZeroFold never assumes a specific tokenizer; a host with a real one can pass
its own estimator into any function here that accepts one."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
