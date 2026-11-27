"""Titles as content assets (docs/formulas.md 65.2, 65.4).

**Production.** A green-lit title spends its budget evenly over its kind's development months
(`kinds.<kind>.dev_months`; the last month takes the remainder), capitalised as a content asset
(debit 1560, credit cash). A strike in the company's home region pauses it (no month done, no
spend, the release a month later). It releases when its months are done and its planned month has
come (a moved date waits).

**Release.** The quality multiplier `q` = lead x team x budget x franchise (clamped to
`quality.range`), where lead = ((creative + vision) / 2 / 10) ** `lead_exponent` x the lead's morale
factor (`no_lead` without one), team = (the assigned unit's development skill / 10) **
`team_exponent` (`no_team`), budget = (budget / the kind's typical budget at scale) **
`budget_exponent`, and franchise = 1 + `franchise_k` x (the last title's audience over the kind's
typical audience - 1) x exp(-years since / `franchise_years`), clamped. The expected audience is
the kind's `audience_m` x q x the overrules' reach (x its platforms' shares, a game); the
audience is that x a mean-one lognormal draw with the kind's `hit_sigma` (stream media (0, title
id)), drawn here and never before. A title whose audience is under `impairment_ratio` of expected
writes its book down to that ratio's share (debit 6770).

**Revenue.** A series or film licensed out earns its audience x the kind's revenue a viewer
(`typical_budget x scale x revenue_mult / audience_m`) over months from release, a geometric share
with time constant `tau_months`, to `tail_months`; one on its company's own service earns nothing
booked (its catalogue value keeps subscribers, tst.sim.media.streaming). A premium game sells its
copies on the same profile at each platform's price x scale, less the store's fee (5150; 12% on
Epic's store for PC from its month, reaching `epic_reach` of PC players), x `gen_lift` for a console
title released within `gen_lift_months` of a generation and x `old_gen_cut` once a later one comes.
A free-to-play game's players start at its audience x `f2p_audience_mult` and fall by `decay` a
month (`live_decay` while live service runs, at `live_cost_share` of the budget a month, 5170);
it earns players x `payer_share` x `spend_cents` x scale, less fees and loot-box rules' cuts.

**Amortisation.** From release the book (after any write-down) is amortised on the kind's schedule
(shares by year, x 1/12 a month; exact, the last month clears it). A cancelled title's book is
written off at once.
"""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.facilities.compute import home_region_of
from tst.sim.facilities.config import month_to_turn
from tst.sim.ledger import CASH, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.media import draws
from tst.sim.media.config import KindBalance, _year_share
from tst.sim.media.data import MONTHS, TINY, end_year_at, file
from tst.sim.media.models import CreativeLead, Title
from tst.sim.money import exact, times
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

CONTENT: Final = "1560_content_assets"
AMORTIZATION: Final = "6770_content_amortization"
CONTENT_REVENUE: Final = "4090_revenue_content"
STORE_FEES: Final = "5150_platform_fees"
OPERATIONS: Final = "5170_media_operations"
MILLION: Final = 1_000_000  # tunable-exempt: audiences are millions
ATTR_MID: Final = 10.0  # tunable-exempt: the attribute scale's middle (1-20)
GAME, SERIES, FILM = "game", "series", "film"  # tunable-exempt: kinds
F2P = "free_to_play"  # tunable-exempt: a monetisation
CONSOLE, PC = "console", "pc"  # tunable-exempt: platforms
EPIC = "epic"  # tunable-exempt: a store
OWN = "own"  # tunable-exempt: a window
F2P_END_SHARE: Final = (
    0.01  # tunable-exempt: a free-to-play title ends below 1% of its first players
)


def kind_of(title: Title, balance: Balance) -> KindBalance:
    return balance.media.kind(title.kind)


def typical_budget_cents(kind: KindBalance, balance: Balance) -> int:
    """A kind's typical budget in the game (x scale)."""
    return times(kind.typical_budget_cents, balance.media.scale)


def lead_factor(lead: CreativeLead | None, morale: float | None, balance: Balance) -> float:
    q = balance.media.quality
    if lead is None:
        return q.no_lead
    base = float(dmath.pow((lead.creative + lead.vision) / 2 / ATTR_MID, q.lead_exponent))
    m = morale if morale is not None else 50.0  # tunable-exempt: morale's neutral point
    return base * (q.morale_floor + q.morale_span * m / 100)


def team_factor(title: Title, state: GameState, balance: Balance, data: GameData) -> float:
    q = balance.media.quality
    if title.unit_id is None:
        return q.no_team
    unit = state.unit(title.unit_id)
    if unit is None or unit.status != "active":
        return q.no_team
    members = [e for e in state.staff(title.company_id) if e.unit_id == unit.id]
    if not members:
        return q.no_team
    cat = data.category(balance.media.games if title.kind == GAME else balance.media.streaming)
    total = 0.0
    for e in members:
        person = state.person(e.person_id)
        total += sum(w * person.skills[k] for k, w in cat.dev_weights.items())
    d = total / len(members)
    return float(dmath.pow(max(d, TINY) / ATTR_MID, q.team_exponent))


def franchise_factor(title: Title, state: GameState, balance: Balance) -> float:
    q = balance.media.quality
    if title.sequel_of is None:
        return 1.0
    prev = state.media.title(title.sequel_of)
    if prev is None or prev.audience is None or prev.released_turn is None:
        return 1.0
    kind = balance.media.kind(prev.kind)
    years = (state.turn - prev.released_turn) / MONTHS
    decay = float(dmath.exp(-years / q.franchise_years))
    mult = 1.0 + q.franchise_k * (prev.audience / kind.audience_m - 1.0) * decay
    return min(q.franchise_range.hi, max(q.franchise_range.lo, mult))


def platform_reach(title: Title, balance: Balance) -> float:
    """A game's share of a typical game's audience on its platforms (1 for series and films)."""
    if title.kind != GAME:
        return 1.0
    shares = balance.media.game_titles.platform_share
    return sum(shares[p] for p in title.platforms)


def lead_morale(title: Title, state: GameState, balance: Balance) -> float | None:
    """The morale a title's quality reads (65.6): its lead's average over production (now, before
    a month is done), less `grievance_keep` of what the title's overrules, cuts and moves cost."""
    if title.lead_person_id is None:
        return None
    now = state.person_state(title.lead_person_id).morale
    avg = title.morale_sum / title.months_done if title.months_done > 0 else now
    if avg is None:
        return None
    return max(0.0, avg - balance.media.talent.grievance_keep * title.grievance)


def quality(title: Title, state: GameState, balance: Balance, data: GameData) -> float:
    """The quality multiplier now (module docstring)."""
    qb = balance.media.quality
    lead = state.media.lead(title.lead_person_id) if title.lead_person_id is not None else None
    if lead is not None and lead.company_id != title.company_id:
        lead = None  # walked or ended
    morale = lead_morale(title, state, balance) if lead is not None else None
    kind = kind_of(title, balance)
    ratio = title.budget_cents / typical_budget_cents(kind, balance)  # money-exact: ratio
    budget = float(dmath.pow(ratio, qb.budget_exponent))
    q = (
        lead_factor(lead, morale, balance)
        * team_factor(title, state, balance, data)
        * budget
        * franchise_factor(title, state, balance)
    )
    return min(qb.range.hi, max(qb.range.lo, q))


def expected_audience(title: Title, q: float, balance: Balance) -> float:
    return kind_of(title, balance).audience_m * q * title.reach * platform_reach(title, balance)


def draw_audience(
    rng: RngFactory, turn: int, title: Title, expected: float, balance: Balance
) -> float:
    """The hit draw (65.2): expected x a mean-one lognormal (stream media (0, title id))."""
    sigma = kind_of(title, balance).hit_sigma
    g = draws.gen(rng, turn, draws.AUDIENCE, title.id)
    z = float(g.standard_normal())
    return expected * float(dmath.exp(sigma * z - sigma * sigma / 2))


def revenue_per_viewer_cents(kind: KindBalance, balance: Balance) -> Fraction:
    """A series or film's revenue a viewer (millions) at the game's scale, exact."""
    return (
        exact(kind.typical_budget_cents) * exact(balance.media.scale) * exact(kind.revenue_mult)
    ) / exact(kind.audience_m)


def month_share(m: int, kind: KindBalance) -> float:
    """Month m's share of a title's revenue (geometric, time constant tau, to tail_months)."""
    if m < 0 or m >= kind.tail_months:
        return 0.0
    keep = float(dmath.exp(-1.0 / kind.tau_months))
    return (1.0 - keep) * float(dmath.pow(keep, m))


def amortised_share(m: int, kind: KindBalance) -> Fraction:
    """The share of the book amortised by the end of month m from release (exact)."""
    year, month = divmod(m, MONTHS)
    sched = kind.amortisation
    if year >= len(sched):
        return Fraction(1)
    done = sum((exact(s) for s in sched[:year]), Fraction())
    return min(Fraction(1), done + exact(sched[year]) * (month + 1) / MONTHS)


def _gen_mult(title: Title, state: GameState, balance: Balance, data: GameData) -> float:
    """A console game's sales multiplier (module docstring)."""
    if CONSOLE not in title.platforms or title.released_turn is None:
        return 1.0
    gb = balance.media.game_titles
    dated = [g.turn for g in file(data).console_generations]
    seeded = [int(d.value) for d in state.media.draws if d.kind == "generation"]
    gens = sorted((*dated, *seeded))
    mult = 1.0
    if any(0 <= title.released_turn - g < gb.gen_lift_months for g in gens):
        mult *= gb.gen_lift
    if any(title.released_turn < g <= state.turn for g in gens):
        mult *= gb.old_gen_cut
    return mult


def _fee(platform: str, title: Title, state: GameState, data: GameData) -> float:
    sf = file(data).store_fees
    if platform == PC and title.store == EPIC and state.turn >= _turn(sf.epic_from):
        return sf.epic
    return sf.default


def _turn(month: str) -> int:
    return month_to_turn(month)


def _loot_mult(state: GameState, data: GameData) -> float:
    """Free-to-play spending's share left by loot-box rules (weighted by the games market's
    regions)."""
    f = file(data)
    year = end_year_at(state.turn)
    out = 0.0
    for region in data.region_keys:
        share = _year_share(f.games_region_share, year, region)
        cut = sum(
            r.cut * r.share for r in f.loot_box_rules if r.region == region and r.active(state.turn)
        )
        out += share * (1.0 - cut)
    return out


def _game_month(
    title: Title, m: int, state: GameState, balance: Balance, data: GameData
) -> tuple[Fraction, Fraction]:
    """A game's (gross, fees) this month, exact cents."""
    gb = balance.media.game_titles
    kind = kind_of(title, balance)
    scale = exact(balance.media.scale)
    reach = platform_reach(title, balance)
    gross = Fraction()
    fees = Fraction()
    if title.monetisation == F2P:
        spend = exact(title.players) * MILLION * exact(gb.payer_share) * gb.spend_cents * scale
        spend *= exact(_loot_mult(state, data))
        for p in title.platforms:
            part = spend * exact(gb.platform_share[p]) / exact(reach)  # money-exact: Fraction
            gross += part
            fees += part * exact(_fee(p, title, state, data))
        return gross, fees
    copies = exact(title.audience or 0.0) * exact(month_share(m, kind)) * MILLION
    copies *= exact(_gen_mult(title, state, balance, data))
    for p in title.platforms:
        part = copies * exact(gb.platform_share[p]) / exact(reach) * gb.price_cents[p] * scale
        if p == PC and title.store == EPIC and state.turn >= _turn(file(data).store_fees.epic_from):
            part *= exact(file(data).store_fees.epic_reach)
        gross += part
        fees += part * exact(_fee(p, title, state, data))
    return gross, fees


def _spend_this_month(title: Title) -> int:
    left = title.budget_cents - title.spent_cents
    months_left = max(1, title.dev_months - title.months_done)
    return max(0, left // months_left) if months_left > 1 else max(0, left)


def strike_on(state: GameState, region: str, data: GameData) -> bool:
    if any(s.region == region and s.active(state.turn) for s in file(data).strikes):
        return True
    from tst.sim.media.talent import seeded_strike_on

    return seeded_strike_on(state, region, data)


def _release(
    title: Title, state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[Title, GameState, list[LedgerEntry], list[LogItem]]:
    """Module docstring: quality, the audience draw, a write-down, the lead's reputation."""
    from tst.sim.media.talent import after_release

    q = quality(title, state, balance, data)
    expected = expected_audience(title, q, balance)
    audience = draw_audience(rng, state.turn, title, expected, balance)
    entries: list[LedgerEntry] = []
    ratio = audience / expected if expected > 0 else 0.0
    book = title.book_cents
    written = 0
    floor = balance.media.quality.impairment_ratio
    if ratio < floor and book > 0:
        written = book - times(book, Fraction(ratio).limit_denominator() / exact(floor))
        if written > 0:
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=title.company_id,
                    memo=f"Content write-down: {title.name}",
                    debit=AMORTIZATION,
                    credit=CONTENT,
                    amount=written,
                )
            )
    players = (
        audience * balance.media.game_titles.f2p_audience_mult if title.monetisation == F2P else 0.0
    )
    out = replace(
        title,
        stage="released",
        released_turn=state.turn,
        quality=q,
        expected=expected,
        audience=audience,
        players=players if title.kind == GAME else 0.0,
        book_cents=book - written,
        written_off_cents=title.written_off_cents + written,
    )
    state = after_release(state, out, ratio, balance)
    logs = [
        inbox_item(
            state.turn,
            title.company_id,
            "media_title_released",
            link_kind="studio",
            link_id=title.id,
            title=title.name,
            audience=f"{audience:,.1f}M",
            expected=f"{expected:,.1f}M",
        )
    ]
    return out, state, entries, logs


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """Every title's month (module docstring), in id order."""
    if not state.media.titles:
        return state, [], []
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    home = home_region_of(state, balance, data)
    out: list[Title] = []
    for title in state.media.titles:
        if title.stage == "development":
            if strike_on(state, home, data) and balance.media.quality.strike_slip:
                out.append(replace(title, release_turn=title.release_turn + 1))
                continue
            if title.months_done < title.dev_months:
                spend = _spend_this_month(title)
                ps = (
                    state.person_state(title.lead_person_id).morale
                    if title.lead_person_id is not None
                    else None
                )
                title = replace(
                    title,
                    morale_sum=title.morale_sum + (ps or 0.0),
                    months_done=title.months_done + 1,
                    spent_cents=title.spent_cents + spend,
                    book_cents=title.book_cents + spend,
                )
                if spend:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=state.turn,
                            company_id=title.company_id,
                            memo=f"Content in production: {title.name}",
                            debit=CONTENT,
                            credit=CASH,
                            amount=spend,
                        )
                    )
            if title.months_done >= title.dev_months and state.turn >= title.release_turn:
                title, state, more, more_logs = _release(title, state, rng, balance, data)
                entries += more
                logs += more_logs
            out.append(title)
            continue
        if title.stage == "released" and title.released_turn is not None:
            title, more = _released_month(title, state, balance, data)
            entries += more
        out.append(title)
    media = replace(state.media, titles=tuple(out))
    return replace(state, media=media), entries, logs


def _released_month(
    title: Title, state: GameState, balance: Balance, data: GameData
) -> tuple[Title, list[LedgerEntry]]:
    assert title.released_turn is not None
    kind = kind_of(title, balance)
    m = state.turn - title.released_turn
    entries: list[LedgerEntry] = []
    gross = Fraction()
    fees = Fraction()
    if title.kind == GAME:
        gross, fees = _game_month(title, m, state, balance, data)
        if title.monetisation == F2P and title.players > 0:
            gb = balance.media.game_titles
            decay = gb.live_decay if title.live_service else gb.decay
            first = (title.audience or 0.0) * gb.f2p_audience_mult
            players = title.players * (1.0 - decay)
            if players < first * F2P_END_SHARE:
                players = 0.0
            title = replace(title, players=players)
            if title.live_service:
                cost = times(title.budget_cents, gb.live_cost_share)
                if cost:
                    entries.append(
                        LedgerEntry.transfer(
                            turn=state.turn,
                            company_id=title.company_id,
                            memo=f"Live-service updates: {title.name}",
                            debit=OPERATIONS,
                            credit=CASH,
                            amount=cost,
                        )
                    )
    elif title.window != OWN:
        gross = (
            exact(title.audience or 0.0)
            * exact(month_share(m, kind))
            * revenue_per_viewer_cents(kind, balance)
        )
    revenue = round(gross)
    fee = round(fees)
    if revenue:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=title.company_id,
                memo=f"Content revenue: {title.name}",
                debit=CASH,
                credit=CONTENT_REVENUE,
                amount=revenue,
            )
        )
    if fee:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=title.company_id,
                memo=f"Store fees: {title.name}",
                debit=STORE_FEES,
                credit=CASH,
                amount=fee,
            )
        )
    net = revenue - fee
    # amortisation: the book at release (after a write-down) over the kind's schedule
    base = title.book_cents + title.amortised_cents
    target = round(exact(base) * amortised_share(m, kind))
    amount = min(title.book_cents, max(0, target - title.amortised_cents))
    if amount:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=title.company_id,
                memo=f"Content amortization: {title.name}",
                debit=AMORTIZATION,
                credit=CONTENT,
                amount=amount,
            )
        )
    return (
        replace(
            title,
            revenue_cents=title.revenue_cents + net,
            book_cents=title.book_cents - amount,
            amortised_cents=title.amortised_cents + amount,
        ),
        entries,
    )


def cancel(title: Title, state: GameState) -> tuple[Title, list[LedgerEntry]]:
    """A cancelled title's book is written off at once (65.2)."""
    entries = []
    if title.book_cents:
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=title.company_id,
                memo=f"Content write-off: {title.name}",
                debit=AMORTIZATION,
                credit=CONTENT,
                amount=title.book_cents,
            )
        )
    return (
        replace(
            title,
            stage="cancelled",
            written_off_cents=title.written_off_cents + title.book_cents,
            book_cents=0,
        ),
        entries,
    )
