from zerofold.bloom import BloomFilter


def test_no_false_negatives():
    bf = BloomFilter(size_bits=1 << 12, num_hashes=4)
    items = [f"item-{i}" for i in range(200)]
    for item in items:
        bf.add(item)
    for item in items:
        assert bf.might_contain(item)


def test_absent_item_usually_reported_absent():
    bf = BloomFilter(size_bits=1 << 16, num_hashes=4)
    for i in range(50):
        bf.add(f"present-{i}")
    false_positives = sum(
        1 for i in range(1000) if bf.might_contain(f"absent-{i}")
    )
    # Sized generously relative to load factor; false positive rate should be low.
    assert false_positives < 50


def test_seeded_with_builds_from_iterable():
    bf = BloomFilter.seeded_with(["a", "b", "c"])
    assert bf.might_contain("a")
    assert bf.might_contain("b")
    assert bf.might_contain("c")
    assert len(bf) == 3


def test_len_counts_add_calls():
    bf = BloomFilter()
    bf.add("x")
    bf.add("y")
    assert len(bf) == 2
