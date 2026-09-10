"""Adversarial semantic-fidelity suite.

Improvement #1: compressed/reconstructed content may be shorter, but it
cannot change polarity, authority, scope, entity, quantity, or temporal
meaning. These cases exist to catch the reproduced "Never" inversion and
to try to break the fix (count collapse, double negation, operator
substitution, unextracted only/except/unless/may).
"""

from zerofold.atoms import SemanticAtom, render_claim
from zerofold.distiller import distill_message
from zerofold.fidelity import FidelityGate, semantic_diff


def _reconstruct(source: str) -> str:
    atoms = distill_message("user", source, namespace="acme")
    return " ".join(render_claim(a) for a in atoms)


def _assert_preserved(source: str) -> None:
    atoms = distill_message("user", source, namespace="acme")
    assert atoms, f"expected at least one atom for {source!r}"
    rendered = " ".join(render_claim(a) for a in atoms)
    verdict = semantic_diff(source, rendered)
    assert verdict.ok, (
        f"semantic fidelity failed for {source!r}\n"
        f"  rendered: {rendered!r}\n"
        f"  missing: {verdict.missing_from_candidate}\n"
        f"  atoms: {[(a.predicate, a.object, a.polarity) for a in atoms]}"
    )


def test_reproduced_never_failure_is_gone():
    """The original bug: distiller dropped 'Never', reconstruction inverted
    the rule to 'use emojis in responses'."""
    source = "Never use emojis in responses."
    atoms = distill_message("user", source, namespace="acme")
    assert len(atoms) == 1
    atom = atoms[0]
    rendered = render_claim(atom)
    assert atom.polarity is False
    assert "never" in atom.object.lower() or "not" in rendered.lower()
    inverted = "user states rule use emojis in responses"
    assert inverted not in rendered.lower()
    assert semantic_diff(source, rendered).ok
    assert not semantic_diff(source, inverted).ok


def test_never_drop_fails_the_invariant():
    source = "Never use emojis in responses."
    dropped = "use emojis in responses."
    verdict = semantic_diff(source, dropped)
    assert verdict.ok is False
    assert any("negations" in m for m in verdict.missing_from_candidate)


def test_never_say_never_does_not_collapse_count():
    """Bag-of-words {never} hid this: dropping the outer operator left an
    inner 'never' and the old set-based gate said ok."""
    source = "please never say never in marketing copy."
    collapsed = "say never in marketing copy."
    assert semantic_diff(source, collapsed).ok is False
    _assert_preserved(source)


def test_gate_rejects_never_drop_without_recompress():
    gate = FidelityGate()
    result = gate.evaluate(
        "Never use emojis in responses.",
        "use emojis in responses.",
    )
    assert result.used_compressed is False
    assert result.dispatch_text == "Never use emojis in responses."


def test_always_authority_survives():
    source = "Always respond in under 200 words."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "always" in rendered.lower()
    assert "200" in rendered


def test_always_drop_fails_the_invariant():
    source = "Always respond in under 200 words."
    dropped = "respond in under 200 words."
    verdict = semantic_diff(source, dropped)
    assert verdict.ok is False
    assert any("authority:always" in m for m in verdict.missing_from_candidate)


def test_should_never_has_negative_polarity():
    source = "You should never use emojis."
    _assert_preserved(source)
    atoms = distill_message("user", source, namespace="acme")
    rendered = " ".join(render_claim(a) for a in atoms)
    assert "never" in rendered.lower()
    assert any(a.polarity is False for a in atoms) or "never" in rendered.lower()


def test_must_not_is_a_prohibition():
    source = "Must not exceed 500 dollars."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "500" in rendered
    assert "not" in rendered.lower() or "never" in rendered.lower()
    assert any(a.polarity is False for a in distill_message("user", source, namespace="acme"))


def test_negative_preference_does_not_invert():
    source = "I don't like verbose answers."
    _assert_preserved(source)
    atoms = distill_message("user", source, namespace="acme")
    prefs = [a for a in atoms if a.predicate == "prefers"]
    assert prefs
    assert prefs[0].polarity is False
    rendered = render_claim(prefs[0])
    assert "not" in rendered.lower() or "don't" in rendered.lower() or "never" in rendered.lower()
    assert rendered.lower() != "user prefers verbose answers"


def test_only_scope_is_not_dropped():
    source = "Only admins may deploy to production."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "only" in rendered.lower()
    assert "may" in rendered.lower()


def test_except_scope_is_not_dropped():
    source = "You may share the report except on weekends."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "except" in rendered.lower()
    assert "may" in rendered.lower()


def test_unless_scope_is_not_dropped():
    source = "Do not deploy unless tests pass."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "unless" in rendered.lower()
    assert "not" in rendered.lower() or "never" in rendered.lower() or "don't" in rendered.lower()


def test_may_permission_is_not_dropped():
    source = "Contractors may view the dashboard."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "may" in rendered.lower()


def test_quantity_survives():
    source = "No more than 3 retries."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "3" in rendered
    verdict = semantic_diff(source, "No more than retries.")
    assert verdict.ok is False
    assert any("numbers:3" in m for m in verdict.missing_from_candidate)


def test_name_survives():
    source = "Hi there, my name is Priya."
    _assert_preserved(source)
    atoms = distill_message("user", source, namespace="acme")
    assert any(a.predicate == "has_name" and "Priya" in a.object for a in atoms)


def test_date_survives():
    source = "The deadline is 2027-03-04."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "2027-03-04" in rendered
    verdict = semantic_diff(source, "The deadline is soon.")
    assert verdict.ok is False
    assert any("dates:" in m for m in verdict.missing_from_candidate)


def test_temporal_after_survives():
    source = "Priya cannot access payroll after 2027-03-04."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "after" in rendered.lower()
    assert "2027-03-04" in rendered
    assert "cannot" in rendered.lower() or "not" in rendered.lower() or "never" in rendered.lower()


def test_two_rules_in_one_message_keep_both_operators():
    source = "Never use emojis in responses. Always be brief please."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "never" in rendered.lower()
    assert "always" in rendered.lower()


def test_never_to_not_substitution_is_allowed_for_polarity():
    """Shorter reconstruction may paraphrase never → not. Meaning holds."""
    source = "Never use emojis in responses."
    paraphrased = "Do not use emojis in responses."
    assert semantic_diff(source, paraphrased).ok


def test_introducing_negation_into_affirmative_fails():
    source = "Always keep replies under 100 words."
    flipped = "Never keep replies under 100 words."
    assert semantic_diff(source, flipped).ok is False
    assert any("negations" in m for m in semantic_diff(source, flipped).missing_from_candidate)


def test_render_claim_does_not_double_negate():
    atom = SemanticAtom(
        subject="user",
        predicate="states_rule",
        object="Never use emojis in responses",
        polarity=False,
        scope="rule",
        namespace="acme",
    )
    rendered = render_claim(atom)
    assert "not never" not in rendered.lower()
    assert "never" in rendered.lower()


def test_render_claim_surfaces_polarity_when_object_has_no_operator():
    atom = SemanticAtom(
        subject="user",
        predicate="prefers",
        object="verbose answers",
        polarity=False,
        scope="preference",
        namespace="acme",
    )
    rendered = render_claim(atom)
    assert "not" in rendered.lower()
    assert semantic_diff("I don't like verbose answers.", rendered).ok


def test_not_only_keeps_both_operators():
    source = "Not only admins can view this."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "not" in rendered.lower()
    assert "only" in rendered.lower()


def test_must_not_mid_clause_is_not_double_negated():
    """Break attempt: fallback object 'You must not…' has polarity False
    but does not *start* with a negation. Prefixing 'not' reversed the
    prohibition into permission."""
    source = "You must not, under any circumstances, share secrets."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "not you must not" not in rendered.lower()
    assert "must not" in rendered.lower()


def test_call_sarah_never_john_does_not_front_not():
    source = "Call Sarah, never John."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "not call sarah" not in rendered.lower()
    assert "never" in rendered.lower()
    assert "Sarah" in rendered
    assert "John" in rendered


def test_forbidden_prohibition_is_kept():
    source = "Forbidden: sharing customer PII."
    _assert_preserved(source)
    rendered = _reconstruct(source)
    assert "forbidden" in rendered.lower()
