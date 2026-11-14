import pytest

from tst.sim.errors import InvalidSeedError, UnknownStreamError
from tst.sim.rng import STREAM_IDS, RngFactory


def test_same_seed_turn_and_name_give_identical_draws() -> None:
    a = RngFactory(42).stream(3, "hiring").integers(0, 2**31, size=8)
    b = RngFactory(42).stream(3, "hiring").integers(0, 2**31, size=8)
    assert a.tolist() == b.tolist()


def test_known_values_are_stable() -> None:
    # Pinned so a NumPy or derivation change that alters every save is caught.
    draws = RngFactory(42).stream(0, "people_gen").integers(0, 1000, size=5).tolist()
    assert draws == PINNED_PEOPLE_GEN_DRAWS


def test_different_names_give_different_draws() -> None:
    factory = RngFactory(7)
    seqs = {
        name: tuple(factory.stream(0, name).integers(0, 2**31, size=4).tolist())
        for name in STREAM_IDS
    }
    assert len(set(seqs.values())) == len(STREAM_IDS)


def test_different_turns_give_different_draws() -> None:
    factory = RngFactory(7)
    a = factory.stream(0, "market").integers(0, 2**31, size=4).tolist()
    b = factory.stream(1, "market").integers(0, 2**31, size=4).tolist()
    assert a != b


def test_different_seeds_give_different_draws() -> None:
    a = RngFactory(1).stream(0, "market").integers(0, 2**31, size=4).tolist()
    b = RngFactory(2).stream(0, "market").integers(0, 2**31, size=4).tolist()
    assert a != b


def test_unknown_name_raises() -> None:
    with pytest.raises(UnknownStreamError):
        RngFactory(1).stream(0, "not_a_stream")


@pytest.mark.parametrize("seed", [-1, 2**64, True])
def test_invalid_seed_raises(seed: int) -> None:
    with pytest.raises(InvalidSeedError):
        RngFactory(seed)


def test_stream_ids_are_unique_and_append_only() -> None:
    assert len(set(STREAM_IDS.values())) == len(STREAM_IDS)
    # Existing ids must never change (ADR-0002).
    assert dict(STREAM_IDS) == {
        "people_gen": 1,
        "hiring": 2,
        "morale": 3,
        "market": 4,
        "rivals": 5,
        "events": 6,
        "founder": 7,
        "growth": 8,
        "reveal": 9,
        "tags": 10,
        "resign": 11,
        "retire": 12,
        "actions": 13,
        "delegate": 14,
        "product_dev": 15,
        "finance": 16,
        "board": 17,
        "rival_spawn": 18,
        "poach": 19,
        "entrants": 20,
        "macro": 21,  # M10
        "rival_region": 22,
        "supply": 26,
        "facility": 27,
        "research": 23,  # M11
        "rival_research": 24,
        "lead_reveal": 25,
        "manufacturing": 30,  # M12b
        "era_window": 31,
        "ipo": 33,  # M13 (25.2)
        "market_sentiment": 34,  # M13 (25.3)
        "pitch": 36,  # M13b (27.1)
        "mna": 37,  # M14 (28)
        "integration": 38,  # M14 (28.5)
        "rival_mna": 39,  # M14 (28.6)
        "scenario": 43,  # M15b (30.3)
        "press": 40,  # M14b (29.4)
        "group": 45,  # M16 (31)
        "founder_life": 46,  # M24 (32.5)
        "commodity": 47,  # M17 (33.1, 33.3, 33.5)
        "geology": 48,  # M18 (34.1)
        "exploration": 49,  # M18 (34.2-34.3)
        "mining": 50,  # M19 (35.2-35.4)
        "refining": 51,  # M20 (36.1, 36.4)
        "region_risk": 52,  # M19 (35.4)
        "personal": 53,  # M26 (37)
        "fab": 54,  # M21 (38)
        "geopolitics": 55,  # M22 (39)
        "automation": 56,  # M27a (40.3)
        "world": 57,  # M28 (41)
        "misc": 99,
    }


PINNED_PEOPLE_GEN_DRAWS = [406, 755, 323, 355, 962]


# --- ADR-0013 entity keys -------------------------------------------------------------------


def _draws(factory: RngFactory, turn: int, name: str, *key: int) -> list[int]:
    return factory.stream(turn, name, *key).integers(0, 2**31, size=6).tolist()


def test_no_key_is_unchanged_from_m0() -> None:
    # The unkeyed derivation must not move, or M0 golden snapshots would change.
    assert RngFactory(42).stream(0, "people_gen").integers(0, 1000, size=5).tolist() == (
        PINNED_PEOPLE_GEN_DRAWS
    )


def test_same_key_is_identical_and_keys_are_independent() -> None:
    factory = RngFactory(9)
    assert _draws(factory, 3, "growth", 17) == _draws(factory, 3, "growth", 17)
    assert _draws(factory, 3, "growth", 17) != _draws(factory, 3, "growth", 18)
    assert _draws(factory, 3, "growth", 17) != _draws(factory, 3, "growth")
    assert _draws(factory, 3, "reveal", 1, 2) != _draws(factory, 3, "reveal", 2, 1)


def test_keyed_draws_do_not_depend_on_other_entities() -> None:
    # Person 5's growth noise is the same however many other people are drawn first.
    alone = _draws(RngFactory(3), 1, "growth", 5)
    factory = RngFactory(3)
    for other in range(40):
        _draws(factory, 1, "growth", other)
    assert _draws(factory, 1, "growth", 5) == alone


@pytest.mark.parametrize("bad", [(-1,), (True,), (1.5,)])
def test_invalid_keys_raise(bad: tuple[object, ...]) -> None:
    with pytest.raises(InvalidSeedError):
        RngFactory(1).stream(0, "growth", *bad)  # type: ignore[arg-type]
