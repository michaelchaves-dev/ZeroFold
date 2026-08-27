from zerofold.atoms import SemanticAtom
from zerofold.language import ZeroLanguageCodec, ZeroLanguageError
import pytest


def test_fold_unfold_roundtrip():
    codec = ZeroLanguageCodec()
    atom = SemanticAtom(
        subject="user", predicate="prefers", object="dark mode",
        polarity=True, scope="preference", confidence=0.75, namespace="acme",
    )
    line = codec.fold(atom)
    restored = codec.unfold(line)
    assert restored.subject == "user"
    assert restored.predicate == "prefers"
    assert restored.object == "dark mode"
    assert restored.polarity is True
    assert restored.scope == "preference"
    assert restored.confidence == pytest.approx(0.75)
    assert restored.namespace == "acme"


def test_repeated_terms_reuse_the_same_reference():
    codec = ZeroLanguageCodec()
    a1 = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    a2 = SemanticAtom(subject="user", predicate="prefers", object="light mode", namespace="acme")
    line1 = codec.fold(a1)
    line2 = codec.fold(a2)
    # "user", "prefers", "acme" are shared -> same reference tokens in both lines
    subj1 = line1.split("|")[0]
    subj2 = line2.split("|")[0]
    assert subj1 == subj2
    # Dictionary grows only for genuinely new terms (user, prefers, dark mode,
    # preference(default scope), "", 1(confidence-ish), acme -> then +1 for "light mode")
    assert len(codec.export_dictionary()) < 2 * 8  # far fewer than two fully-separate atoms


def test_export_and_load_dictionary_roundtrip():
    codec = ZeroLanguageCodec()
    atom = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="acme")
    line = codec.fold(atom)
    terms = codec.export_dictionary()

    restored_codec = ZeroLanguageCodec.load_dictionary(terms)
    restored = restored_codec.unfold(line)
    assert restored.subject == atom.subject
    assert restored.object == atom.object


def test_unfold_rejects_malformed_line():
    codec = ZeroLanguageCodec()
    with pytest.raises(ZeroLanguageError):
        codec.unfold("not|enough|fields")


def test_unfold_rejects_unresolvable_reference():
    codec = ZeroLanguageCodec()
    with pytest.raises(ZeroLanguageError):
        codec.resolve("@99")
