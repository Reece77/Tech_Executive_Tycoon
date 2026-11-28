"""M47 sub-task 3's property test (docs/formulas.md 58.3-58.4): whatever the moves and offers,
no outcome is ever worse for the counterpart than its reservation value, its demand never
rises or falls by more than move_step a round, and a walk-away happens only on the stated
conditions (patience gone, the round cap, or a threat with an offer outside the zone)."""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from tests.unit.test_m47_negotiation import ref
from tst.loader import LoadedData
from tst.sim.negotiation import engine
from tst.sim.negotiation.config import MOVE_KINDS
from tst.sim.negotiation.models import BP, Move
from tst.sim.rng import RngFactory

moves = st.builds(
    Move,
    st.sampled_from(MOVE_KINDS),
    st.one_of(st.none(), st.integers(0, 1)),
    st.one_of(st.none(), st.integers(0, 1)),
    st.one_of(st.none(), st.integers(0, 3)),
)
rounds = st.lists(
    st.tuples(st.integers(5_000, 15_000), st.lists(moves, min_size=1, max_size=4)),
    min_size=1,
    max_size=12,
)


@settings(max_examples=150, deadline=None)
@given(
    seed=st.integers(0, 2**32),
    wants=st.sampled_from(["lower", "higher"]),
    played=rounds,
    skill=st.floats(0.8, 1.2),
    finish=st.sampled_from(["none", "accept", "skip"]),
)
def test_no_outcome_beats_the_reservation(
    loaded: LoadedData,
    seed: int,
    wants: str,
    played: list[tuple[int, list[Move]]],
    skill: float,
    finish: str,
) -> None:
    b = loaded.balance.negotiation
    neg = engine.open_negotiation(
        ref(wants=wants), RngFactory(seed), 30, skill, ("ruthless", "beloved"), 0, loaded.balance
    )
    for value, ms in played:
        if neg.status != "open":
            break
        before = neg
        neg = engine.play_round(neg, (value,), tuple(ms), b)
        assert 0.0 <= neg.level <= before.level
        # at most move_step, x (1 + concession_jitter) for the round's hidden draw (M57r-B)
        assert before.level - neg.level <= b.move_step * (1 + b.concession_jitter) + 1e-12
        last = neg.rounds[-1]
        if neg.status == "walked":
            threat = any(m.kind == "threaten_walk" for m in last.moves)
            outside = not engine.inside(before, (value,))
            assert (threat and outside) or last.reason == "walked_patience"
            if last.reason == "walked_patience":
                assert neg.patience_left <= 0 or len(neg.rounds) >= b.max_rounds
    if neg.status == "open" and finish == "accept":
        neg = engine.accept_counter(neg)
    elif neg.status == "open" and finish == "skip":
        neg = engine.skip(neg)
    if neg.final is not None:
        assert engine.inside(neg, neg.final)
        # never past the reservation (its own share: a half no longer, the zone is skewed)
        assert (
            engine.zone_share(neg, neg.final)
            <= engine.zone_share(neg, neg.hidden.reservation) + 1e-9
        )
        if neg.status == "skipped":
            assert neg.final == (BP,)
