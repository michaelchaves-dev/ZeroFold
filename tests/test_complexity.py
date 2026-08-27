from zerofold.complexity import ComplexityInputs, complexity_score, min_quality_tier


def test_chat_intent_maps_to_tier_1():
    score = complexity_score(ComplexityInputs(intent="chat"))
    assert min_quality_tier(score) == 1


def test_code_intent_is_more_complex_than_chat():
    chat_score = complexity_score(ComplexityInputs(intent="chat"))
    code_score = complexity_score(ComplexityInputs(intent="code"))
    assert code_score > chat_score


def test_large_context_raises_the_floor():
    small = complexity_score(ComplexityInputs(intent="qa", context_tokens=100))
    large = complexity_score(ComplexityInputs(intent="qa", context_tokens=10_000))
    assert large > small


def test_risk_flags_raise_the_floor_but_cap_out():
    one_risk = complexity_score(ComplexityInputs(intent="chat", risk_flags=["destructive_action"]))
    many_risks = complexity_score(ComplexityInputs(intent="chat", risk_flags=["a", "b", "c", "d", "e", "f"]))
    assert one_risk > complexity_score(ComplexityInputs(intent="chat"))
    assert many_risks <= 1.0


def test_high_complexity_maps_to_tier_3():
    score = complexity_score(ComplexityInputs(intent="code", context_tokens=10_000, risk_flags=["x"]))
    assert min_quality_tier(score) == 3


def test_tier_boundaries_are_monotonic():
    assert min_quality_tier(0.0) == 1
    assert min_quality_tier(0.29) == 1
    assert min_quality_tier(0.3) == 2
    assert min_quality_tier(0.59) == 2
    assert min_quality_tier(0.6) == 3
    assert min_quality_tier(1.0) == 3
