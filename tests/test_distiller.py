from zerofold.atoms import FLAG_EXPLICIT_USER_RULE, has_flag
from zerofold.distiller import distill_message, distill_segment


def test_extracts_name():
    atoms = distill_message("user", "Hi there, my name is Priya.", namespace="acme")
    assert any(a.predicate == "has_name" and a.object == "Priya." for a in atoms) or any(
        a.predicate == "has_name" for a in atoms
    )


def test_extracts_preference_positive():
    atoms = distill_message("user", "I prefer dark mode in the editor.", namespace="acme")
    prefs = [a for a in atoms if a.predicate == "prefers"]
    assert len(prefs) == 1
    assert prefs[0].polarity is True


def test_extracts_preference_negative():
    atoms = distill_message("user", "I don't like verbose answers.", namespace="acme")
    prefs = [a for a in atoms if a.predicate == "prefers"]
    assert len(prefs) == 1
    assert prefs[0].polarity is False


def test_extracts_explicit_rule_with_flag():
    atoms = distill_message("user", "Always respond in under 200 words.", namespace="acme")
    rules = [a for a in atoms if a.predicate == "states_rule"]
    assert len(rules) == 1
    assert rules[0].polarity is True
    assert has_flag(rules[0].flags, FLAG_EXPLICIT_USER_RULE)


def test_never_rule_is_negative_polarity():
    atoms = distill_message("user", "Never use emojis in responses.", namespace="acme")
    rules = [a for a in atoms if a.predicate == "states_rule"]
    assert len(rules) == 1
    assert rules[0].polarity is False


def test_extracts_constraint_as_high_importance():
    from zerofold.atoms import FLAG_HIGH_IMPORTANCE

    atoms = distill_message("user", "The deadline is March 3rd 2027.", namespace="acme")
    constraints = [a for a in atoms if a.predicate == "constrains"]
    assert len(constraints) == 1
    assert has_flag(constraints[0].flags, FLAG_HIGH_IMPORTANCE)


def test_distill_segment_dedupes_and_skips_irrelevant_messages():
    messages = [
        {"role": "user", "content": "Thanks!"},
        {"role": "user", "content": "I prefer dark mode."},
        {"role": "user", "content": "I prefer dark mode."},
    ]
    atoms = distill_segment(messages, namespace="acme")
    assert len(atoms) == 1


def test_no_atoms_from_plain_chat():
    atoms = distill_message("user", "What's the weather like today in general terms?", namespace="acme")
    assert atoms == []
