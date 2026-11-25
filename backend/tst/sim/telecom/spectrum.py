"""Spectrum auctions and licences (docs/formulas.md 62.2).

**Auctions.** Each of telecom.yaml's dated auctions is announced `auction.notice_months` before
its month; from `telecom.start` every licence area that auctions spectrum gets seeded ones, every
`auction.seeded_every` years (months, bands, blocks and bidders drawn on stream telecom (0, 2,
area index, n); hidden until announced). An auction runs in its month as a **clock auction**: a
block's price starts at the reserve and rises `auction.increment` a round while the bidders still
in ask for more blocks than there are; a bidder stays in while the price is at most its value a
block. The rest are awarded at the last price (uniform), and blocks no one still wants at it are
unsold. A bidder wins at most `auction.max_blocks_share` of the blocks.

- **Rivals' values and demands** are drawn when the auction runs (stream telecom (1, auction id))
  and never stored or shown: a dated auction's named winners want their data blocks at values a
  block of the data's price x `winner_value`; bidders outside the game hold the data's other
  blocks; and one marginal loser values a block at the data's price x `loser_value`, so without
  the player an auction ends near its real proceeds. A seeded auction's bidders are the region's
  operators, each wanting a share of the blocks at the reserve x `seeded_value`.
- **The player** registers a number of blocks and a limit a block (`bid_spectrum`); it stays in
  while the price is at most its limit. It pays the price x blocks won in the auction month.

**Licences** carry `mhz x won / blocks` of the band in the auction's area for its term, booked to
1540 spectrum licences and amortized straight line (6760). At the term's end a living company's
licence renews at `auction.renewal_share` of its price; a failed company's expires. A coverage
obligation is checked by the region's telecom regulator (tst.sim.telecom.regulation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, SPECTRUM, LedgerEntry
from tst.sim.ledger import SPECTRUM_AMORTIZATION as AMORTIZATION
from tst.sim.log import LogItem, inbox_item
from tst.sim.rng import RngFactory
from tst.sim.state import GameState
from tst.sim.telecom import draws
from tst.sim.telecom.config import BANDS, AuctionDef
from tst.sim.telecom.data import MONTHS, file, in_telecom, region_index
from tst.sim.telecom.models import Auction, Award, SpectrumLicence

OTHERS: Final = "Bidders outside the game"  # tunable-exempt: a label
MARGINAL: Final = "Other bidders"  # tunable-exempt: a label
PLAYER_KEY: Final = -1  # tunable-exempt: the player's bidder index


@dataclass(frozen=True, slots=True)
class Bidder:
    name: str
    company_id: int | None
    blocks: int
    value_cents: float  # a block (hidden)


def _round_up(x: float) -> int:
    return max(1, math.ceil(x))


def clock(
    bidders: list[Bidder], blocks: int, reserve: int, increment: float, max_rounds: int
) -> tuple[int, int, dict[int, int]]:
    """(rounds, final price a block, blocks won by bidder index): module docstring."""
    price = reserve
    rounds = 1
    while rounds < max_rounds:
        demand = sum(b.blocks for b in bidders if b.value_cents >= price)
        if demand <= blocks:
            break
        price = _round_up(price * (1.0 + increment))
        rounds += 1
    won: dict[int, int] = {}
    left = blocks
    active = [i for i, b in enumerate(bidders) if b.value_cents >= price]
    active.sort(key=lambda i: (-bidders[i].value_cents, i))
    for i in active:
        n = min(bidders[i].blocks, left)
        if n > 0:
            won[i] = n
            left -= n
    return rounds, price, won


# --- Announcing ---------------------------------------------------------------------------------


def _from_def(d: AuctionDef, auction_id: int, scale: float) -> Auction:
    return Auction(
        id=auction_id,
        key=d.key,
        label=d.label,
        region=d.region,
        area=d.area,
        band=d.band,
        mhz=d.mhz,
        blocks=d.blocks,
        reserve_cents=max(1, round(d.reserve_cents * scale)),
        turn=d.turn,
        term_years=d.term_years,
        obligation=d.obligation,
        obligation_years=d.obligation_years,
        history=True,
    )


def _area_index(region: str, area: str, data: GameData) -> int:
    return region_index(region, data) * 100 + [
        a.key for a in file(data).region(region).areas
    ].index(area)


def _seeded_auction(
    state: GameState,
    rng: RngFactory,
    region: str,
    area: str,
    turn: int,
    n: int,
    auction_id: int,
    balance: Balance,
    data: GameData,
) -> Auction:
    ab = balance.telecom.auction
    r = file(data).region(region)
    a = r.area(area)
    assert a is not None
    g = draws.gen(rng, turn, draws.WORLD, draws.SCHEDULE, _area_index(region, area, data), n, 1)
    band = BANDS[int(g.integers(0, len(BANDS)))]
    blocks = round(ab.seeded_blocks.lo + (ab.seeded_blocks.hi - ab.seeded_blocks.lo) * g.random())
    people = r.mobile_at(2025.0) * 1_000_000 * a.share  # tunable-exempt: millions
    mhz = ab.seeded_mhz[band]
    reserve = ab.seeded_reserve_cents_mhz_pop[band] * mhz * people * balance.telecom.scale / blocks
    year = 2010 + turn // MONTHS  # tunable-exempt: turn 0 is January 2010
    return Auction(
        id=auction_id,
        key=f"seeded_{region}_{area}_{n}",
        label=f"{a.label} {band}-band auction ({year})",
        region=region,
        area=area,
        band=band,
        mhz=mhz,
        blocks=max(1, blocks),
        reserve_cents=max(1, round(reserve)),
        turn=turn,
        term_years=ab.seeded_term_years,
        obligation=ab.seeded_obligation,
        obligation_years=ab.seeded_obligation_years,
        history=False,
    )


def _schedule_next(
    rng: RngFactory, region: str, area: str, after: int, n: int, balance: Balance, data: GameData
) -> int:
    ab = balance.telecom.auction
    g = draws.gen(rng, after, draws.WORLD, draws.SCHEDULE, _area_index(region, area, data), n, 0)
    years = ab.seeded_every.lo + (ab.seeded_every.hi - ab.seeded_every.lo) * g.random()
    return after + max(1, round(years * MONTHS))


def announce_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Dated auctions `notice_months` ahead, and from telecom.start the seeded schedule."""
    tb = balance.telecom
    ab = tb.auction
    f = file(data)
    t = state.telecom
    keys = {a.key for a in t.auctions}
    added: list[Auction] = []
    next_id = t.next_auction_id()
    for d in f.auctions:
        if d.key in keys or not d.turn - ab.notice_months <= state.turn <= d.turn:
            continue
        added.append(_from_def(d, next_id, tb.scale))
        next_id += 1
    world = t.world
    schedule = dict(world.next_auction)
    if state.turn >= tb.start_turn:
        for r in f.regions:
            for a in r.areas:
                if a.method != "auction":
                    continue
                key = f"{r.key}/{a.key}"
                n = sum(
                    1 for x in (*t.auctions, *added) if x.key.startswith(f"seeded_{r.key}_{a.key}_")
                )
                if key not in schedule:
                    schedule[key] = _schedule_next(rng, r.key, a.key, state.turn, n, balance, data)
                due = schedule[key]
                if state.turn >= due - ab.notice_months:
                    added.append(
                        _seeded_auction(state, rng, r.key, a.key, due, n, next_id, balance, data)
                    )
                    next_id += 1
                    schedule[key] = _schedule_next(rng, r.key, a.key, due, n + 1, balance, data)
    if not added and schedule == dict(world.next_auction):
        return state, []
    world = replace(world, next_auction=tuple(sorted(schedule.items())))
    state = replace(state, telecom=replace(t, auctions=(*t.auctions, *added), world=world))
    logs = []
    for c in state.companies:
        if not c.is_player or not c.alive or not in_telecom(state, c.id, balance):
            continue
        for x in added:
            logs.append(
                inbox_item(
                    state.turn,
                    c.id,
                    "spectrum_auction_announced",
                    auction=x.label,
                    region=data.region(x.region).label,
                    blocks=str(x.blocks),
                    mhz=f"{x.mhz:g}",
                    reserve_cents=x.reserve_cents,
                    month=format_turn(x.turn),
                )
            )
    return state, logs


# --- Running ------------------------------------------------------------------------------------


def _rival_bidders(
    state: GameState, auction: Auction, rng: RngFactory, balance: Balance, data: GameData
) -> list[Bidder]:
    ab = balance.telecom.auction
    g = draws.gen(rng, auction.turn, draws.AUCTION, auction.id)
    cap = max(1, int(auction.blocks * ab.max_blocks_share))
    out: list[Bidder] = []
    if auction.history:
        d = file(data).auction(auction.key)
        assert d is not None
        price = d.gross_cents * balance.telecom.scale / d.blocks
        named = 0
        for company, n in sorted(d.winners.items()):
            c = next((x for x in state.companies if x.name == company and x.alive), None)
            v = price * (
                ab.winner_value.lo + (ab.winner_value.hi - ab.winner_value.lo) * g.random()
            )
            out.append(Bidder(company, c.id if c else None, min(cap, n), v))
            named += n
        rest = d.blocks - named
        if rest > 0:
            v = price * (
                ab.winner_value.lo + (ab.winner_value.hi - ab.winner_value.lo) * g.random()
            )
            out.append(Bidder(OTHERS, None, rest, v))
        v = price * (ab.loser_value.lo + (ab.loser_value.hi - ab.loser_value.lo) * g.random())
        out.append(Bidder(MARGINAL, None, max(1, d.blocks // 4), v))
        return out
    f = file(data)
    ops = [o for o in f.operators if o.region == auction.region and o.mobile]
    lo, hi = ab.seeded_bidders.lo, ab.seeded_bidders.hi
    n = max(1, round(lo + (hi - lo) * g.random()))
    names = sorted({o.company for o in ops})
    chosen = names[:n] if len(names) >= n else names
    for name in chosen:
        c = next((x for x in state.companies if x.name == name and x.alive), None)
        want = max(1, round(auction.blocks / max(1, len(chosen)) * (0.8 + 0.8 * g.random())))
        v = auction.reserve_cents * (
            ab.seeded_value.lo + (ab.seeded_value.hi - ab.seeded_value.lo) * g.random()
        )
        out.append(Bidder(name, c.id if c else None, min(cap, want), v))
    if not out:
        v = auction.reserve_cents * ab.seeded_value.lo
        out.append(Bidder(MARGINAL, None, max(1, auction.blocks // 2), v))
    return out


def run_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Auctions whose month is this one run; the player's wins become licences (module
    docstring)."""
    t = state.telecom
    due = [a for a in t.auctions if a.status == "announced" and a.turn == state.turn]
    if not due:
        return state, [], []
    ab = balance.telecom.auction
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    licences = list(t.licences)
    next_licence = t.next_licence_id()
    out: dict[int, Auction] = {}
    for a in due:
        bidders = _rival_bidders(state, a, rng, balance, data)
        player = a.bid_company_id
        mine_index: int | None = None
        if player is not None and a.bid_blocks > 0:
            company = state.company(player)
            cap = max(1, int(a.blocks * ab.max_blocks_share))
            mine_index = len(bidders)
            bidders.append(
                Bidder(company.name, player, min(cap, a.bid_blocks), float(a.bid_limit_cents))
            )
        rounds, price, won = clock(bidders, a.blocks, a.reserve_cents, ab.increment, ab.max_rounds)
        awards = []
        for i, n in sorted(won.items()):
            b = bidders[i]
            paid = price * n
            awards.append(Award(b.name, b.company_id, n, paid))
            if player is not None and i == mine_index:
                licences.append(
                    SpectrumLicence(
                        id=next_licence,
                        company_id=player,
                        region=a.region,
                        area=a.area,
                        band=a.band,
                        mhz=a.mhz * n / a.blocks,
                        auction_id=a.id,
                        paid_cents=paid,
                        turn=state.turn,
                        expires_turn=state.turn + a.term_years * MONTHS,
                        obligation=a.obligation,
                        obligation_turn=(
                            state.turn + a.obligation_years * MONTHS if a.obligation > 0 else None
                        ),
                    )
                )
                next_licence += 1
                entries.append(
                    LedgerEntry.transfer(
                        turn=state.turn,
                        company_id=player,
                        memo=f"Spectrum: {a.label}",
                        debit=SPECTRUM,
                        credit=CASH,
                        amount=paid,
                    )
                )
        out[a.id] = replace(
            a, status="closed", rounds=rounds, price_cents=price, awards=tuple(awards)
        )
        if player is not None and a.bid_blocks > 0:
            mine = won.get(mine_index, 0) if mine_index is not None else 0
            logs.append(
                inbox_item(
                    state.turn,
                    player,
                    "spectrum_auction_result",
                    auction=a.label,
                    rounds=str(rounds),
                    price_cents=price,
                    won=str(mine),
                    asked=str(a.bid_blocks),
                )
            )
    auctions = tuple(out.get(a.id, a) for a in t.auctions)
    state = replace(state, telecom=replace(t, auctions=auctions, licences=tuple(licences)))
    return state, entries, logs


# --- Licences: amortization and renewal ---------------------------------------------------------


def licences_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Amortization of every active licence, and renewals at the term's end (module docstring):
    a living company renews (its cash may go negative, as any bill's)."""
    t = state.telecom
    if not t.licences:
        return state, [], []
    ab = balance.telecom.auction
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    out = []
    for lic in t.licences:
        if lic.status != "active":
            out.append(lic)
            continue
        term = max(1, lic.expires_turn - lic.turn)
        months = min(term, state.turn - lic.turn + 1)
        total = lic.paid_cents * months // term
        charge = total - lic.amortized_cents
        if charge > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=lic.company_id,
                    memo="Spectrum amortization",
                    debit=AMORTIZATION,
                    credit=SPECTRUM,
                    amount=charge,
                )
            )
            lic = replace(lic, amortized_cents=total)
        if state.turn >= lic.expires_turn - 1:
            fee = round(lic.paid_cents * ab.renewal_share)
            company = state.company(lic.company_id)
            if company is not None and company.alive:
                if fee > 0:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=state.turn,
                            company_id=lic.company_id,
                            memo="Spectrum renewal",
                            debit=SPECTRUM,
                            credit=CASH,
                            amount=fee,
                        )
                    )
                lic = replace(
                    lic,
                    paid_cents=fee,
                    amortized_cents=0,
                    turn=state.turn + 1,
                    expires_turn=state.turn + 1 + term,
                )
                log_kind = "spectrum_renewed"
            else:
                lic = replace(lic, status="expired")
                log_kind = "spectrum_expired"
            logs.append(
                inbox_item(
                    state.turn,
                    lic.company_id,
                    log_kind,
                    region=data.region(lic.region).label,
                    band=lic.band,
                    mhz=f"{lic.mhz:g}",
                    fee_cents=fee,
                )
            )
        out.append(lic)
    return replace(state, telecom=replace(t, licences=tuple(out))), entries, logs
