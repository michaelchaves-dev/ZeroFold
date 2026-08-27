"""
Zero Language — a compact, reference-based intermediate representation for
Zero Atoms (spec section 14).

The goal is not "English with vowels removed" — it's a machine-oriented
encoding that never stores the same string twice within a codec's lifetime.
The first time a term (a subject, predicate, object, or scope) appears it is
interned and written out in full; every later occurrence folds to a short
`@<n>` reference. `unfold()` reverses this losslessly using the same
dictionary.

A codec is scoped to whatever the caller wants to share a dictionary across
(typically one per CNS namespace). It is plain data — `export_dictionary()`
/ `load_dictionary()` let a host persist and restore it alongside the atoms
it encodes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

from zerofold.atoms import SemanticAtom

_FIELD_SEP = "|"
_POLARITY_TRUE = "+"
_POLARITY_FALSE = "-"


class ZeroLanguageError(ValueError):
    pass


@dataclass
class ZeroLanguageCodec:
    """Interning dictionary + fold/unfold for SemanticAtom <-> compact text."""

    _terms: List[str]
    _index: Dict[str, int]

    def __init__(self) -> None:
        self._terms = []
        self._index = {}

    def intern(self, term: str) -> str:
        """Return a stable `@<n>` reference for `term`, registering it if new."""
        if term in self._index:
            return f"@{self._index[term]}"
        n = len(self._terms)
        self._terms.append(term)
        self._index[term] = n
        return f"@{n}"

    def resolve(self, ref: str) -> str:
        if not ref.startswith("@"):
            raise ZeroLanguageError(f"not a reference: {ref!r}")
        try:
            n = int(ref[1:])
            return self._terms[n]
        except (ValueError, IndexError) as e:
            raise ZeroLanguageError(f"unresolvable reference: {ref!r}") from e

    def fold(self, atom: SemanticAtom) -> str:
        """Encode an atom as a compact reference-based line."""
        parts = [
            self.intern(atom.subject),
            self.intern(atom.predicate),
            _POLARITY_TRUE if atom.polarity else _POLARITY_FALSE,
            self.intern(atom.object),
            self.intern(atom.scope),
            self.intern(atom.time) if atom.time else "",
            f"{atom.confidence:.4g}",
            self.intern(atom.namespace),
        ]
        return _FIELD_SEP.join(parts)

    def unfold(self, line: str) -> SemanticAtom:
        """Decode a line produced by `fold()` back into a SemanticAtom.
        Loses nothing except `flags`/`source_refs`, which are structural
        bookkeeping, not part of the folded meaning."""
        fields = line.split(_FIELD_SEP)
        if len(fields) != 8:
            raise ZeroLanguageError(f"malformed Zero Language line: {line!r}")
        subj_ref, pred_ref, pol, obj_ref, scope_ref, time_ref, conf, ns_ref = fields
        if pol not in (_POLARITY_TRUE, _POLARITY_FALSE):
            raise ZeroLanguageError(f"malformed polarity marker: {pol!r}")
        return SemanticAtom(
            subject=self.resolve(subj_ref),
            predicate=self.resolve(pred_ref),
            object=self.resolve(obj_ref),
            polarity=(pol == _POLARITY_TRUE),
            scope=self.resolve(scope_ref),
            time=self.resolve(time_ref) if time_ref else None,
            confidence=float(conf),
            namespace=self.resolve(ns_ref),
        )

    def export_dictionary(self) -> List[str]:
        """Terms in interning order — index in this list is the `@<n>` ref."""
        return list(self._terms)

    @classmethod
    def load_dictionary(cls, terms: List[str]) -> "ZeroLanguageCodec":
        codec = cls()
        codec._terms = list(terms)
        codec._index = {t: i for i, t in enumerate(codec._terms)}
        return codec

    def fold_batch(self, atoms: List[SemanticAtom]) -> Tuple[List[str], List[str]]:
        """Fold many atoms against one dictionary. Returns (lines, dictionary)."""
        lines = [self.fold(a) for a in atoms]
        return lines, self.export_dictionary()
