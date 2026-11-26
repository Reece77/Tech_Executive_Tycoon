"""Custom scenarios (M52, ADR-0026, docs/formulas.md 66.1-66.2): checking a spec against the
editor's ranges and the loaded data, and applying it at the start.

A custom game is a scenario game (`GameMode.kind` "scenario") whose `scenario` is the key
"custom/<slug>" and whose `scenario_sha256` is the file's hash. Its entry is put into the game
data beside scenarios.yaml's (`with_custom`), so §63's start code builds the company exactly as
it builds a historical scenario's (`apply_start`); then `apply_overrides` applies the overrides
block in the start month, before the rivals' balances are brought forward:

- **rivals** (incumbents.yaml, by name): removed as a failed rival closes (15.1), as Sandbox's
  rivals option removes them; cash x `cash_mult` (against common equity); every product's
  quality + `quality_delta`, clamped to 0-100; added generic rivals by category, each a 52.3
  entrant on stream `scenario`, key (ADDED + category index x ADDED_SPAN + k,), rival key
  (CUSTOM_KEY, category index, k);
- **markets**: every segment's addressable customers (national and regional) x `market_mult`
  this month; `growth_delta` joins the mode record and adds to the category's annual growth in
  every month from the start (`research.eras.annual_growth`, never below 0);
- **world**: from `editor.macro_from_year` (history before it is the same on every seed), the
  macro month the start reads (confidence, the base rate) and each commodity's price level
  (its trend and index x the multiplier), from which 20.1's and 33.1's AR(1) steps go on.

No new stream (ADR-0026): staff are M15b's draws, added rivals use `scenario` keys past them.
Hidden values are never set: new people draw theirs from the usual streams (point 3).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import TYPE_CHECKING, Final

from tst.sim.calendar import ym_to_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.errors import InvalidModeError
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerBalances, LedgerEntry
from tst.sim.modes.config import GoalSpec, HistoricalScenario
from tst.sim.modes.custom_config import (
    CUSTOM_PREFIX,
    CustomScenario,
    EditorBalance,
    Range,
)
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

if TYPE_CHECKING:
    from tst.sim.modes.world import ModeSpec

CENTS_A_DOLLAR: Final = 100  # tunable-exempt: cents in a dollar
MAX_QUALITY: Final = 100.0  # tunable-exempt: the quality scale's top
INCUMBENT_KEY: Final = 0  # tunable-exempt: rivals.models' incumbent rival_key tag
CUSTOM_KEY: Final = 20  # tunable-exempt: rival_key tag of a custom start's added rival
ADDED: Final = 1_000_000  # tunable-exempt: `scenario` keys past every staff draw's (index,)
ADDED_SPAN: Final = 100  # tunable-exempt: keys a category's added rivals may use
BLANK_BACKGROUND: Final = "ex_big_tech_founders"  # scenarios.yaml start a blank game uses
BLANK_LABEL: Final = "A blank start"
DIFFICULTY: Final = "standard"  # a blank start's cash is the background's standard cash

# The goal kinds' required fields (63.1's notes; 30.3)
GOAL_FIELDS: Final[Mapping[str, tuple[str, ...]]] = {
    "arr": ("arr_dollars",),
    "customers": ("category", "customers"),
    "solvent_margin": (),
    "unit_share": ("category", "share"),
    "profit_no_down_round": (),
    "solvent_series": ("series",),
    "platform_share": ("share",),
    "vehicles_year": ("units",),
    "fab_catch_up": ("node_gap",),
    "node_volume": ("node",),
    "family_succession": (),
}


def custom_key(slug: str) -> str:
    return CUSTOM_PREFIX + slug


def is_custom_key(key: str | None) -> bool:
    return key is not None and key.startswith(CUSTOM_PREFIX)


def with_custom(data: GameData, spec: CustomScenario) -> GameData:
    """The game data with the custom entry beside scenarios.yaml's, under "custom/<slug>"
    (never a scenarios.yaml key): what §63's start code and the monthly judge read."""
    key = custom_key(spec.key)
    entry = spec.model_copy(update={"key": key})
    kept = tuple(h for h in data.historical if h.key != key)
    return data.model_copy(update={"historical": (*kept, entry)})


def from_historical(h: HistoricalScenario) -> CustomScenario:
    """A scenarios.yaml entry opened in the editor: the same fields and no overrides (66.4
    target 2). Its difficulty record (`sensible_wins`) is the historical entry's, not kept."""
    fields = h.model_dump(exclude={"key", "sensible_wins"})
    return CustomScenario.model_validate(
        {**fields, "key": h.key.replace("_", "-"), "opened_from": h.key}
    )


def blank(year: int, balance: Balance, data: GameData) -> CustomScenario:
    """A blank start in `year` (66.1): the background's standard cash, no staff or products,
    no goal."""
    from tst.sim.setup import starting_cash_cents

    cash = starting_cash_cents(balance, BLANK_BACKGROUND, DIFFICULTY) // CENTS_A_DOLLAR
    return CustomScenario(
        key=f"blank-{year}",
        label=f"{BLANK_LABEL} in {year}",
        description=f"January {year}. A new company and the world as it stood.",
        year=year,
        background=BLANK_BACKGROUND,
        cash_dollars=int(cash),
        stage=0,
        opened_from=f"blank_{year}",
    )


# --- Checking (66.1: "validation is the loader's, plus the editor's ranges") ----------------


def _range(out: list[str], label: str, value: float, r: Range) -> None:
    if not r.holds(value):
        out.append(f"{label} is {value:g}: the editor allows {r.text()}")


def computed_markets(balance: Balance) -> frozenset[str]:
    """Categories whose addressable market follows its own data every month (cars, robots,
    telecom services): their market and growth are not editable."""
    from tst.sim.telecom.data import demand_categories

    return frozenset(
        (
            balance.vehicles.category,
            balance.robotics.industrial,
            balance.robotics.humanoid,
            *demand_categories(balance),
        )
    )


def editable_categories(balance: Balance, data: GameData) -> tuple[str, ...]:
    """Every category with a market, from the loaded data (M54's and M55's included)."""
    return tuple(c.key for c in data.categories if c.markets and not c.pseudo)


def _node_ready(node: str, turn: int, data: GameData) -> bool | None:
    """True when `node` is in volume by `turn`; False if not yet; None if no such node."""
    from tst.sim.facilities.config import month_to_turn

    if data.nodes is None:
        return None
    for n in data.nodes.nodes:
        if n.key == node:
            return min(month_to_turn(m) for m in n.first.values()) <= turn
    if any(n.key == node for n in (*data.nodes.future, *data.nodes.dynasty_future)):
        return False
    return None


def _check_goal(out: list[str], spec: CustomScenario, ed: EditorBalance, data: GameData) -> None:
    goal: GoalSpec | None = spec.goal
    if goal is None or spec.deadline is None:
        return
    missing = [f for f in GOAL_FIELDS[goal.kind] if getattr(goal, f) is None]
    if missing:
        out.append(f"the goal {goal.kind!r} needs {', '.join(missing)}")
    if goal.category is not None and goal.category not in {c.key for c in data.categories}:
        out.append(f"the goal's category {goal.category!r} is not a category")
    if goal.region is not None and goal.region not in data.region_keys:
        out.append(f"the goal's region {goal.region!r} is not a region")
    if goal.node is not None and _node_ready(goal.node, 10**6, data) is None:
        out.append(f"the goal's node {goal.node!r} is not a process node")
    for name in ("share",):
        v = getattr(goal, name)
        if v is not None and not 0 < v <= 1:
            out.append(f"the goal's share is {v:g}: it must be above 0 and at most 1")
    for name in ("arr_dollars", "customers", "units"):
        v = getattr(goal, name)
        if v is not None and v <= 0:
            out.append(f"the goal's {name} must be above 0")
    year, month = spec.deadline
    if not 1 <= month <= 12:  # tunable-exempt: calendar months
        out.append(f"the deadline's month is {month}: 1 to 12")
        return
    years = (ym_to_turn(year, month) - ym_to_turn(spec.year, 1) + 1) / 12  # tunable-exempt
    if years <= 0:
        out.append("the deadline is before the start")
    else:
        _range(out, "the deadline's years from the start", round(years, 2), ed.deadline_years)


def refusals(spec: CustomScenario, balance: Balance, data: GameData) -> list[str]:
    """Every reason the editor refuses `spec` (empty: valid). Ranges are `editor.*`'s."""
    ed = balance.editor
    out: list[str] = []
    _range(out, "the start year", spec.year, ed.start_years)
    start = ym_to_turn(spec.year, 1)
    background = data.scenario(spec.background)
    if background is None or not background.selectable:
        out.append(f"the background {spec.background!r} is not a start the game offers")
    _range(out, "starting cash ($)", spec.cash_dollars, ed.cash_dollars)
    if spec.sensible_wins is not None:
        out.append("a custom scenario has no recorded difficulty (sensible_wins)")
    # the company
    roles = {r.key: r for r in data.roles}
    units = {s.unit for s in spec.staff if s.unit is not None}
    for s in spec.staff:
        role = roles.get(s.role)
        if role is None:
            out.append(f"staff: {s.role!r} is not a role")
        elif s.level not in role.salary_band_mid_cents:
            out.append(f"staff: {s.role} has no level {s.level!r}")
        _range(out, f"staff ({s.role}, {s.level})", s.count, ed.staff_count)
    _range(out, "staff in all", sum(s.count for s in spec.staff), ed.staff_total)
    _range(out, "products", len(spec.products), ed.products)
    categories = {c.key: c for c in data.categories}
    for p in spec.products:
        cat = categories.get(p.category)
        if cat is None or not cat.markets or cat.pseudo:
            out.append(f"product {p.name!r}: {p.category!r} is not a category it can sell in")
            continue
        _range(out, f"{p.name}: quality", p.quality, ed.quality)
        _range(out, f"{p.name}: features", p.features, ed.features)
        _range(out, f"{p.name}: brand", p.brand, ed.brand)
        segments = set(cat.segment_keys)
        for seg, value in sorted(p.segments.items()):
            if seg not in segments:
                out.append(f"{p.name}: {cat.label} has no segment {seg!r}")
            _range(out, f"{p.name} ({seg}): customers", value.customers, ed.customers)
            _range(out, f"{p.name} ({seg}): price ($)", value.price_dollars, ed.price_dollars)
        if p.status == "in_development" and any(v.customers for v in p.segments.values()):
            out.append(f"{p.name}: a product in development has no customers")
        if p.contract is not None:
            makers = balance.hardware.contract.manufacturers
            if p.contract.manufacturer not in makers:
                out.append(f"{p.name}: {p.contract.manufacturer!r} is not a contract maker")
            if not data.has_city(p.contract.city):
                out.append(f"{p.name}: {p.contract.city!r} is not a city")
    domains = {d.key for d in data.tech.domains} if data.tech is not None else set()
    for lead in spec.research:
        if lead.domain not in domains:
            out.append(f"research: {lead.domain!r} is not a research domain")
        _range(out, f"research lead ({lead.domain})", lead.lead, ed.research_lead)
    lenders = {x.key for x in data.lenders}
    for loan in spec.loans:
        if loan.lender not in lenders:
            out.append(f"debt: {loan.lender!r} is not a lender")
        if loan.interest_only_months >= loan.term_months:
            out.append("debt: the interest-only months must be fewer than the term")
    _range(out, "debt ($)", sum(x.principal_dollars for x in spec.loans), ed.debt_dollars)
    _range(out, "fabs", len(spec.fabs), ed.fabs)
    for fab in spec.fabs:
        ready = _node_ready(fab.node, start, data)
        if ready is None:
            out.append(f"fab: {fab.node!r} is not a process node")
        elif not ready:
            out.append(f"fab: {fab.node} is not yet in volume in January {spec.year}")
        if fab.region not in data.region_keys:
            out.append(f"fab: {fab.region!r} is not a region")
        if fab.unit not in units:
            out.append(f"fab: its team {fab.unit!r} is not a staff line's team")
        fab_sizes = balance.facility.kinds["fab"].sizes or ()
        if fab.capacity not in fab_sizes:
            sizes = ", ".join(str(s) for s in fab_sizes)
            out.append(f"fab: {fab.capacity} wafer starts is not a fab size ({sizes})")
        if fab.age_months > (spec.year - 2000) * 12:  # tunable-exempt: no fab before 2000
            out.append("fab: built before 2000")
    if spec.founder_age is not None:
        _range(out, "the founder's age", spec.founder_age, ed.founder_age)
    if spec.founder_region is not None and spec.founder_region not in data.region_keys:
        out.append(f"the founder's region {spec.founder_region!r} is not a region")
    if spec.hq_city is not None and not data.has_city(spec.hq_city):
        out.append(f"the home city {spec.hq_city!r} is not a city")
    if spec.family is not None:
        _range(out, "children", len(spec.family.child_ages), ed.children)
        for age in spec.family.child_ages:
            _range(out, "a child's age", age, ed.child_age)
        if spec.founder_age is not None and max(spec.family.child_ages) > spec.founder_age - 18:
            out.append("a child is older than the founder's age less 18")  # tunable-exempt
    _check_goal(out, spec, ed, data)
    # the overrides
    o = spec.overrides
    incumbents = {c.name for c in data.incumbents}
    for name, r in sorted(o.rivals.items()):
        if name not in incumbents:
            out.append(f"rivals: {name!r} is not an incumbent")
        _range(out, f"{name}: cash x", r.cash_mult, ed.rival_cash_mult_range)
        _range(out, f"{name}: quality +", r.quality_delta, ed.rival_quality_range)
    editable = set(editable_categories(balance, data))
    computed = computed_markets(balance)
    for added in o.added_rivals:
        if added.category not in editable:
            out.append(f"added rivals: {added.category!r} is not a category with a market")
        _range(out, f"added rivals ({added.category})", added.count, ed.added_rivals)
    if len({a.category for a in o.added_rivals}) != len(o.added_rivals):
        out.append("added rivals: one line a category")
    for key, m in sorted(o.markets.items()):
        if key not in editable:
            out.append(f"markets: {key!r} is not a category with a market")
        elif key in computed and (m.market_mult != 1 or m.growth_delta != 0):
            out.append(f"markets: {key}'s market follows its own data and cannot be edited")
        _range(out, f"{key}: market x", m.market_mult, ed.market_mult_range)
        _range(out, f"{key}: growth +", m.growth_delta, ed.growth_delta_range)
    w = o.world
    macro = w.confidence is not None or w.policy_rate_pct is not None or bool(w.commodities)
    if macro and spec.year < ed.macro_from_year:
        out.append(
            f"world: the macro and commodity prices are history before {ed.macro_from_year}"
            f" (the start is {spec.year})"
        )
    if w.confidence is not None:
        _range(out, "consumer confidence", w.confidence, ed.confidence)
    if w.policy_rate_pct is not None:
        _range(out, "the base rate (%)", w.policy_rate_pct, ed.policy_rate_pct)
    goods = {g.key for g in data.commodities.goods} if data.commodities is not None else set()
    for key, mult in sorted(w.commodities.items()):
        if key not in goods:
            out.append(f"world: {key!r} is not a commodity")
        _range(out, f"{key}: price x", mult, ed.commodity_mult_range)
    from tst.sim.modes.challenges import RULES

    for rule in o.rules.challenges:
        if rule not in RULES:
            out.append(f"rules: {rule!r} is not a challenge rule")
    if len(set(o.rules.challenges)) != len(o.rules.challenges):
        out.append("rules: each challenge once")
    return out


def check(spec: CustomScenario, balance: Balance, data: GameData) -> CustomScenario:
    """`spec`, or InvalidModeError naming every reason it is refused."""
    reasons = refusals(spec, balance, data)
    if reasons:
        raise InvalidModeError("; ".join(reasons))
    return spec


# --- Applying the overrides at the start (66.1) ----------------------------------------------


def _incumbent_ids(state: GameState, data: GameData) -> dict[str, int]:
    """Incumbent name -> its company id, for those still in business and independent."""
    names = {i: c.name for i, c in enumerate(data.incumbents)}
    out: dict[str, int] = {}
    for c in state.companies:
        key = c.rival_key
        incumbent = len(key) == 2 and key[0] == INCUMBENT_KEY and key[1] in names  # tunable-exempt
        if incumbent and c.alive and c.parent_id is None and not c.is_player:
            out[names[key[1]]] = c.id
    return out


def apply_overrides(
    state: GameState,
    balances: LedgerBalances,
    spec: CustomScenario,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, dict[tuple[int, str], int], tuple[LedgerEntry, ...]]:
    """The overrides block in the start month: rivals, markets and world (module docstring).
    Returns the state, the balances to bring forward and the added rivals' founding entries."""
    from tst.sim.finance.insolvency import fail_rival
    from tst.sim.state import with_product

    o = spec.overrides
    out = dict(balances)
    ids = _incumbent_ids(state, data)
    for name, r in sorted(o.rivals.items()):
        cid = ids.get(name)
        if cid is None:  # gone by the start year (failed or bought): nothing to change
            continue
        if not r.present:
            state, _ = fail_rival(
                state,
                state.company(cid),
                balance.hiring.candidate_shelf_turns,
                balance.rivals.free_agent_months,
            )
            continue
        if r.cash_mult != 1:
            cash = out.get((cid, CASH), 0)
            delta = round(cash * r.cash_mult) - cash
            out[(cid, CASH)] = cash + delta
            out[(cid, COMMON_EQUITY)] = out.get((cid, COMMON_EQUITY), 0) - delta
        if r.quality_delta:
            for p in state.company_products(cid):
                q = min(MAX_QUALITY, max(0.0, p.quality + r.quality_delta))
                state = with_product(state, replace(p, quality=q))
    state = _markets(state, spec)
    state = _world(state, spec, balance, data)
    entries: list[LedgerEntry] = []
    index = {c.key: i for i, c in enumerate(data.categories)}
    from tst.sim.dynasty.rivals import enter
    from tst.sim.modes.scenarios import scenario_draw

    for added in sorted(o.added_rivals, key=lambda a: index[a.category]):
        i = index[added.category]
        for k in range(added.count):
            g = scenario_draw(rng, state.turn, ADDED + i * ADDED_SPAN + k)
            made = enter(state, data.categories[i], g, (CUSTOM_KEY, i, k), rng, balance, data)
            if made is None:
                break
            state, entry, _ = made
            entries.append(entry)
    return state, out, tuple(entries)


def _markets(state: GameState, spec: CustomScenario) -> GameState:
    mult = {k: m.market_mult for k, m in spec.overrides.markets.items() if m.market_mult != 1}
    if not mult:
        return state
    return replace(
        state,
        markets=tuple(
            replace(m, addressable=m.addressable * mult[m.category]) if m.category in mult else m
            for m in state.markets
        ),
        regional_markets=tuple(
            replace(m, addressable=m.addressable * mult[m.category]) if m.category in mult else m
            for m in state.regional_markets
        ),
    )


def _world(state: GameState, spec: CustomScenario, balance: Balance, data: GameData) -> GameState:
    w = spec.overrides.world
    if w.confidence is not None or w.policy_rate_pct is not None:
        from tst.sim.finance.macro import current

        macro = current(state.macro, state.turn - 1, data)
        if w.confidence is not None:
            macro = replace(macro, confidence=w.confidence)
        if w.policy_rate_pct is not None:
            macro = replace(macro, base_rate=w.policy_rate_pct)
        state = replace(state, macro=macro)
    if w.commodities:
        mult = w.commodities
        state = replace(
            state,
            supply=tuple(
                replace(g, base=g.base * mult[g.good], index=g.index * mult[g.good])
                if g.good in mult
                else g
                for g in state.supply
            ),
        )
    return state


def mode_spec(spec: CustomScenario, sha256: str) -> ModeSpec:
    """The ModeSpec a custom scenario's game starts from: a scenario start under its custom
    key, its cash, eras and challenge rules, and the file's hash (ADR-0026 point 4)."""
    from tst.sim.modes.world import ModeSpec

    return ModeSpec(
        kind="scenario",
        start_year=spec.year,
        cash_cents=spec.cash_dollars * CENTS_A_DOLLAR,
        eras=spec.overrides.world.eras,
        scenario=custom_key(spec.key),
        challenges=spec.overrides.rules.challenges,
        scenario_sha256=sha256,
    )
