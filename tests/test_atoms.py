import pytest

from zerofold.atoms import FLAG_CONFIRMED, FLAG_EXPLICIT_USER_RULE, SemanticAtom, has_flag, set_flag


def test_object_id_stable_for_identical_atoms():
    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode")
    b = SemanticAtom(subject="User", predicate="Prefers", object="Dark Mode  ")
    assert a.object_id() == b.object_id()


def test_object_id_differs_on_polarity():
    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode", polarity=True)
    b = SemanticAtom(subject="user", predicate="prefers", object="dark mode", polarity=False)
    assert a.object_id() != b.object_id()
    # But they must share a fingerprint — that's how contradictions get found.
    assert a.fingerprint() == b.fingerprint()


def test_fingerprint_ignores_object_text():
    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode")
    b = SemanticAtom(subject="user", predicate="prefers", object="light mode")
    assert a.fingerprint() == b.fingerprint()
    assert a.object_id() != b.object_id()


def test_fingerprint_differs_across_namespace():
    a = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="ns-a")
    b = SemanticAtom(subject="user", predicate="prefers", object="dark mode", namespace="ns-b")
    assert a.fingerprint() != b.fingerprint()


def test_rejects_empty_fields():
    with pytest.raises(ValueError):
        SemanticAtom(subject="", predicate="prefers", object="x")


def test_rejects_out_of_range_confidence():
    with pytest.raises(ValueError):
        SemanticAtom(subject="user", predicate="prefers", object="x", confidence=1.5)


def test_flag_helpers():
    flags = set_flag(0, FLAG_EXPLICIT_USER_RULE)
    assert has_flag(flags, FLAG_EXPLICIT_USER_RULE)
    assert not has_flag(flags, FLAG_CONFIRMED)


def test_with_flag_returns_new_atom():
    a = SemanticAtom(subject="user", predicate="prefers", object="x")
    b = a.with_flag(FLAG_CONFIRMED)
    assert a.flags == 0
    assert has_flag(b.flags, FLAG_CONFIRMED)
