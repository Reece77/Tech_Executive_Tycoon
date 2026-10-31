"""Rival startups (docs/formulas.md 15.4): founded in phase 9, built and launched like the
player's products by their own individuals, funded or cut back when cash runs low, and gone
when bankrupt (14.7).

Randomness: founding uses stream `rival_spawn`, key `(category_index,)`, one generator per
category per month, draws in this order: the founding roll; then, if founded, the name, the
personality, the team size, the cash, the number of segments and the segments. The team is
generated with stream `people_gen`, key `(company_id, 1)`. Funding answers draw from the
startup's monthly `rivals` generator (decisions.py), after its action noise.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np

from tst.sim.calendar import turn_to_ym, ym_to_turn
from tst.sim.data_models import FUNCTIONS, Balance, CategoryDef, GameData
from tst.sim.finance.fundraising import climate
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rivals.models import RivalMove
from tst.sim.rivals.setup import hire_key_people, key_people_split
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    with_company,
    with_product,
    with_product_segment,
    with_rival_move,
)

STARTUP_STAGE = 1  # tunable-exempt: a founded startup is a garage startup (spec section 3)
TEAM_STREAM_PART = 1  # tunable-exempt: second key part of a startup team's people_gen stream
FOUNDER_LEVEL = "exec"  # tunable-exempt: the startup's founder is its top person
TEAM_LEVEL = "mid"  # tunable-exempt: a startup's first employees (15.4 does not say)
ENTRANT_LEVEL = "senior"  # tunable-exempt: every entrant's people (18.7)


def alive_startups(state: GameState, data: GameData | None = None) -> list[CompanyState]:
    """Startups in business; with `data`, without the scheduled entrants (18.7)."""
    return [
        c
        for c in state.companies
        if c.is_startup and c.failed_turn is None and not (data and is_entrant(c, data))
    ]


def _record(
    state: GameState, company: CompanyState, action: str, detail: str, product_id: int | None = None
) -> tuple[GameState, RivalMove]:
    move_id, ids = state.next_ids.take("rival_move")
    move = RivalMove(
        id=move_id,
        company_id=company.id,
        turn=state.turn,
        action=action,
        product_id=product_id,
        detail=f"{company.name} {detail}",
    )
    return with_rival_move(replace(state, next_ids=ids), move), move


def found_startups(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[RivalMove, ...]]:
    """Phase 9: each category may found a startup (15.4), by categories.yaml order."""
    sb = balance.rivals.startup
    entries: list[LedgerEntry] = []
    moves: list[RivalMove] = []
    mood = climate(state, data)
    for index, category in enumerate(data.categories):
        if len(alive_startups(state, data)) >= sb.max_alive:  # entrants do not count (18.7)
            break
        gen = rng.stream(state.turn, "rival_spawn", index)
        chance = sb.found_rate * mood * (1 + category.growth_in(turn_to_ym(state.turn)[0]))
        if float(gen.random()) >= chance:
            continue
        taken = {c.name for c in state.companies}
        names = [n for n in data.startup_names if n not in taken]
        if not names:
            continue
        name = names[int(gen.integers(0, len(names)))]
        personality = sb.personalities[int(gen.integers(0, len(sb.personalities)))]
        team = int(gen.integers(int(sb.team.lo), int(sb.team.hi), endpoint=True))
        cash = round(float(gen.uniform(sb.cash_cents.lo, sb.cash_cents.hi)))
        segments_all = list(category.segment_keys)
        count = min(len(segments_all), 1 + int(gen.integers(0, 2)))
        picks = sorted(
            (int(i) for i in gen.choice(len(segments_all), size=count, replace=False)),
        )
        state, company, entry = found_company(
            state,
            name,
            personality,
            category,
            [segments_all[i] for i in picks],
            cash,
            ["builder", *key_people_split(team, _mix(category.key, balance))],
            [FOUNDER_LEVEL, *([TEAM_LEVEL] * team)],
            rng,
            balance,
            data,
        )
        product_id = state.company_products(company.id)[0].id
        entries.append(entry)
        state, move = _record(
            state, company, "founded", f"was founded in {category.label}", product_id
        )
        moves.append(move)
    return state, tuple(entries), tuple(moves)


def launch_ready(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, tuple[RivalMove, ...]]:
    """Phase 9: a startup launches its product as soon as it is allowed (11.2)."""
    from tst.sim.actions.products import launch_problems

    moves: list[RivalMove] = []
    for company in alive_startups(state):
        for product in state.company_products(company.id):
            if product.status != "in_development":
                continue
            if launch_problems(state, product, balance, data):
                continue
            state = with_product(state, replace(product, status="live", launched_turn=state.turn))
            category = data.category(product.category)
            state, move = _record(
                state, company, "launched", f"launched in {category.label}", product.id
            )
            moves.append(move)
    return state, tuple(moves)


def startup_funding(
    state: GameState,
    company: CompanyState,
    draw: float,
    months: float,
    monthly_cost: int,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, tuple[LedgerEntry, ...], RivalMove | None, bool]:
    """15.4: with cash for fewer than 6 months, a startup tries once a quarter to raise 18
    months of costs (chance 0.6 x climate). Returns (state, entries, move, failed): a failed
    attempt means it cuts costs instead."""
    sb = balance.rivals.startup
    quarter = 3  # tunable-exempt: "once a quarter"
    if months >= sb.low_cash_months:
        return state, (), None, False
    if company.last_raise_turn is not None and state.turn - company.last_raise_turn < quarter:
        return state, (), None, False
    company = replace(company, last_raise_turn=state.turn)
    state = with_company(state, company)
    if draw >= sb.raise_chance * climate(state, data):
        return state, (), None, True
    amount = round(sb.raise_months * monthly_cost)
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company.id,
        memo="Funding round",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=amount,
    )
    state, move = _record(state, company, "funded", f"raised ${amount // 100:,}")
    return state, (entry,), move, False


def record_failures(
    state: GameState, logs: tuple[LogItem, ...]
) -> tuple[GameState, tuple[RivalMove, ...]]:
    """Each rival_failed note in phase 7 becomes a market-news move."""
    moves: list[RivalMove] = []
    for item in logs:
        if item.template != "rival_failed":
            continue
        company = state.company(item.company_id or 0)
        state, move = _record(state, company, "failed", "ran out of money and closed")
        moves.append(move)
    return state, tuple(moves)


def _mix(category: str, balance: Balance) -> dict[str, float]:
    """The new company's function mix: its only product's category (15.1)."""
    mix = balance.rivals.function_mix.get(category)
    return dict(mix) if mix else {fn: 1 / len(FUNCTIONS) for fn in FUNCTIONS}


def found_company(
    state: GameState,
    name: str,
    personality: str,
    category: CategoryDef,
    segments: list[str],
    cash: int,
    functions: list[str],
    levels: list[str],
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    gen: np.random.Generator | None = None,
) -> tuple[GameState, CompanyState, LedgerEntry]:
    """A rival startup with one product in development, its people and its opening cash
    (15.4). People come from `gen`, else stream people_gen keyed (company_id, 1)."""
    company_id = max(c.id for c in state.companies) + 1
    product_id, ids = state.next_ids.take("product")
    state = replace(state, next_ids=ids)
    company = CompanyState(
        id=company_id,
        name=name,
        is_player=False,
        stage=STARTUP_STAGE,
        founded_turn=state.turn,
        root_product_id=product_id,
        personality=personality,
        is_startup=True,
    )
    state = with_company(state, company)
    state = with_product(
        state,
        Product(
            id=product_id,
            company_id=company_id,
            category=category.key,
            name=name,
            status="in_development",
            quality=balance.products.start_quality,
            feature_points=0.0,
            brand=0.0,
            marketing_budget_cents=0,
            created_turn=state.turn,
        ),
    )
    factor = balance.rivals.price_factor[personality]
    for segment in segments:
        market = category.market(segment)
        state = with_product_segment(
            state,
            ProductSegment(
                product_id=product_id,
                segment=market.segment,
                price_cents=max(1, round(market.reference_price_cents * factor)),
                added_turn=state.turn,
            ),
        )
    state = hire_key_people(
        state,
        company,
        functions,
        rng,
        balance,
        data,
        stream_part=TEAM_STREAM_PART,
        salary_mult=balance.rivals.startup.salary_mult,
        levels=levels,
        gen=gen,
    )
    entry = LedgerEntry.transfer(
        turn=state.turn,
        company_id=company_id,
        memo="Founders' and angels' money",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=cash,
    )
    return state, company, entry


def is_entrant(company: CompanyState, data: GameData) -> bool:
    """A scheduled entrant (18.7): a startup named in entrants.yaml."""
    return company.is_startup and any(e.name == company.name for e in data.entrants)


def found_entrants(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[RivalMove, ...]]:
    """Phase 9: each entrant founded in its real month, on every seed (18.7). Founding draws
    nothing; its people (all senior) come from stream `entrants`, key (entrant_index,)."""
    entries: list[LedgerEntry] = []
    moves: list[RivalMove] = []
    for index, entrant in enumerate(data.entrants):
        if ym_to_turn(entrant.year, entrant.month) != state.turn:
            continue
        if any(c.name == entrant.name for c in state.companies):
            continue
        category = data.category(entrant.category)
        team = entrant.staff - 1
        functions = ["builder", *key_people_split(team, _mix(category.key, balance))]
        segments = [s for s in category.segment_keys if s in entrant.segments]
        state, company, entry = found_company(
            state,
            entrant.name,
            entrant.personality,
            category,
            segments,
            entrant.cash_cents,
            functions,
            [ENTRANT_LEVEL] * entrant.staff,
            rng,
            balance,
            data,
            gen=rng.stream(state.turn, "entrants", index),
        )
        entries.append(entry)
        product_id = state.company_products(company.id)[0].id
        state, move = _record(
            state, company, "founded", f"was founded in {category.label}", product_id
        )
        moves.append(move)
    return state, tuple(entries), tuple(moves)
