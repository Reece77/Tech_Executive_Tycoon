"""M47's balance targets (docs/formulas.md 58.5), printed by tools/m47_targets.py.

The engine (tst.sim.negotiation.engine) is the same for every deal kind; a kind differs in its
zone's spread (negotiation.spread) and, for an acquisition, in its zone being 28.3's first
counter and reservation. So targets 2 and 3 play scripted negotiators against every deal kind's
counterparts, `DEALS` deals a kind on each seed, each a fresh draw (stream negotiation, its own
deal key), with the scripts choosing moves as template mode's buttons do:

1. **Skip is fair:** skip closes at the median, today's terms. For every kind but an acquisition
   that median is the existing price itself (the quote at 10,000 bp, the candidate's expectation,
   the rival's offer, the award, the settlement's fine, the listed upfront), and skip executes the
   kind's existing action at it (tests/unit/test_m47_deals.py); printed as the largest gap. For an
   acquisition, today's price is the second counter of 28.3's talks (the first counter's halfway
   point to the reservation), measured on every private company of a new game on each seed.
2. **Talking matters, within limits:** a strong negotiator (score 16) playing well gets terms
   10-25% of the zone better than skip on average; a weak one (score 6) playing naively 0-15%
   worse; no outcome beats the reservation (the property test; checked here on every deal).
3. **Walk-aways happen:** a script that always threatens to walk, offering at the revealed
   range's far end, loses at least 30% of deals.
4. **No leak:** tests/integration/test_m47_conversations.py (planted hidden values never reach a
   prompt or a reply).
5. **Turn time unchanged:** conversations run between turns; no turn phase reads them. The turn
   budgets are make check-timing's; printed here is a month's mean time on seed 1 for reference.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from statistics import mean, median
from typing import Final

from tst.loader import LoadedData, load_all
from tst.sim.negotiation import engine
from tst.sim.negotiation.config import DEAL_KINDS, NegotiationBalance
from tst.sim.negotiation.models import BP, Counterpart, DealRef, Move, Negotiation, TermSpec
from tst.sim.rng import RngFactory

SEEDS: Final = tuple(range(1, 11))
DEALS: Final = 40  # deals of each kind on each seed
DATA: Final = Path(__file__).resolve().parents[2] / "data"
TURN: Final = 96  # January 2018 (the practice save's month); draws differ by month only
STRONG: Final = 16.0
WEAK: Final = 6.0
FACTS: Final = ("fact one", "fact two", "fact three")
ACQUISITION_ANCHOR: Final = 1.30  # a typical first counter over the reservation (28.3)
SUM: Final = 1_000_000_000  # a cents term's median for the scripts ($10M)
BANDS: Final[dict[str, tuple[float, float]]] = {"strong": (0.10, 0.25), "weak": (-0.15, 0.0)}
WALKS: Final = 0.30  # target 3: at least this share of deals lost
SKIP_GAP: Final = 0.01  # target 1: the median gap to today's price


@cache
def loaded() -> LoadedData:
    return load_all(DATA)


def _ref(kind: str, k: int) -> DealRef:
    bp = kind in ("supplier", "offtake", "foundry", "ppa")
    wants = "higher" if kind in ("foundry", "government", "licence_out") else "lower"
    median = BP if bp else SUM
    zones = None
    if kind == "acquisition":
        reservation = SUM
        zones = ((round(reservation * ACQUISITION_ANCHOR), reservation),)
    return DealRef(
        kind,  # type: ignore[arg-type]
        (k,),
        f"{kind} {k}",
        (TermSpec("price", "Price", "bp" if bp else "cents", wants, 100.0, "a unit"),),  # type: ignore[arg-type]
        (median,),
        Counterpart("Counterpart", "role", "Org", f"{kind}:{k}"),
        FACTS,
        zones,
    )


def _toward_them(neg: Negotiation, value: int, step: int) -> int:
    """`value` moved `step` toward the counterpart (up when the player wants lower)."""
    return value + step if neg.terms[0].wants == "lower" else value - step


def _limit_side(neg: Negotiation, b: NegotiationBalance, far: bool) -> int:
    """The revealed range's end on the player's side (far) or the counterpart's (near)."""
    lo, hi = engine.revealed(neg, b)[0]
    lower = neg.terms[0].wants == "lower"
    return (lo if lower else hi) if far else (hi if lower else lo)


def sensible(neg: Negotiation, b: NegotiationBalance) -> Negotiation:
    """One sensible player, as template mode's buttons allow, reading only what is shown: it
    anchors at the revealed range's far end with a justification, then splits the difference
    between that end and their offer, citing a new fact each round (an appeal when none is
    left); it takes their offer once it falls inside the revealed range, or when they are about
    to walk. The strong and the weak negotiator play it alike; only their score differs (and
    with it the moves' effects and how narrow the range they see is)."""
    fact = 0
    while neg.status == "open":
        last = neg.rounds[-1] if neg.rounds else None
        near = _limit_side(neg, b, far=False)
        inside = neg.counter[0] <= near if neg.terms[0].wants == "lower" else neg.counter[0] >= near
        if last is not None and (last.mood == "final" or inside):
            return engine.accept_counter(neg)
        far = _limit_side(neg, b, far=True)
        if not neg.rounds:
            offer, moves = far, [Move("anchor"), Move("justify", fact=0)]
        else:
            offer = far + (neg.counter[0] - far) // 2
            moves = [Move("justify", fact=fact)] if fact < len(FACTS) else [Move("appeal")]
        fact += 1
        neg = engine.play_round(neg, (offer,), tuple(moves), b)
    return neg


strong = sensible
weak = sensible


def threat(neg: Negotiation, b: NegotiationBalance) -> Negotiation:
    """Always threatens to walk, offering at the revealed range's far end; takes the counter
    when they are about to walk."""
    while neg.status == "open":
        last = neg.rounds[-1] if neg.rounds else None
        if last is not None and last.mood == "final":
            return engine.accept_counter(neg)
        neg = engine.play_round(neg, (_limit_side(neg, b, far=True),), (Move("threaten_walk"),), b)
    return neg


SCRIPTS: Final[
    dict[str, tuple[Callable[[Negotiation, NegotiationBalance], Negotiation], float]]
] = {
    "strong": (strong, STRONG),
    "weak": (weak, WEAK),
    "threat": (threat, 11.0),
}


@dataclass(frozen=True, slots=True)
class Reading:
    script: str
    kind: str
    shares: tuple[float, ...]  # zone share of each agreed deal (+ better than skip)
    walked: int
    deals: int
    beyond: int  # outcomes past the reservation (must be 0)


def play(script: str, seeds: Sequence[int] = SEEDS, deals: int = DEALS) -> list[Reading]:
    data = loaded()
    b = data.balance.negotiation
    fn, score = SCRIPTS[script]
    skill = engine.skill_factor({k: score for k in b.skill.weights}, b)
    out = []
    for kind in DEAL_KINDS:
        shares: list[float] = []
        walked = beyond = 0
        for seed in seeds:
            for k in range(deals):
                neg = engine.open_negotiation(
                    _ref(kind, k), RngFactory(seed), TURN, skill, (), 0, data.balance
                )
                neg = fn(neg, b)
                if neg.status == "walked":
                    walked += 1
                    continue
                assert neg.final is not None
                if not engine.inside(neg, neg.final):
                    beyond += 1
                shares.append(engine.zone_share(neg, neg.final))
        out.append(Reading(script, kind, tuple(shares), walked, len(seeds) * deals, beyond))
    return out


def acquisition_skip_gaps(seeds: Sequence[int] = SEEDS) -> list[float]:
    """Target 1 for an acquisition: |skip - today's second counter| / today's, on every private
    company of a new game on each seed (28.3's talks, as shown)."""
    from tst.balance.game import start_game
    from tst.balance.report import SCENARIO
    from tst.sim.mna import formulas as mf
    from tst.sim.mna import valuation
    from tst.sim.negotiation import deals as nd

    data = loaded()
    gaps = []
    for seed in seeds:
        game = start_game(data, seed, SCENARIO)
        state, balances = game.state, game.balances
        rng = RngFactory(state.save_meta.master_seed)
        for c in state.rivals():
            if (
                not c.alive
                or c.parent_id is not None
                or valuation.is_listed(state, c.id, data.game_data)
            ):
                continue
            deal = nd.deal_for(
                state, "acquisition", {"target_id": c.id, "mode": "brand"}, rng, balances,
                data.balance, data.game_data,
            )  # fmt: skip
            assert deal.ref.zones is not None
            ((first, reservation),) = deal.ref.zones
            today = mf.next_counter_exact(first, reservation)  # before display rounding
            skip = (first + reservation) // 2
            gaps.append(abs(skip - today) / today)
    return gaps


def turn_ms(turns: int = 12) -> float:
    from tst.balance.game import start_game
    from tst.balance.report import SCENARIO

    game = start_game(loaded(), 1, SCENARIO)
    started = time.perf_counter()
    for _ in range(turns):
        game.turn()
    return (time.perf_counter() - started) * 1000 / turns


def report(seeds: Sequence[int] = SEEDS, deals: int = DEALS, timing: bool = True) -> str:
    lines = [
        f"M47 targets (formulas.md 58.5), seeds {seeds[0]}-{seeds[-1]}, {deals} deals a kind a seed"
    ]
    gaps = acquisition_skip_gaps(seeds)
    mid = median(gaps) if gaps else 0.0
    worst = max(gaps, default=0.0)
    ok1 = mid <= SKIP_GAP
    lines.append(
        f"1. Skip is fair: every kind but acquisitions closes at today's price exactly (0.0%); "
        f"acquisitions vs today's second counter: median {mid:.3%}, worst {worst:.3%} on "
        f"{len(gaps)} companies (median within 1%): {'met' if ok1 else 'MISSED'}"
    )
    rows = {s: play(s, seeds, deals) for s in SCRIPTS}
    beyond = sum(r.beyond for rs in rows.values() for r in rs)
    for name in ("strong", "weak"):
        lo, hi = BANDS[name]
        all_shares = [x for r in rows[name] for x in r.shares]
        avg = mean(all_shares)
        walks = sum(r.walked for r in rows[name]) / sum(r.deals for r in rows[name])
        per = ", ".join(f"{r.kind} {mean(r.shares) if r.shares else 0:+.0%}" for r in rows[name])
        met = lo <= avg <= hi
        lines.append(
            f"2. {name} ({'score 16' if name == 'strong' else 'score 6'}): {avg:+.1%} of the zone "
            f"vs skip (band {lo:+.0%} to {hi:+.0%}), walked {walks:.0%}: "
            f"{'met' if met else 'MISSED'} [{per}]"
        )
    lines.append(
        f"2. Beyond the reservation: {beyond} outcomes (must be 0): "
        f"{'met' if beyond == 0 else 'MISSED'}"
    )
    t = rows["threat"]
    lost = sum(r.walked for r in t) / sum(r.deals for r in t)
    lines.append(
        f"3. Always threatening to walk loses {lost:.0%} of deals (at least 30%): "
        f"{'met' if lost >= WALKS else 'MISSED'}"
    )
    lines.append("4. No leak: tests/integration/test_m47_conversations.py (planted values): met")
    if timing:
        lines.append(
            f"5. Turn time: conversations run between turns; a 2010 month on seed 1 takes "
            f"{turn_ms():.0f} ms (budgets: make check-timing)"
        )
    return "\n".join(lines)
