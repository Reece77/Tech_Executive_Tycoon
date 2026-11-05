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

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import FUNCTIONS, Balance, CategoryDef, GameData
from tst.sim.finance.fundraising import climate
from tst.sim.geo import formulas as gf
from tst.sim.geo.cities import home_region
from tst.sim.geo.models import ProductRegion, RegionalSegment
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry
from tst.sim.log import LogItem
from tst.sim.mna.style import style  # M14 (28.5): a kept brand's directive
from tst.sim.products.models import Product, ProductSegment
from tst.sim.research.eras import annual_growth
from tst.sim.rivals.models import ENTRANT_KEY, STARTUP_KEY, RivalMove, stream_key
from tst.sim.rivals.setup import hire_key_people, key_people_split
from tst.sim.rng import RngFactory
from tst.sim.state import (
    CompanyState,
    GameState,
    with_company,
    with_product,
    with_product_region,
    with_product_segment,
    with_regional_segment,
    with_rival_move,
)

STARTUP_STAGE = 1  # tunable-exempt: a founded startup is a garage startup (spec section 3)
TEAM_STREAM_PART = 1  # tunable-exempt: second key part of a startup team's people_gen stream
FOUNDER_LEVEL = "exec"  # tunable-exempt: the startup's founder is its top person
TEAM_LEVEL = "mid"  # tunable-exempt: a startup's first employees (15.4 does not say)
ENTRANT_LEVEL = "senior"  # tunable-exempt: every entrant's people (18.7)
ENTRANT_REGION = "north_america"  # tunable-exempt: entrants start in North America (19.6)


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
        if category.capacity_market:  # M12a (22.3): selling capacity needs data centres
            continue
        if category.sells_units or category.assembly_market:  # M12b (26): scheduled only
            continue
        gen = rng.stream(state.turn, "rival_spawn", index)
        growth = annual_growth(state, data, category.key)  # with era boosts (M11, 21.4)
        chance = sb.found_rate * mood * (1 + growth)
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
            rival_key=startup_key(state, index),
        )
        product_id = state.company_products(company.id)[0].id
        entries.append(entry)
        region = founding_region(state, rng, company, category, balance, data)
        state = sell_first_in(state, company, product_id, region, balance, data)
        where = f" in {data.region(region).label}" if region != _home(state, balance, data) else ""
        state, move = _record(
            state, company, "founded", f"was founded in {category.label}{where}", product_id
        )
        moves.append(move)
    return state, tuple(entries), tuple(moves)


def startup_key(state: GameState, category_index: int) -> tuple[int, ...]:
    """(STARTUP_KEY, category index, n): the nth startup founded in the category, counting
    every one ever founded (failed ones stay in the state) (ADR-0013 amendment, M12a)."""
    n = sum(1 for c in state.companies if c.rival_key[:2] == (STARTUP_KEY, category_index))
    return (STARTUP_KEY, category_index, n)


def _home(state: GameState, balance: Balance, data: GameData) -> str | None:
    return home_region(state, balance, data) if data.cities and data.region_markets else None


def founding_region(
    state: GameState,
    rng: RngFactory,
    company: CompanyState,
    category: CategoryDef,
    balance: Balance,
    data: GameData,
) -> str:
    """A startup's region, drawn by its category's addressable demand in each region (19.6):
    one uniform from stream `rival_region`, key the startup's rival key (ADR-0013 amendment,
    M12a; its company id before), in regions.yaml order."""
    home = _home(state, balance, data)
    if home is None:
        return ""
    weights: list[float] = []
    for region in data.region_keys:
        total = 0.0
        for seg in category.segment_keys:
            if region == home:
                market = state.market(category.key, seg)
                total += market.addressable if market is not None else 0.0
            else:
                rmarket = state.regional_market(category.key, seg, region)
                total += rmarket.addressable if rmarket is not None else 0.0
        weights.append(total)
    key = stream_key(company.id, company.rival_key)
    u = float(rng.stream(state.turn, "rival_region", *key).random()) * sum(weights)
    acc = 0.0
    for region, w in zip(data.region_keys, weights, strict=True):
        acc += w
        if u < acc:
            return region
    return data.region_keys[-1]


def sell_first_in(
    state: GameState,
    company: CompanyState,
    product_id: int,
    region: str,
    balance: Balance,
    data: GameData,
) -> GameState:
    """A new rival's product sells first in `region` (19.6): its home segments move there,
    at that region's prices."""
    home = _home(state, balance, data)
    if home is None or region in ("", home):
        return state
    product = state.product(product_id)
    assert product is not None
    factor = balance.rivals.price_factor[style(state, company)]
    category = data.category(product.category)
    for seg in state.segments_of(product_id):
        reference = category.market(seg.segment).reference_price_cents
        price = gf.regional_price_cents(reference, region, home, data, factor)  # M10r
        state = with_regional_segment(
            state, RegionalSegment(product_id, region, seg.segment, price, added_turn=state.turn)
        )
    state = replace(
        state,
        product_segments=tuple(s for s in state.product_segments if s.product_id != product_id),
    )
    return with_product_region(state, ProductRegion(product_id, region, state.turn, state.turn))


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
    rival_key: tuple[int, ...] = (),
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
        rival_key=rival_key,
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
            rival_key=(ENTRANT_KEY, index),  # ADR-0013 amendment (M12a)
        )
        entries.append(entry)
        product_id = state.company_products(company.id)[0].id
        state = sell_first_in(state, company, product_id, ENTRANT_REGION, balance, data)  # 19.6
        state, move = _record(
            state, company, "founded", f"was founded in {category.label}", product_id
        )
        moves.append(move)
    return state, tuple(entries), tuple(moves)
