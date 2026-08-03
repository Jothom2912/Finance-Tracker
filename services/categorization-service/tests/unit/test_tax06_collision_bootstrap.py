from app.tools.tax06_collision_bootstrap import allocate_surrogates, collision_free_start


def test_collision_free_start_clears_occupied_and_published_ranges() -> None:
    assert collision_free_start(11, 11, 24) == 24
    assert collision_free_start(30, 28, 24) == 31
    assert collision_free_start(100, 140, 109) == 141


def test_allocate_surrogates_is_contiguous_and_deterministic() -> None:
    keys = ["food", "housing", "transport"]
    assert allocate_surrogates(keys, 31) == {"food": 31, "housing": 32, "transport": 33}
