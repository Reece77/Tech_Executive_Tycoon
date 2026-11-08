"""Industry rankings (docs/formulas.md 30.4, M15b sub-task 5): three lists each January, as
news and on the Rankings screen, built at December's month end from public or revealed-to-all
measures: revenue, Best places to work (mean morale, pay against market and tenure, companies
of rank.places_min_staff or more) and Most innovative (research leads, eras caused and
launches over rank.years).

A top place (rank.effect_places) in Best places to work adds rank.hiring to the company's
hiring appeal for the year; in Most innovative, rank.brand points on its brand target."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.modes.config import RankWeights
from tst.sim.modes.models import ListKind, Ranking
from tst.sim.money import format_money
from tst.sim.people.models import FOUNDER_ROLE
from tst.sim.state import GameState, player_companies

MONTHS_A_YEAR: Final = 12  # tunable-exempt: calendar
DECEMBER: Final = 11  # tunable-exempt: calendar (turn % 12)
MORALE_SCALE: Final = 100  # tunable-exempt: morale is 0-100
PAY_FULL: Final = 1.25  # tunable-exempt: pay at 1.25 x market scores the full pay measure (M15b)
LIST_LABELS: Final[dict[str, str]] = {
    "revenue": "Top 50 by revenue",
    "places": "Best places to work",
    "innovative": "Most innovative",
}


def _weighted(w: RankWeights, a: float, b: float, c: float) -> float:
    return w.first * a + w.second * b + w.third * c


def _revenue(state: GameState, company_id: int) -> int:
    return sum(state.company(company_id).mrr_history[-MONTHS_A_YEAR:])


def places_measure(
    state: GameState, company_id: int, balance: Balance, data: GameData
) -> float | None:
    """Best places to work (30.4): mean morale, pay against market and tenure of the key
    people on staff; None below rank.places_min_staff staff (pools count toward size)."""
    from tst.sim.org.morale import market_mid_for

    rb = balance.rank
    staff = [e for e in state.staff(company_id) if e.role != FOUNDER_ROLE]
    size = len(staff) + sum(p.headcount for p in state.company_pools(company_id))
    if size < rb.places_min_staff or not staff:
        return None
    morale = [m for e in staff if (m := state.person_state(e.person_id).morale) is not None]
    pay = [
        e.salary_cents / mid for e in staff if (mid := market_mid_for(state, e, balance, data)) > 0
    ]
    tenure = [state.turn - e.start_turn for e in staff]
    m = sum(morale) / len(morale) / MORALE_SCALE if morale else 0.0
    p = min(sum(pay) / len(pay) / PAY_FULL, 1.0) if pay else 0.0
    t = min(sum(tenure) / len(tenure) / rb.tenure_full_months, 1.0)
    return _weighted(rb.places, m, p, t)


def innovative_measure(state: GameState, company_id: int, balance: Balance) -> float:
    """Most innovative (30.4): summed research leads, eras caused and launches in the last
    rank.years."""
    rb = balance.rank
    since = state.turn - rb.years * MONTHS_A_YEAR
    leads = sum(r.lead for r in state.research_leads if r.company_id == company_id)
    eras = sum(1 for a in state.era_arrivals if a.company_id == company_id and a.turn > since)
    launches = sum(
        1
        for p in state.company_products(company_id)
        if p.launched_turn is not None and p.launched_turn > since
    )
    return _weighted(
        rb.innovative,
        min(leads / rb.lead_full, 1.0),
        min(eras / rb.eras_full, 1.0),
        min(launches / rb.launches_full, 1.0),
    )


def lists(
    state: GameState, balance: Balance, data: GameData
) -> dict[ListKind, list[tuple[int, float]]]:
    """Each list's (company id, measure), best first; ties by revenue, then by the stable
    rival key, the player after any rival it ties with (M15a fix: ties went to the lowest
    company id, the player's, so it won a sparse Most innovative list most years)."""
    rb = balance.rank
    held = {h.company_id for h in state.holdings}  # M16: the group's revenue is not a company's
    alive = [c for c in state.ledger_companies() if c.alive and c.id not in held]
    revenue_of = {c.id: _revenue(state, c.id) for c in alive}
    stable = {c.id: (c.is_player, c.rival_key, c.id) for c in alive}

    def order(x: tuple[int, float]) -> tuple[float, int, tuple[bool, tuple[int, ...], int]]:
        return (-x[1], -revenue_of[x[0]], stable[x[0]])

    revenue = sorted(
        ((c.id, float(_revenue(state, c.id))) for c in alive if _revenue(state, c.id) > 0),
        key=order,
    )[: rb.top_revenue]
    places = sorted(
        ((c.id, v) for c in alive if (v := places_measure(state, c.id, balance, data)) is not None),
        key=order,
    )[: rb.top_lists]
    innovative = sorted(
        ((c.id, v) for c in alive if (v := innovative_measure(state, c.id, balance)) > 0),
        key=order,
    )[: rb.top_lists]
    return {"revenue": revenue, "places": places, "innovative": innovative}


def publish(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LogItem, ...]]:
    """December's month end: next January's three lists, and a news item for each company
    the player controls: its place on each list (or "not ranked") and each list's top
    rank.news_top names, linked to the Rankings screen (playtest 4, M15r addendum b)."""
    if state.turn % MONTHS_A_YEAR != DECEMBER:
        return state, ()
    january = state.turn + 1
    if any(r.turn == january for r in state.rankings):
        return state, ()
    new: list[Ranking] = []
    for kind, ranked in lists(state, balance, data).items():
        new += [
            Ranking(turn=january, kind=kind, place=i + 1, company_id=cid, value=value)
            for i, (cid, value) in enumerate(ranked)
        ]
    new.sort(key=lambda r: (r.kind, r.place))  # the order a save loads them in
    state = replace(state, rankings=(*state.rankings, *new))
    logs = []
    names = {c.id: c.name for c in state.companies}
    for company in player_companies(state):
        if any(h.company_id == company.id for h in state.holdings):
            continue  # M16 (31.2): one January item, for the company the player runs
        params: dict[str, str] = {}
        for list_kind in LIST_LABELS:
            listed = [r for r in new if r.kind == list_kind]
            own = next((r for r in listed if r.company_id == company.id), None)
            params[f"{list_kind}_place"] = f"#{own.place}" if own else "not ranked"
            names_top = ", ".join(
                f"{r.place}. {names[r.company_id]}" for r in listed[: balance.rank.news_top]
            )
            params[f"{list_kind}_top"] = names_top or "nobody yet"
        mine_all = [r for r in new if r.company_id == company.id]
        places = "; ".join(f"{LIST_LABELS[r.kind]}: #{r.place}" for r in mine_all)
        top = next((r for r in new if r.kind == "revenue" and r.place == 1), None)
        logs.append(
            inbox_item(
                january - 1,
                company.id,
                "rankings_published",
                link_kind="rankings",
                link_id=0,
                year=str(turn_to_ym(january)[0]),
                places=places or "no place yet",
                leader=names[top.company_id] if top else "nobody",
                revenue=format_money(round(top.value)) if top else "-",
                **params,
            )
        )
    return state, tuple(logs)


def placed(state: GameState, company_id: int, kind: ListKind, balance: Balance) -> bool:
    """A top rank.effect_places place in this year's `kind` list, while its effect runs."""
    rb = balance.rank
    return any(
        r.kind == kind
        and r.company_id == company_id
        and r.place <= rb.effect_places
        and r.turn <= state.turn < r.turn + rb.effect_months
        for r in state.rankings
    )


def hiring_bonus(state: GameState, company_id: int, balance: Balance) -> float:
    """+rank.hiring hiring appeal for a top Best places to work place (30.4)."""
    return balance.rank.hiring if placed(state, company_id, "places", balance) else 0.0


def brand_bonus(state: GameState, company_id: int, balance: Balance) -> float:
    """+rank.brand brand-target points for a top Most innovative place (30.4)."""
    return balance.rank.brand if placed(state, company_id, "innovative", balance) else 0.0
