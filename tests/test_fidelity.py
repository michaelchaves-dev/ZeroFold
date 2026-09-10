from zerofold.fidelity import FidelityGate, deterministic_diff, semantic_diff


def test_deterministic_diff_passes_when_nothing_lost():
    diff = deterministic_diff(
        "Sarah confirmed the refund of $500 on 2027-03-04.",
        "Sarah confirmed $500 refund, 2027-03-04.",
    )
    assert diff.ok


def test_deterministic_diff_flags_sentence_initial_capitalization_conservatively():
    """The entity check is intentionally naive: it can't tell a real proper
    noun from a capitalized sentence-opener. That means it over-flags rather
    than under-flags — the correct failure direction per the "preserve more
    under ambiguity" invariant, even though it costs some false positives."""
    diff = deterministic_diff(
        "Meet Sarah for the refund.",
        "Sarah gets a refund.",
    )
    assert not diff.ok
    assert "entities:Meet" in diff.missing_from_candidate


def test_deterministic_diff_flags_dropped_number():
    diff = deterministic_diff(
        "The invoice total is 4500 dollars.",
        "The invoice total is settled.",
    )
    assert not diff.ok
    assert any("numbers" in m for m in diff.missing_from_candidate)


def test_deterministic_diff_flags_dropped_negation():
    diff = deterministic_diff(
        "The user does not want emails.",
        "The user wants emails.",
    )
    assert not diff.ok
    assert any("negations" in m for m in diff.missing_from_candidate)


def test_deterministic_diff_flags_dropped_entity():
    diff = deterministic_diff("Contact Sarah about this.", "Contact them about this.")
    assert not diff.ok
    assert any("entities" in m for m in diff.missing_from_candidate)


def test_semantic_diff_flags_dropped_always():
    diff = semantic_diff("Always encrypt PII at rest.", "Encrypt PII at rest.")
    assert not diff.ok
    assert "authority:always" in diff.missing_from_candidate


def test_semantic_diff_flags_dropped_only():
    diff = semantic_diff("Only admins may deploy.", "admins may deploy.")
    assert not diff.ok
    assert "scope:only" in diff.missing_from_candidate


def test_semantic_diff_never_count_collapse():
    diff = semantic_diff(
        "please never say never in marketing copy.",
        "say never in marketing copy.",
    )
    assert not diff.ok
    assert any("negations" in m for m in diff.missing_from_candidate)


def test_gate_dispatches_compressed_when_diff_passes_and_no_scorer():
    gate = FidelityGate()
    result = gate.evaluate("Sarah owes $500.", "Sarah owes $500.")
    assert result.used_compressed
    assert result.dispatch_text == "Sarah owes $500."


def test_gate_falls_back_to_raw_when_diff_fails_and_no_recompress():
    gate = FidelityGate()
    result = gate.evaluate("Sarah owes $500.", "Someone owes money.")
    assert not result.used_compressed
    assert result.dispatch_text == "Sarah owes $500."


def test_gate_uses_independent_scorer_and_respects_threshold():
    gate = FidelityGate(threshold=0.9)
    low_score = lambda raw, candidate: 0.5
    result = gate.evaluate("Sarah owes $500.", "Sarah owes $500.", independent_scorer=low_score)
    assert not result.used_compressed
    assert result.dispatch_text == "Sarah owes $500."
    assert result.score == 0.5


def test_gate_dispatches_compressed_when_score_meets_threshold():
    gate = FidelityGate(threshold=0.8)
    high_score = lambda raw, candidate: 0.95
    result = gate.evaluate("Sarah owes $500.", "Sarah owes $500.", independent_scorer=high_score)
    assert result.used_compressed
    assert result.score == 0.95


def test_gate_retries_via_recompress_fn_then_succeeds():
    gate = FidelityGate(max_retries=1)
    attempts = {"n": 0}

    def recompress(raw, missing):
        attempts["n"] += 1
        return raw  # second attempt just returns the raw text, which must pass

    result = gate.evaluate(
        "Sarah owes $500.", "vague summary", recompress_fn=recompress
    )
    assert result.used_compressed
    assert attempts["n"] == 1
    assert result.attempts == 1


def test_gate_gives_up_after_max_retries():
    gate = FidelityGate(max_retries=1)

    def always_bad(raw, missing):
        return "still vague"

    result = gate.evaluate("Sarah owes $500.", "vague summary", recompress_fn=always_bad)
    assert not result.used_compressed
    assert result.dispatch_text == "Sarah owes $500."
    assert result.attempts == 1
