from zerofold.contracts import contract_from_intent
from zerofold.outbound import OutboundSupervisor


def test_contract_from_intent_lowers_evidence_bar_for_code():
    c = contract_from_intent("code", 500)
    assert c.evidence == "optional"
    assert c.max_tokens == 500


def test_contract_from_intent_requires_evidence_for_qa():
    c = contract_from_intent("qa", 500)
    assert c.evidence == "required"


def test_outbound_rejects_empty_response():
    sup = OutboundSupervisor()
    result = sup.validate("   ", contract_from_intent("chat", 100))
    assert not result.passed
    assert result.violations[0].code == "empty"


def test_outbound_passes_clean_response():
    sup = OutboundSupervisor()
    result = sup.validate("The deadline is March 3rd, 2027.", contract_from_intent("qa", 100))
    assert result.passed


def test_outbound_flags_repetition():
    sup = OutboundSupervisor(shingle_size=3)
    text = " ".join(["the quick brown fox jumps"] * 10)
    result = sup.validate(text, contract_from_intent("chat", 200))
    codes = [v.code for v in result.violations]
    assert "repetition" in codes
    assert not result.passed


def test_outbound_flags_format_mismatch_for_json_contract():
    sup = OutboundSupervisor()
    contract = contract_from_intent("extraction", 100, format="json")
    result = sup.validate("this is not json.", contract)
    codes = [v.code for v in result.violations]
    assert "format_mismatch" in codes
    assert not result.passed


def test_outbound_accepts_valid_json_for_json_contract():
    sup = OutboundSupervisor()
    contract = contract_from_intent("extraction", 100, format="json")
    result = sup.validate('{"name": "Priya"}', contract)
    assert result.passed


def test_outbound_budget_exceeded_is_non_blocking():
    sup = OutboundSupervisor()
    long_text = "word " * 500 + "."
    result = sup.validate(long_text, contract_from_intent("chat", 10))
    codes = [v.code for v in result.violations]
    assert "budget_exceeded" in codes
    # non-blocking on its own (repetition would also trip here, so isolate it)
    budget_violation = next(v for v in result.violations if v.code == "budget_exceeded")
    assert budget_violation.blocking is False


def test_outbound_unsupported_claim_is_non_blocking_but_reported():
    sup = OutboundSupervisor()
    contract = contract_from_intent("qa", 100)
    result = sup.validate("This treatment is scientifically proven and guaranteed to work.", contract)
    codes = [v.code for v in result.violations]
    assert "unsupported_claim" in codes
    claim_violation = next(v for v in result.violations if v.code == "unsupported_claim")
    assert claim_violation.blocking is False


def test_outbound_cited_claim_is_not_flagged():
    sup = OutboundSupervisor()
    contract = contract_from_intent("qa", 100)
    result = sup.validate(
        "According to the manufacturer, this is guaranteed for one year.", contract
    )
    codes = [v.code for v in result.violations]
    assert "unsupported_claim" not in codes
