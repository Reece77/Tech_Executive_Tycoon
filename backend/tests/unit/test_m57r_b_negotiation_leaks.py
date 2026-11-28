"""M57r-B (review 10 item 4, F2; ruling 2): no estimator over a negotiation's public view
recovers the counterpart's reservation better than the shown range allows.

Review 10 reproduced three estimators on M47's engine: (a) the shown range's midpoint is linear
in its width, so three throwaway rounds extrapolate it to the reservation (median error 1.3-3.9%
of the zone); (b) each counter is `reservation + level x (aspiration - reservation)` with the
level known from the published effects table; (c) the zone is symmetric about today's price,
so `2 x price - opening` is the reservation. Each runs here on 400 seeds against the engine as
it now is, and must miss by at least ESTIMATE_FLOOR of the zone (median), as must their mean
(a player combining them).
"""

from __future__ import annotations

import statistics
from dataclasses import replace

from tests.unit.test_m47_negotiation import ref
from tst.loader import LoadedData
from tst.sim.negotiation import engine
from tst.sim.negotiation.models import BP, Move, Negotiation
from tst.sim.rng import RngFactory

SEEDS = range(400)
ESTIMATE_FLOOR = 0.10  # the median miss, x the zone; review 10 measured 0.013-0.039


def _open(loaded: LoadedData, seed: int) -> Negotiation:
    return engine.open_negotiation(ref(), RngFactory(seed), 24, 1.0, (), 0, loaded.balance)


def _lowball(neg: Negotiation, loaded: LoadedData, rounds: int = 3) -> list[Negotiation]:
    """Throwaway rounds: an offer far below any zone with a neutral move."""
    b = loaded.balance.negotiation
    out = [neg]
    for _ in range(rounds):
        if out[-1].status != "open":
            break
        out.append(engine.play_round(out[-1], (1,), (Move("neutral"),), b))
    return out


def _zone(neg: Negotiation) -> float:
    return abs(neg.hidden.aspiration[0] - neg.hidden.reservation[0])


def _midpoint_extrapolation(steps: list[Negotiation], loaded: LoadedData) -> float | None:
    """(a): fit the range's midpoint against its half-width and read it at width 0."""
    b = loaded.balance.negotiation
    pts = []
    for n in steps:
        ((lo, hi),) = engine.revealed(n, b)
        pts.append(((hi - lo) / 2, (hi + lo) / 2))
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    if len(set(xs)) < 2:
        return ys[-1]  # no slope to read: the midpoint itself
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sum(
        (x - mx) ** 2 for x in xs
    )
    return my - slope * mx


def _counter_inversion(steps: list[Negotiation], loaded: LoadedData) -> float | None:
    """(b): the published effects give the level; invert the counter with the opening."""
    b = loaded.balance.negotiation
    if len(steps) < 2 or steps[1].status != "open":
        return None
    step = min(b.move_step, b.move_step * b.effects["neutral"].concession * steps[0].hidden.skill)
    level = max(0.0, 1.0 - step)
    if level >= 1.0:
        return None
    a, c = steps[0].opening[0], steps[1].counter[0]
    return (c - level * a) / (1 - level)


def _symmetry(neg: Negotiation) -> float:
    """(c): today's price mirrored through the opening."""
    return 2 * BP - neg.opening[0]


def _misses(loaded: LoadedData) -> dict[str, list[float]]:
    out: dict[str, list[float]] = {"a": [], "b": [], "c": [], "mean": []}
    for seed in SEEDS:
        neg = _open(loaded, seed)
        steps = _lowball(neg, loaded)
        r, zone = neg.hidden.reservation[0], _zone(neg)
        found = {
            "a": _midpoint_extrapolation(steps, loaded),
            "b": _counter_inversion(steps, loaded),
            "c": _symmetry(neg),
        }
        known = [v for v in found.values() if v is not None]
        found["mean"] = statistics.fmean(known)
        for k, v in found.items():
            if v is not None:
                out[k].append(abs(v - r) / zone)
    return out


def test_no_estimator_recovers_the_reservation(loaded: LoadedData) -> None:
    misses = _misses(loaded)
    medians = {k: statistics.median(v) for k, v in misses.items()}
    for k, m in medians.items():
        assert m >= ESTIMATE_FLOOR, (k, medians)


def test_the_range_still_holds_the_reservation_and_nests(loaded: LoadedData) -> None:
    b = loaded.balance.negotiation
    for seed in range(60):
        steps = _lowball(_open(loaded, seed), loaded, rounds=6)
        before: tuple[int, int] | None = None
        for n in steps:
            ((lo, hi),) = engine.revealed(n, b)
            assert lo <= n.hidden.reservation[0] <= hi
            if before is not None:
                assert before[0] <= lo and hi <= before[1]  # nested in the last
            before = (lo, hi)


def test_the_ranges_width_is_the_same_whatever_the_true_zone(loaded: LoadedData) -> None:
    """Paired state: the same opening with another reservation (the range's centre held, the
    zone wider) shows the same range: its width says nothing about the zone."""
    b = loaded.balance.negotiation
    neg = _open(loaded, 11)
    h = neg.hidden
    start = engine.revealed(neg, b)
    # move the reservation by a tenth of the zone and the offset to hold the centre
    shift = round(_zone(neg) / 10)
    half0 = (
        float(engine.nominal_zone(neg, 0, b))
        * b.range.start
        * float((b.skill.band.lo + b.skill.band.hi - h.skill) ** b.range.skill_power)
    )
    off = h.offsets[0] + shift / (b.range.centre * half0)
    assert -1.0 <= off <= 1.0
    other = replace(
        neg,
        hidden=replace(h, reservation=(h.reservation[0] - shift,), offsets=(off,)),
    )
    assert engine.revealed(other, b) == start
