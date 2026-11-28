"""M47 sub-tasks 2-3 (docs/formulas.md 58.2-58.4): zones, counterparts, moves and rounds."""

from __future__ import annotations

from dataclasses import replace

import pytest

from tst.loader import LoadedData
from tst.sim.negotiation import engine
from tst.sim.negotiation.models import BP, Counterpart, DealRef, Move, Negotiation, TermSpec
from tst.sim.rng import RngFactory

FACTS = ("The quoted price is 5,180.00 $/t", "100 t a year", "Take-or-pay 80%")


def ref(key: int = 1, kind: str = "supplier", wants: str = "lower", median: int = BP) -> DealRef:
    unit = "bp" if median == BP else "cents"
    return DealRef(
        kind,  # type: ignore[arg-type]
        (key,),
        "A deal",
        (TermSpec("price", "Price", unit, wants, 50.0, "$/t"),),  # type: ignore[arg-type]
        (median,),
        Counterpart("Dana", "sales", "Traders", "traders:x"),
        FACTS,
    )


def opened(loaded: LoadedData, seed: int = 7, **kw: object) -> Negotiation:
    return engine.open_negotiation(
        ref(**kw),  # type: ignore[arg-type]
        RngFactory(seed),
        24,
        1.0,
        (),
        0,
        loaded.balance,
    )


def test_the_zone_is_seeded_by_deal_and_month(loaded: LoadedData) -> None:
    a, b = opened(loaded), opened(loaded)
    assert a == b
    other = opened(loaded, key=2)
    assert other.hidden != a.hidden
    later = engine.open_negotiation(ref(), RngFactory(7), 25, 1.0, (), 0, loaded.balance)
    assert later.hidden != a.hidden


def test_the_zone_wraps_todays_price_and_skip_is_the_median(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    for seed in range(1, 30):
        neg = opened(loaded, seed=seed)
        h = neg.hidden
        assert h.reservation[0] < BP < h.aspiration[0]  # the player wants lower
        # M57r-B (ruling 2): the zone is asymmetric, the reservation's distance the
        # aspiration's x (1 +/- reservation_skew) by a draw (so 2 x price - opening is no
        # longer the reservation)
        d = h.aspiration[0] - BP
        skew = b.reservation_skew
        assert d * (1 - skew) - 1 <= BP - h.reservation[0] <= d * (1 + skew) + 1
        assert 3 <= h.patience <= 8
        assert engine.skip(neg).final == (BP,)
        lo, hi = engine.revealed(neg, b)[0]
        assert lo <= h.reservation[0] <= hi
    seller = opened(loaded, wants="higher", median=1_000_000)
    assert seller.hidden.aspiration[0] < 1_000_000 < seller.hidden.reservation[0]
    assert engine.skip(seller).final == (1_000_000,)


def test_the_opening_is_shown_rounded_in_the_counterparts_favour(loaded: LoadedData) -> None:
    neg = opened(loaded)
    step = engine.step_of(BP, loaded.balance.negotiation)
    assert neg.opening[0] % step == 0 and neg.opening[0] >= neg.hidden.aspiration[0]


def test_invalid_moves_are_neutral(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    neg = opened(loaded)
    offer = (neg.counter[0] - 100,)
    claimed = (
        Move("concede", term=0),  # nothing conceded yet: no earlier offer
        Move("justify", fact=9),  # no such fact
        Move("anchor"),  # not far below their demand
    )
    assert engine.check_moves(neg, offer, claimed, b) == (Move("neutral"),) * 3
    ok = engine.check_moves(
        neg, (neg.hidden.reservation[0],), (Move("justify", fact=0), Move("anchor")), b
    )
    assert [m.kind for m in ok] == ["justify", "anchor"]
    assert engine.check_moves(neg, offer, (Move("package", 0, 0),), b) == (Move("neutral"),)


def test_a_justification_counts_once_per_fact(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    neg = engine.play_round(opened(loaded), (9000,), (Move("justify", fact=0),), b)
    again = engine.check_moves(neg, (9000,), (Move("justify", fact=0),), b)
    assert again == (Move("neutral"),)


def test_a_threat_outside_the_zone_walks(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    neg = opened(loaded)
    low = (neg.hidden.reservation[0] - 1,)
    after = engine.play_round(neg, low, (Move("threaten_walk"),), b)
    assert after.status == "walked" and after.rounds[-1].reason == "walked_threat"
    inside = engine.play_round(neg, (neg.hidden.reservation[0] + 1,), (Move("threaten_walk"),), b)
    assert inside.status != "walked" or inside.rounds[-1].reason == "walked_patience"


def test_patience_runs_out(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    neg = opened(loaded)
    low = (neg.hidden.reservation[0] - 500,)
    for _ in range(b.max_rounds):
        if neg.status != "open":
            break
        neg = engine.play_round(neg, low, (Move("neutral"),), b)
    assert neg.status == "walked" and neg.rounds[-1].reason == "walked_patience"
    assert len(neg.rounds) <= neg.hidden.patience


def test_accepting_the_counter_is_inside_the_zone(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    neg = engine.play_round(opened(loaded), (8000,), (Move("justify", fact=1),), b)
    done = engine.accept_counter(neg)
    assert done.status == "agreed" and done.final == neg.counter
    assert engine.inside(neg, done.final)


def test_skill_and_persona_scale_within_the_band(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    assert engine.skill_factor({}, b) == pytest.approx(b.skill.band.lo)
    top = {"negotiation": 20.0, "communication": 20.0, "strategy": 20.0}
    assert engine.skill_factor(top, b) == pytest.approx(b.skill.band.hi)
    neg = replace(opened(loaded), persona=("ruthless",))
    neg = replace(neg, hidden=replace(neg.hidden, skill=b.skill.band.hi))
    assert engine._mult(neg, "threaten_walk", b) == pytest.approx(b.skill.band.hi)


def test_a_replay_of_the_stored_moves_is_identical(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    start = opened(loaded)
    rounds = (
        ((8500,), (Move("anchor"), Move("justify", fact=0))),
        ((9000,), (Move("concede", term=0), Move("appeal"))),
    )
    played = start
    for offer, moves in rounds:
        played = engine.play_round(played, offer, moves, b)
    assert engine.replay(start, rounds, b) == played


def test_zone_share_is_zero_at_skip_and_half_at_the_reservation(loaded: LoadedData) -> None:
    neg = opened(loaded)
    h = neg.hidden
    width = h.aspiration[0] - h.reservation[0]
    assert engine.zone_share(neg, (BP,)) == 0
    # M57r-B: an asymmetric zone, so the reservation's share is its distance's, not a half
    assert engine.zone_share(neg, h.reservation) == pytest.approx((BP - h.reservation[0]) / width)
    assert engine.zone_share(neg, h.aspiration) == pytest.approx(-(h.aspiration[0] - BP) / width)
    assert engine.zone_share(neg, h.reservation) - engine.zone_share(
        neg, h.aspiration
    ) == pytest.approx(1.0)
