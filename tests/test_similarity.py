from zerofold.similarity import LocalTextSimilarity, cosine_similarity, tokenize


def test_identical_text_is_maximally_similar():
    assert cosine_similarity("dark mode please", "dark mode please") == 1.0


def test_disjoint_text_is_zero():
    assert cosine_similarity("dark mode", "pizza toppings") == 0.0


def test_partial_overlap_is_between_zero_and_one():
    score = cosine_similarity("I prefer dark mode", "I prefer light mode")
    assert 0.0 < score < 1.0


def test_empty_strings_are_zero_not_an_error():
    assert cosine_similarity("", "anything") == 0.0
    assert cosine_similarity("", "") == 0.0


def test_tokenize_lowercases_and_strips_punctuation():
    assert tokenize("Dark-Mode, please!") == ["dark", "mode", "please"]


def test_backend_wrapper_matches_function():
    backend = LocalTextSimilarity()
    assert backend.similarity("a b c", "a b c") == cosine_similarity("a b c", "a b c")
