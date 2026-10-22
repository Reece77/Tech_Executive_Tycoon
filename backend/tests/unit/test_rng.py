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
        "misc": 99,
    }


PINNED_PEOPLE_GEN_DRAWS = [406, 755, 323, 355, 962]
