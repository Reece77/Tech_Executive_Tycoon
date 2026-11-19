"""Bidding, awards and protests (docs/formulas.md 57.2).

**Score** (0-100): `w.price x P + w.technical x T + w.past_performance x PP`, with `large_weights`
for a large tender. P = 100 x the lowest price ratio among the bids / the bid's (price over the
tender's value); T = (1 - capture_weight) x the product's quality + capture_weight x the capture
team (its members' mean of `capture_skills`, 1-20 scaled to 0-100); PP = the bidder's record:
the mean performance of its completed contracts, blended from `newcomer_pp` to it over the first
`pp_full` of them.

**Rivals** bid at the award (stream `defence` (1, tender_id, round)), in government.yaml's order:
every prime with merit in the area (from its `from_year`) and every company bidder with a live
product there, from a bloc the government takes, each with `rival_bid_chance` (a named tender's
historical winners always, with `history_bonus` merit). A rival's merit is its strength (a prime's
data, a company's best live product's quality) + N(0, `rival_merit_sd`), its price ratio uniform
in `rival_price`, its PP its data. Three draws a candidate whether it bids or not, then a
tie-break draw a bid. Rivals' bids are never stored.

**Awards**: the `awards` best scores win; a named tender without a qualifying player bid is
awarded to its record's winners, and with one the player displaces the lowest-scoring historical
winner when it scores above it. The lowest awardee's band is published (`band` wide).

**Protests**: when the player wins, each losing rival protests with `protests.rival_chance`
(x `large_mult` on a large tender); the first holds the award `delay_months` (drawn), and is
sustained at GAO's effectiveness rate for the year, re-competing the tender once (round 1).
The player may protest a loss within `window_months` (the action, `protests.cost_cents`). A named
tender's record protests (JEDI) hold it until its record's cancellation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

import numpy as np

from tst.sim.data_models import Balance, GameData
from tst.sim.government import draws
from tst.sim.government.config import ScoreWeights
from tst.sim.government.data import (
    PCT,
    SKILL_MAX,
    area_of,
    company_bloc,
    file,
    gov_bloc,
    is_large,
    year_of,
)
from tst.sim.government.models import Bid, BidStatus, Protest, ScoreTerms, Tender
from tst.sim.government.sourcing import requirements
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

TIE: Final = 1e-6  # tunable-exempt: a tie-break's weight
PLAYER_PROTEST: Final = 1  # tunable-exempt: key suffix of the player's protest draw


@dataclass(frozen=True, slots=True)
class Candidate:
    name: str
    company_id: int | None
    merit: float
    pp: float
    ratio: float
    score: float = 0.0
    player: bool = False


def weights(tender: Tender, balance: Balance) -> ScoreWeights:
    b = balance.government.bids
    return b.large_weights if is_large(tender, balance) else b.weights


def band_of(score: float, balance: Balance) -> int:
    width = balance.government.bids.band
    return int(min(PCT - width, max(0.0, score)) // width * width)


def capture_score(
    state: GameState, company_id: int, team: tuple[int, ...], balance: Balance
) -> float:
    skills = balance.government.bids.capture_skills
    staff = {e.person_id for e in state.staff(company_id)}
    values = []
    for pid in team:
        if pid not in staff:
            continue
        s = state.person(pid).skills
        values.append(sum(s[k] for k in skills) / len(skills))
    if not values:
        return 0.0
    return sum(values) / len(values) / SKILL_MAX * PCT


def past_performance(state: GameState, company_id: int, balance: Balance) -> float:
    b = balance.government.bids
    done = [
        c.performance
        for c in state.gov_contracts
        if c.company_id == company_id and c.status in ("completed", "defaulted")
    ]
    if not done:
        return b.newcomer_pp
    weight = min(1.0, len(done) / b.pp_full)
    return b.newcomer_pp * (1 - weight) + (sum(done) / len(done)) * weight


def player_candidate(state: GameState, bid: Bid, tender: Tender, balance: Balance) -> Candidate:
    b = balance.government.bids
    product = state.product(bid.product_id)
    quality = product.quality if product is not None else 0.0
    capture = capture_score(state, bid.company_id, bid.team, balance)
    merit = (1 - b.capture_weight) * quality + b.capture_weight * capture
    return Candidate(
        name=state.company(bid.company_id).name,
        company_id=bid.company_id,
        merit=merit,
        pp=past_performance(state, bid.company_id, balance),
        # money-exact: rate (a price ratio scored as a float, never posted)
        ratio=bid.price_cents / max(1, tender.value_cents),
        player=True,
    )


def _company_by_name(state: GameState, name: str) -> int | None:
    for c in state.companies:
        if c.name == name and not c.is_player and c.failed_turn is None:
            return c.id
    return None


def _best_quality(state: GameState, company_id: int, area: str, data: GameData) -> float | None:
    best = None
    for p in state.products:
        if p.company_id == company_id and p.status == "live" and area_of(p, data) == area:
            best = p.quality if best is None else max(best, p.quality)
    return best


def rival_candidates(
    state: GameState, tender: Tender, g: np.random.Generator, balance: Balance, data: GameData
) -> list[Candidate]:
    """Rivals' bids at the award (module docstring), drawn in a fixed order."""
    f = file(data)
    gb = balance.government.bids
    gov = f.government(tender.government)
    hist = next((h for h in f.tenders if h.key == tender.key), None) if tender.key else None
    winners = set(hist.winners) if hist is not None else set()
    year = year_of(tender.award_turn)
    turn = state.turn
    out: list[Candidate] = []
    for p in f.primes:
        u, noise, price = float(g.random()), float(g.normal()), float(g.random())
        prime_merit = p.areas.get(tender.area)
        if prime_merit is None or p.from_year > year:
            continue
        if gov_bloc_of(p.country, data, turn) not in gov.open_to and p.name not in winners:
            continue
        is_winner = p.name in winners
        if not is_winner and u >= gb.rival_bid_chance:
            continue
        merit = prime_merit + gb.rival_merit_sd * noise + (gb.history_bonus if is_winner else 0.0)
        ratio = gb.rival_price.lo + (gb.rival_price.hi - gb.rival_price.lo) * price
        cid = _company_by_name(state, p.name)
        out.append(Candidate(p.name, cid, min(PCT, merit), p.past_performance, ratio))
    for c in f.company_bidders:
        u, noise, price = float(g.random()), float(g.normal()), float(g.random())
        if tender.area not in c.areas or c.from_year > year:
            continue
        cid = _company_by_name(state, c.name)
        is_winner = c.name in winners
        if cid is None:
            if not is_winner:
                continue
            strength = gb.newcomer_pp + gb.history_bonus  # a record winner absent
        else:
            best = _best_quality(state, cid, tender.area, data)
            company = state.company(cid)
            if best is None:
                if not is_winner:
                    continue
                best = gb.newcomer_pp + gb.history_bonus
            strength = best
            if company_bloc(state, company, balance, data) not in gov.open_to and not is_winner:
                continue
        if not is_winner and u >= gb.rival_bid_chance:
            continue
        merit = strength + gb.rival_merit_sd * noise + (gb.history_bonus if is_winner else 0.0)
        ratio = gb.rival_price.lo + (gb.rival_price.hi - gb.rival_price.lo) * price
        out.append(Candidate(c.name, cid, min(PCT, merit), c.past_performance, ratio))
    return out


def gov_bloc_of(country: str, data: GameData, turn: int) -> str:
    from tst.sim.geopolitics import world

    if not world.enabled(data):
        return "us_aligned"
    return world.bloc_of(data, country, turn)


def score_all(
    candidates: list[Candidate], tender: Tender, g: np.random.Generator, balance: Balance
) -> list[Candidate]:
    if not candidates:
        return []
    w = weights(tender, balance)
    low = min(c.ratio for c in candidates)
    out = []
    for c in candidates:
        price = PCT * low / c.ratio if c.ratio > 0 else PCT
        total = w.price * price + w.technical * c.merit + w.past_performance * c.pp
        out.append(replace(c, score=total + TIE * float(g.random())))
    return out


def terms_of(c: Candidate, low: float, tender: Tender, balance: Balance) -> ScoreTerms:
    w = weights(tender, balance)
    price = PCT * low / c.ratio if c.ratio > 0 else PCT
    total = w.price * price + w.technical * c.merit + w.past_performance * c.pp
    return ScoreTerms(price=price, technical=c.merit, past_performance=c.pp, weighted=total)


@dataclass(frozen=True, slots=True)
class Outcome:
    state: GameState
    winners: tuple[Candidate, ...]
    player_won: bool
    logs: tuple[LogItem, ...] = ()


def award(
    state: GameState, tender: Tender, rng: RngFactory, balance: Balance, data: GameData
) -> Outcome:
    """Score the bids and award the tender this month (module docstring). The player's bid, if
    any, gets its status, terms and reasons; rivals' bids are discarded."""
    g = draws.gen(rng, tender.award_turn, draws.AWARD, tender.id, tender.round)
    rivals = rival_candidates(state, tender, g, balance, data)
    bids = [
        b
        for b in state.gov_bids
        if b.tender_id == tender.id and b.status in ("submitted", "won", "lost")
    ]
    player: Candidate | None = None
    bid: Bid | None = bids[0] if bids else None
    reasons: tuple[str, ...] = ()
    if bid is not None:
        company = state.company(bid.company_id)
        reasons = requirements(state, company, state.product(bid.product_id), tender, balance, data)
        if not reasons:
            player = player_candidate(state, bid, tender, balance)
    pool = [*rivals, *([player] if player is not None else [])]
    scored = score_all(pool, tender, g, balance)
    f = file(data)
    hist = next((h for h in f.tenders if h.key == tender.key), None) if tender.key else None
    if hist is not None:
        by_name = {c.name: c for c in scored if not c.player}
        record = [
            by_name.get(n) or Candidate(n, _company_by_name(state, n), 0, 0, 1)
            for n in hist.winners
        ]
        mine = next((c for c in scored if c.player), None)
        winners = list(record)
        if mine is not None and record:
            lowest = min(record, key=lambda c: c.score)
            if mine.score > lowest.score:
                winners = [mine if c is lowest else c for c in record]
    else:
        winners = sorted(scored, key=lambda c: -c.score)[: tender.awards]
    player_won = any(c.player for c in winners)
    band = (
        band_of(min(c.score for c in winners), balance)
        if winners and any(c.score for c in winners)
        else None
    )
    low = min((c.ratio for c in pool), default=1.0)
    state = replace(
        state,
        tenders=tuple(
            replace(
                t,
                status="awarded",
                winners=tuple(c.name for c in winners),
                winner_ids=tuple(c.company_id for c in winners if c.company_id is not None),
                winning_band=band,
                protest_until=None,
            )
            if t.id == tender.id
            else t
            for t in state.tenders
        ),
    )
    logs: list[LogItem] = []
    if bid is not None:
        status: BidStatus
        if reasons:
            status = "disqualified"
            terms = None
        else:
            assert player is not None
            status = "won" if player_won else "lost"
            terms = terms_of(player, low, tender, balance)
        state = replace(
            state,
            gov_bids=tuple(
                replace(b, status=status, terms=terms, reasons=reasons) if b.id == bid.id else b
                for b in state.gov_bids
            ),
        )
        logs.append(
            inbox_item(
                state.turn,
                bid.company_id,
                "tender_awarded",
                tender=tender.title,
                outcome=status,
                winners=", ".join(c.name for c in winners),
            )
        )
    return Outcome(state=state, winners=tuple(winners), player_won=player_won, logs=tuple(logs))


def rival_protest(
    state: GameState,
    tender: Tender,
    outcome: Outcome,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Protest | None:
    """When the player won: does a losing rival protest (module docstring)? Round 0 only."""
    if not outcome.player_won or tender.round > 0:
        return None
    pb = balance.government.protests
    g = draws.gen(rng, tender.award_turn, draws.AWARD, tender.id, tender.round, 2)
    chance = pb.rival_chance * (pb.large_mult if is_large(tender, balance) else 1.0)
    winners = {c.name for c in outcome.winners}
    losers = [
        c
        for c in rival_candidates(
            state,
            tender,
            draws.gen(rng, tender.award_turn, draws.AWARD, tender.id, tender.round),
            balance,
            data,
        )
        if c.name not in winners
    ]
    for c in losers:
        if float(g.random()) < min(1.0, chance):
            delay = int(g.integers(round(pb.delay_months.lo), round(pb.delay_months.hi) + 1))
            eff = file(data).protest_year(year_of(state.turn)).effectiveness
            return Protest(
                tender_id=tender.id,
                by=c.name,
                company_id=c.company_id,
                turn=state.turn,
                until=state.turn + delay,
                sustain=float(g.random()) < eff,
            )
    return None


def player_protest(
    state: GameState,
    tender: Tender,
    company_id: int,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Protest:
    pb = balance.government.protests
    g = draws.gen(rng, state.turn, draws.AWARD, tender.id, tender.round, PLAYER_PROTEST)
    delay = int(g.integers(round(pb.delay_months.lo), round(pb.delay_months.hi) + 1))
    eff = file(data).protest_year(year_of(state.turn)).effectiveness
    return Protest(
        tender_id=tender.id,
        by=state.company(company_id).name,
        company_id=company_id,
        turn=state.turn,
        until=state.turn + delay,
        sustain=float(g.random()) < eff,
    )


__all__ = ["gov_bloc"]
