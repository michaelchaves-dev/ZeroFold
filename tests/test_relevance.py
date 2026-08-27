from zerofold.relevance import evaluate, filter_relevant


def test_discards_pleasantries():
    assert evaluate("Thanks!").keep is False
    assert evaluate("ok").keep is False
    assert evaluate("sounds good").keep is False


def test_discards_retry_markers():
    assert evaluate("never mind, ignore that").keep is False


def test_discards_empty():
    assert evaluate("   ").keep is False


def test_keeps_explicit_rule():
    d = evaluate("Always respond in under 200 words.")
    assert d.keep is True
    assert d.reason == "durable_signal"


def test_keeps_preference_statement():
    assert evaluate("I prefer dark mode over light mode.").keep is True


def test_keeps_text_with_numbers_or_contact_info():
    assert evaluate("My budget is 5000 dollars").keep is True
    assert evaluate("reach me at name@example.com").keep is True


def test_discards_short_content_free_text():
    assert evaluate("cool beans").keep is False


def test_filter_relevant_on_message_list():
    messages = [
        {"role": "user", "content": "Hi"},
        {"role": "user", "content": "My name is Priya and I always want concise answers."},
        {"role": "assistant", "content": "Got it."},
    ]
    kept = filter_relevant(messages)
    assert len(kept) == 1
    assert "Priya" in kept[0]["content"]
