"""Era milestones (docs/formulas.md 21.4): arrival on the historical month or earlier by
threshold, the boosts they bring to demand growth and adoption, and the History and news
lines. Arrival is checked in phase 3 after research progress; growth is read in phase 9.
"""

from __future__ import annotations

from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.research import levels
from tst.sim.research.data import EraDef, rate_in
from tst.sim.research.models import EraArrival
from tst.sim.state import GameState, with_era_arrival


def base_growth(data: GameData, category: str, year: int) -> float:
    """A category's annual demand growth without era boosts: eras.yaml's base_growth for
    categories whose eras are in the tuned curves, else categories.yaml's (21.4)."""
    table = data.eras.base_growth.get(category)
    if table:
        return rate_in(table, year)
    return data.category(category).growth_in(year)


def _active(arrival: EraArrival | None, months: int, turn: int) -> bool:
    return arrival is not None and arrival.turn <= turn < arrival.turn + months


def growth_boost(state: GameState, data: GameData, category: str, segment: str | None) -> float:
    """Annual growth points the arrived eras add this month; `segment` None counts only the
    boosts that cover every segment (the category's own growth, for startups and the API)."""
    total = 0.0
    for era in data.eras.eras:
        arrival = state.era_arrival(era.key)
        if arrival is None:
            continue
        for b in era.boosts:
            if b.category != category or not _active(arrival, b.months, state.turn):
                continue
            if (segment is None and b.segments is None) or (
                segment is not None and b.covers(category, segment)
            ):
                total += b.growth
    return total


def annual_growth(
    state: GameState, data: GameData, category: str, segment: str | None = None
) -> float:
    """Base growth plus the era boosts running this month (21.4)."""
    year = turn_to_ym(state.turn)[0]
    return base_growth(data, category, year) + growth_boost(state, data, category, segment)


def adoption_factor(state: GameState, data: GameData, category: str, segment: str) -> float:
    """The product of the running eras' adoption multipliers for a segment (21.4)."""
    factor = 1.0
    for era in data.eras.eras:
        arrival = state.era_arrival(era.key)
        for b in era.boosts:
            if (
                b.adoption != 1
                and b.covers(category, segment)
                and _active(arrival, b.months, state.turn)
            ):
                factor *= b.adoption
    return factor


def causer(
    state: GameState, data: GameData, balance: Balance, era: EraDef
) -> tuple[int, float] | None:
    """The company whose level in the era's domain reaches its threshold this month, the
    highest level first, ties by company id; None if nobody does (21.4)."""
    need = levels.threshold(data, balance, era)
    best: tuple[int, float] | None = None
    companies = sorted(
        {r.company_id for r in state.research_leads if r.domain == era.domain and r.lead > 0}
    )
    for cid in companies:
        if not state.company(cid).alive:
            continue
        lvl = levels.level(state, data, balance, cid, era.domain)
        if lvl >= need and (best is None or lvl > best[1]):
            best = (cid, lvl)
    return best


def arrive_eras(
    state: GameState, data: GameData, balance: Balance
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 3, after research progress: each era not yet arrived arrives on its
    historical month, or this month if a company's level reaches its threshold (21.4).
    In eras.yaml order, so an earlier era's +5 counts toward a later one's level."""
    logs: list[LogItem] = []
    for era in data.eras.eras:
        if state.era_arrival(era.key) is not None:
            continue
        hist = levels.historical_turn(era)
        found = causer(state, data, balance, era) if state.turn < hist else None
        if state.turn < hist and found is None:
            continue
        cid = found[0] if found else None
        arrival = EraArrival(era.key, state.turn, cid, max(0, hist - state.turn))
        state = with_era_arrival(state, arrival)
        logs.append(era_news(state, data, balance, era, arrival))
    return state, tuple(logs)


def era_news(
    state: GameState, data: GameData, balance: Balance, era: EraDef, arrival: EraArrival
) -> LogItem:
    """The player's inbox note for an arrived era (21.4): who caused it, how early, and the
    first mover's head start when it is the player's."""
    player = state.player.id
    if arrival.company_id is None:
        who = "on schedule"
    elif arrival.company_id == player:
        who = f"{arrival.months_early} months early, pulled forward by your research"
    else:
        name = state.company(arrival.company_id).name
        who = f"{arrival.months_early} months early, pulled forward by {name}"
    categories = ", ".join(data.category(c).label for c in era.categories) or "no market yet"
    rnd = balance.rnd
    note = (
        f" First-mover head start: for {rnd.first_mover_months} months your {categories}"
        f" products get +{rnd.first_mover_cap:g} on their quality cap and"
        f" +{rnd.first_mover_brand:g} on their brand target, and your"
        f" {levels.domain_def(data, era.domain).label} lead does not decay."
        if arrival.company_id == player
        else ""
    )
    return inbox_item(
        state.turn,
        player,
        "era_arrived",
        era=era.label,
        when=who,
        markets=categories,
        note=note,
    )


def arrival_label(state: GameState, era: EraDef, arrival: EraArrival) -> str:
    """'June 2017, on schedule' or 'March 2016, 15 months early (Kestrel)' (History)."""
    month = format_turn(arrival.turn)
    if arrival.company_id is None:
        return f"{month}, on schedule"
    name = state.company(arrival.company_id).name
    return f"{month}, {arrival.months_early} months early ({name})"
