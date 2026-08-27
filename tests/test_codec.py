from zerofold.codec import normalize_text, source_hash, stable_hash, stable_json


def test_stable_json_sorts_keys():
    assert stable_json({"b": 1, "a": 2}) == '{"a":2,"b":1}'


def test_stable_hash_deterministic():
    assert stable_hash({"a": 1, "b": 2}) == stable_hash({"b": 2, "a": 1})


def test_normalize_text_collapses_whitespace_and_case():
    assert normalize_text("  Hello   World  ") == "hello world"


def test_source_hash_stable_across_whitespace_variation():
    assert source_hash("Hello   world") == source_hash("hello world  ")


def test_source_hash_differs_for_different_text():
    assert source_hash("hello") != source_hash("goodbye")
