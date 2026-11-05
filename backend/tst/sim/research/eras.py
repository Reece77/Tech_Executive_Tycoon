"""Era milestones (docs/formulas.md 21.4): arrival on the historical month or earlier by
threshold, the boosts they bring to demand growth and adoption, and the History and news
lines. Arrival is checked in phase 3 after research progress; growth is read in phase 9.
"""

from __future__ import annotations

from dataclasses import replace

from tst.sim.calendar import format_turn, turn_to_ym
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import format_money
from tst.sim.press.moments import queue_moment
from tst.sim.products.models import SELLING
from tst.sim.research import levels
from tst.sim.research.data import EraDef, rate_in
from tst.sim.research.models import EraArrival, EraWindow
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, player_companies, with_era_arrival, with_era_window

TREND_MONTHS = 12  # tunable-exempt: the pre-era trend's window (27.3: "12-month trend")


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
    """Base growth plus the era boosts running this month (21.4). A segment whose demand
    follows other markets (M12b, 26.3: chips' `growth_follows`) takes their mean growth, era
    boosts included, as its base."""
    year = turn_to_ym(state.turn)[0]
    follows = (data.category(category).growth_follows or {}).get(segment) if segment else None
    if follows:
        base = sum(annual_growth(state, data, c) for c in follows) / len(follows)
    else:
        base = base_growth(data, category, year)
    return base + growth_boost(state, data, category, segment)


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
    state: GameState, data: GameData, balance: Balance, rng: RngFactory
) -> tuple[GameState, tuple[LogItem, ...]]:
    """Phase 3, after research progress: each era not yet arrived arrives on its
    historical month (a future era: its seeded scheduled month, 26.4), or this month if a
    company's level reaches its threshold (21.4). In eras.yaml order, so an earlier era's +5
    counts toward a later one's level."""
    logs: list[LogItem] = []
    for index, era in enumerate(data.eras.eras):
        if state.era_arrival(era.key) is not None:
            continue
        hist = levels.scheduled_turn(era, index, rng)
        found = causer(state, data, balance, era) if state.turn < hist else None
        if state.turn < hist and found is None:
            continue
        cid = found[0] if found else None
        arrival = EraArrival(era.key, state.turn, cid, max(0, hist - state.turn))
        state = with_era_arrival(state, arrival)
        logs += [  # every company the player controls hears (ADR-0020 1; M12r)
            era_news(state, data, balance, era, arrival, c.id) for c in player_companies(state)
        ]
        if cid is not None and cid in {c.id for c in player_companies(state)}:
            state = with_era_window(state, _window(state, data, era, cid))  # 27.3 (M13b)
            state = queue_moment(state, cid, "era", {"era": era.label})  # M14b (29.1)
    state, reports = era_reports(state, data, balance)
    return state, (*logs, *reports)


def _mrr(state: GameState, product_id: int) -> int:
    return round(
        sum(s.customers * (s.price_cents or 0) for s in state.segments_of(product_id))
        + sum(s.customers * (s.price_cents or 0) for s in state.regional_segments_of(product_id))
    )


def _customers(state: GameState, product_id: int) -> float:
    return sum(s.customers for s in state.segments_of(product_id)) + sum(
        s.customers for s in state.regional_segments_of(product_id)
    )


def affected(state: GameState, era: EraDef, company_id: int) -> list[int]:
    """The company's selling products in the era's categories (27.3)."""
    return [
        p.id
        for p in state.company_products(company_id)
        if p.status in SELLING and p.category in era.categories
    ]


def _window(state: GameState, data: GameData, era: EraDef, company_id: int) -> EraWindow:
    """The first mover's baseline at arrival (27.3)."""
    history = state.company(company_id).mrr_history
    trend = 0.0
    if len(history) > TREND_MONTHS and history[-1 - TREND_MONTHS] > 0 and history[-1] > 0:
        trend = (history[-1] / history[-1 - TREND_MONTHS]) ** (1 / TREND_MONTHS) - 1
    demand = tuple(
        (c, sum(m.addressable for m in state.markets if m.category == c)) for c in era.categories
    )
    return EraWindow(
        era.key,
        company_id,
        state.turn,
        tuple(
            (pid, _customers(state, pid), _mrr(state, pid))
            for pid in affected(state, era, company_id)
        ),
        trend,
        demand,
    )


def era_reports(
    state: GameState, data: GameData, balance: Balance
) -> tuple[GameState, tuple[LogItem, ...]]:
    """At a first-mover window's end, the era report (27.3): each affected product's customers
    and MRR against its pre-era trend, each category's demand against its pre-era path (base
    growth, no boost), and what the window added."""
    months = balance.rnd.first_mover_months
    logs: list[LogItem] = []
    for w in state.era_windows:
        if w.reported or state.turn < w.start_turn + months:
            continue
        era = next(e for e in data.eras.eras if e.key == w.era_key)
        lines = []
        added = 0
        for pid, customers, mrr in w.products:
            product = state.product(pid)
            if product is None:
                continue
            growth = (1 + w.trend) ** months
            expected = round(mrr * growth)
            now = _mrr(state, pid)
            added += now - expected
            lines.append(
                f"{product.name}: {_customers(state, pid):,.0f} customers (trend "
                f"{customers * growth:,.0f}), {format_money(now)} a month (trend "
                f"{format_money(expected)})"
            )
        for category, then in w.demand:
            path = then
            for t in range(w.start_turn, state.turn):
                path *= (1 + base_growth(data, category, turn_to_ym(t)[0])) ** (1 / TREND_MONTHS)
            now_d = sum(m.addressable for m in state.markets if m.category == category)
            lines.append(
                f"{data.category(category).label} demand {now_d:,.0f} against "
                f"{path:,.0f} on its pre-era path"
            )
        logs.append(
            inbox_item(
                state.turn,
                w.company_id,
                "era_report",
                era=era.label,
                months=months,
                lines="; ".join(lines) if lines else "no products in its markets",
                added_cents=added,
            )
        )
        state = with_era_window(state, replace(w, reported=True))
    return state, tuple(logs)


def era_news(
    state: GameState,
    data: GameData,
    balance: Balance,
    era: EraDef,
    arrival: EraArrival,
    observer_id: int,
) -> LogItem:
    """One player company's inbox note for an arrived era (21.4): who caused it, how
    early, and the first mover's head start when the observer caused it. The causing
    company is named apart from the observer, so another company of the player's group is
    named, not called "your research" (ADR-0020 1; M12r)."""
    causer = arrival.company_id
    if causer is None:
        who = "on schedule"
    elif causer == observer_id:
        who = f"{arrival.months_early} months early, pulled forward by your research"
    else:
        name = state.company(causer).name
        who = f"{arrival.months_early} months early, pulled forward by {name}"
    categories = ", ".join(data.category(c).label for c in era.categories) or "no market yet"
    rnd = balance.rnd
    appeal = f", x{rnd.first_mover_appeal:g} appeal" if rnd.first_mover_appeal != 1 else ""
    note = (
        f" First-mover head start: for {rnd.first_mover_months} months your {categories}"
        f" products get +{rnd.first_mover_cap:g} on their quality cap"
        f"{appeal}, +{rnd.first_mover_brand:g} on their brand target,"
        f" and your {levels.domain_def(data, era.domain).label} lead does not decay."
        + _products_line(state, era, observer_id, balance)
        if causer == observer_id
        else ""
    )
    return inbox_item(
        state.turn,
        observer_id,
        "era_arrived",
        era=era.label,
        when=who,
        markets=categories,
        note=note,
    )


def _products_line(state: GameState, era: EraDef, company_id: int, balance: Balance) -> str:
    """The first mover's affected products with what the window gives them (27.3)."""
    rnd = balance.rnd
    appeal = f"; appeal x{rnd.first_mover_appeal:g}" if rnd.first_mover_appeal != 1 else ""
    items = []
    for pid in affected(state, era, company_id):
        p = state.product(pid)
        if p is None:
            continue
        items.append(
            f"{p.name} (quality {p.quality:.0f}, cap +{rnd.first_mover_cap:g}; brand "
            f"{p.brand:.0f}, target +{rnd.first_mover_brand:g}{appeal})"
        )
    return (
        " Affected: " + "; ".join(items) + "."
        if items
        else " You have no product in these markets yet."
    )


def arrival_label(state: GameState, era: EraDef, arrival: EraArrival) -> str:
    """'June 2017, on schedule' or 'March 2016, 15 months early (Kestrel)' (History)."""
    month = format_turn(arrival.turn)
    if arrival.company_id is None:
        return f"{month}, on schedule"
    name = state.company(arrival.company_id).name
    return f"{month}, {arrival.months_early} months early ({name})"
