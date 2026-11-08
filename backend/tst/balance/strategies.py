"""The v1 scripted strategies (docs/balance-targets.md, Reece's D3a): do-nothing,
bootstrap-frugal, steady and blitzscale. Each is a function called once a month before the
turn is played; it acts only through `Game.act`, so every rule (energy, cash, gates) applies.

The numbers here describe the scripts, not the game, so they live in code (like the M3a
earn-and-burn script) rather than in balance.yaml.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

from tst.balance.game import PLAYER, Game
from tst.sim.actions import (
    AcceptBridge,
    AcceptTermSheet,
    AppointExecutive,
    AssignUnit,
    CloseSearch,
    CreateProduct,
    CreateUnit,
    HireBanks,
    Interview,
    LaunchProduct,
    MakeOffer,
    MovePerson,
    OpenSearch,
    SetMarketing,
    SetPrice,
    StartRound,
)
from tst.sim.actions.products import launch_problems
from tst.sim.actions.scaleup import appoint_problem
from tst.sim.finance.captable import open_round
from tst.sim.finance.fundraising import arr_cents, next_series, series_problem
from tst.sim.finance.statements import projected_runway
from tst.sim.hiring.phases import monthly_costs
from tst.sim.markets_public.ipo import eligibility_problem
from tst.sim.org.executives import displayed_score, seats_in_play
from tst.sim.org.models import SEATS
from tst.sim.products.models import Product

type Strategy = Callable[[Game], None]

FIRST_PRODUCT: Final = ("Pipeline", "b2b_saas", ("smb", "mid_market"))
SECOND_PRODUCT: Final = ("Forge", "dev_tools", ("smb", "mid_market"))
SECOND_TEAM: Final = "Forge team"
# Who gets hired, in order (cycled after the list): builders first, then go-to-market.
HIRE_ORDER: Final = (
    "software_engineer",
    "software_engineer",
    "software_engineer",
    "account_executive",
    "marketer",
    "software_engineer",
    "product_manager",
    "sales_representative",
    "designer",
    "software_engineer",
    "account_executive",
    "devops_engineer",
)
OFFER_RATIO: Final = 1.05  # offers at 1.05x the candidate's ask, no equity
INTERVIEW_ENERGY_RESERVE: Final = 0  # energy kept back after interviews


# --- Shared steps ----------------------------------------------------------------------------

# M8 (Reece, 2026-10-31): at stage 3 the scripts fill executive seats. Each vacant seat takes
# the best senior-or-above employee by displayed fit; if nobody fits (a "weak fit" or no
# one eligible), an exec-level network search for the seat's role, hired at 1.05x the ask.
SEAT_ROLES: Final = {
    "coo": "operations_manager",
    "cfo": "finance_manager",
    "cto": "software_engineer",
    "cpo": "product_manager",
    "cmo": "marketer",
    "cro": "account_executive",
}


def appoint_executives(game: Game, seats: tuple[str, ...] = SEATS) -> None:
    """Fill vacant seats from stage 3 (see SEAT_ROLES)."""
    state = game.state
    b = game.loaded.balance
    if not seats_in_play(state, PLAYER, b):
        return
    for seat in seats:
        state = game.state
        if state.seat_holder(PLAYER, seat) is not None:
            continue
        options = [
            (displayed_score(state, PLAYER, e.person_id, seat, b), e.person_id)
            for e in state.staff(PLAYER)
            if appoint_problem(state, PLAYER, seat, e.person_id, b) is None
        ]
        fitting = [o for o in options if o[0] >= b.exec_seats.fit_bands.lo]
        if fitting:
            game.act(AppointExecutive(game.founder_id, seat, max(fitting)[1]))
            continue
        _exec_search(game, SEAT_ROLES[seat])


def _exec_search(game: Game, role: str) -> None:
    """Hire an exec for `role`: offer to an open exec candidate, else open the search."""
    state = game.state
    for candidate in state.open_candidates(PLAYER):
        person = state.person(candidate.person_id)
        if person.role != role or person.level != "exec":
            continue
        if state.pending_offer_for(person.id) is not None:
            return
        if candidate.interviewed_turn is None and not game.act(
            Interview(game.founder_id, person.id)
        ):
            return
        ask = person.salary_expectation_cents or 0
        game.act(MakeOffer(game.founder_id, person.id, round(ask * OFFER_RATIO), 0))
        return
    if not any(s.role == role and s.level == "exec" for s in state.open_searches(PLAYER)):
        game.act(OpenSearch(game.founder_id, role, "network", level="exec"))


def _products(game: Game) -> list[Product]:
    return [p for p in game.state.company_products(PLAYER) if p.status != "retired"]


def ensure_product(
    game: Game, index: int, second: tuple[str, str, tuple[str, ...]] = SECOND_PRODUCT
) -> Product | None:
    """Create product `index` (0 or 1) if missing: reference prices; the root builds the
    first, a new team the second (`second`: M8 runs it in Fintech, 18.9 target 5)."""
    products = _products(game)
    if len(products) > index:
        return products[index]
    name, category, segments = (FIRST_PRODUCT, second)[index]
    product_id = game.state.next_ids.product
    if not game.act(CreateProduct(game.founder_id, name, category, segments)):
        return None
    cat = game.loaded.game_data.category(category)
    for market in cat.markets:
        if market.segment in segments:
            game.act(
                SetPrice(game.founder_id, product_id, market.segment, market.reference_price_cents)
            )
    unit_id = None
    if index == 1:
        unit_id = game.state.next_ids.unit
        game.act(CreateUnit(game.founder_id, "team", SECOND_TEAM))
    game.act(AssignUnit(game.founder_id, product_id, unit_id))
    return game.state.product(product_id)


def launch_ready(game: Game) -> None:
    for product in _products(game):
        if product.status == "in_development" and not launch_problems(
            game.state, product, game.loaded.balance, game.loaded.game_data
        ):
            game.act(LaunchProduct(game.founder_id, product.id))


def set_marketing(game: Game, cents: int) -> None:
    """The same monthly budget on every live or developing product."""
    for product in _products(game):
        if product.marketing_budget_cents != cents:
            game.act(SetMarketing(game.founder_id, product.id, cents))


def last_revenue(game: Game) -> int:
    return game.snapshots[-1].mrr_cents if game.snapshots else 0


def monthly_cost(game: Game) -> int:
    return sum(
        amount
        for _, _, amount in monthly_costs(
            game.state, PLAYER, game.loaded.balance, game.loaded.game_data
        )
    )


def runway(game: Game) -> int | None:
    """Months of cash at this month's projected net burn; None when profitable."""
    return projected_runway(
        game.state, PLAYER, game.cash, game.loaded.balance, game.loaded.game_data
    )


def headcount(game: Game) -> int:
    """Staff other than the founder, plus offers still waiting for an answer."""
    pending = sum(1 for o in game.state.offers if o.company_id == PLAYER and o.status == "pending")
    return len(game.state.staff(PLAYER)) - 1 + pending


def hire(
    game: Game,
    wanted: int,
    per_month: int,
    order: tuple[str, ...] = HIRE_ORDER,
    keep: frozenset[int] = frozenset(),
) -> None:
    """Work toward `wanted` employees (offers out count) in `order` (cycled): the next
    `per_month` slots' roles each get a job post (others close), their candidates are
    interviewed while energy lasts and offered 1.05x the ask. Job posts close once the target
    is reached. Searches in `keep` (M15a: a v2 script's own searches) are left open."""
    state = game.state
    searches = [
        s
        for s in state.searches
        if s.company_id == PLAYER and s.status == "open" and s.id not in keep
    ]
    count = headcount(game)
    slots = [order[(count + i) % len(order)] for i in range(min(per_month, wanted - count))]
    for search in searches:
        if search.role not in slots:
            game.act(CloseSearch(game.founder_id, search.id))
    if not slots:
        return
    for role in dict.fromkeys(slots):
        if not any(s.role == role for s in searches):
            game.act(OpenSearch(game.founder_id, role, "job_post"))
    for candidate in list(game.state.candidates):
        if not slots:
            break
        person = game.state.person(candidate.person_id)
        if (
            candidate.company_id != PLAYER
            or candidate.status != "open"
            or person.role not in slots
            or game.state.pending_offer_for(person.id) is not None
            or person.salary_expectation_cents is None
        ):
            continue
        if candidate.interviewed_turn is None:
            cost = game.loaded.balance.founder.energy_cost["interview"]
            if game.energy() < cost + INTERVIEW_ENERGY_RESERVE:
                break
            if not game.act(Interview(game.founder_id, person.id)):
                continue
        salary = round(person.salary_expectation_cents * OFFER_RATIO)
        if game.act(MakeOffer(game.founder_id, person.id, salary, 0)):
            slots.remove(person.role)
    team = next((u for u in game.state.units if u.name == SECOND_TEAM), None)
    if team is not None:  # alternate new hires between the root and the second team
        for i, employment in enumerate(game.state.staff(PLAYER)):
            # M8 fix: offers made last month resolve at the start of this one, so a new hire
            # joined last turn (the old check, start_turn == state.turn, never matched).
            joined = employment.start_turn == state.turn - 1
            if employment.unit_id is None and i % 2 and joined:
                game.act(MovePerson(game.founder_id, employment.person_id, team.id))


def accept_bridges(game: Game) -> None:
    for safe in game.state.company_safes(PLAYER):
        if safe.kind == "bridge" and safe.status == "offered":
            game.act(AcceptBridge(game.founder_id, safe.id))


def fundraise(game: Game, targets: dict[str, int], pick: str, seed_ok: bool = True) -> None:
    """Start the next round as soon as its gate allows (the seed only when `seed_ok`) and
    accept the best term sheet: the highest pre-money (`pick="pre"`) or the largest amount
    (`pick="amount"`)."""
    state = game.state
    current = open_round(state, PLAYER)
    if current is not None:
        sheets = [t for t in state.sheets_of(current.id) if t.status == "offered"]
        if current.status == "open" and sheets:
            if pick == "amount":
                best = max(sheets, key=lambda t: (t.amount_cents, t.pre_money_cents, -t.id))
            else:
                best = max(sheets, key=lambda t: (t.pre_money_cents, -t.id))
            game.act(AcceptTermSheet(game.founder_id, best.id))
        return
    series = next_series(state, PLAYER)
    if series not in targets or (series == "seed" and not seed_ok):
        return
    if series_problem(state, PLAYER, series, game.loaded.balance) is None:
        game.act(StartRound(game.founder_id, series, targets[series]))


IPO_BANK = "morgan_stanley"  # M13 (25.9): the scripts' lead underwriter


def go_public(game: Game) -> None:
    """M13 (25.9): hire the banks as soon as the company is eligible (25.1); the chain's
    events take their first choice (Continue and the critical answer in Game.turn)."""
    if eligibility_problem(game.state, PLAYER, game.loaded.balance) is None:
        game.act(HireBanks(game.founder_id, IPO_BANK))


def closed_series(game: Game) -> set[str]:
    return {r.series for r in game.state.company_rounds(PLAYER) if r.status == "closed"}


# --- The strategies --------------------------------------------------------------------------


def do_nothing(game: Game) -> None:
    """The founder alone: no product, no hires, no money raised."""


BOOTSTRAP_ORDER = (  # Reece, M7a B1: an engineer to build, an account executive at launch
    "software_engineer",
    "account_executive",
    "software_engineer",
    "marketer",
    "software_engineer",
    "account_executive",
    "product_manager",
    "software_engineer",
    "sales_representative",
    "designer",
)
BOOTSTRAP_BUILDERS = 1  # employees before launch
BOOTSTRAP_AT_LAUNCH = 2  # employees once live (the account executive)
BOOTSTRAP_MAX = 15  # employees at most
BOOTSTRAP_CASH_MONTHS = 12  # then one more hire when cash covers this many months of costs
BOOTSTRAP_MARKETING = 0.10  # share of last month's revenue spent on marketing


def bootstrap_frugal(game: Game) -> None:
    """One B2B SaaS product built by the founder and 1 engineer, launched when allowed; an
    account executive at launch; then one hire each time cash covers 12 months of costs, to
    15; never raises; marketing 10% of last month's revenue (Reece, M7a B1)."""
    ensure_product(game, 0)
    launch_ready(game)
    wanted = BOOTSTRAP_BUILDERS
    if any(p.status == "live" for p in _products(game)):
        wanted = max(headcount(game), BOOTSTRAP_AT_LAUNCH)
        covered = game.cash >= BOOTSTRAP_CASH_MONTHS * monthly_cost(game)
        if headcount(game) >= BOOTSTRAP_AT_LAUNCH and covered:
            wanted = min(headcount(game) + 1, BOOTSTRAP_MAX)
    hire(game, wanted, per_month=1, order=BOOTSTRAP_ORDER)
    set_marketing(game, round(BOOTSTRAP_MARKETING * last_revenue(game)))
    appoint_executives(game)  # M8: from stage 3


STEADY_START = 5  # the M3a earn-and-burn team
STEADY_RUNWAY = 24  # hire one more while projected runway is above this (keeps it above 18)
STEADY_ROUNDS = {"seed": 150_000_000, "a": 600_000_000}  # $1.5M seed, $6M Series A
STEADY_SEED_RUNWAY = 12  # start the seed when runway falls below this or at launch (M7a B3)
STEADY_SECOND_ARR = 500_000_000  # second product at $5M ARR
STEADY_MARKETING_MIN = 1_000_000  # $10,000 a month, then 20% of revenue
STEADY_MARKETING = 0.20


def steady(game: Game, appoint: bool = True, keep: frozenset[int] = frozenset()) -> None:
    """The M3a team on one product; a seed at launch or when runway falls below 12 months,
    whichever comes first, and a Series A when allowed, best pre-money; grows while runway
    stays above 18 months; a second product at $5M ARR."""
    accept_bridges(game)
    months = runway(game)
    live = any(p.status == "live" for p in _products(game))
    seed_ok = live or (months is not None and months < STEADY_SEED_RUNWAY)
    fundraise(game, STEADY_ROUNDS, pick="pre", seed_ok=seed_ok)
    ensure_product(game, 0)
    if arr_cents(game.state, PLAYER, game.loaded.balance) >= STEADY_SECOND_ARR:
        ensure_product(game, 1)
    launch_ready(game)
    wanted = STEADY_START
    if headcount(game) >= STEADY_START and (months is None or months > STEADY_RUNWAY):
        wanted = headcount(game) + 1
    hire(game, wanted, per_month=2, keep=keep)
    set_marketing(game, max(STEADY_MARKETING_MIN, round(STEADY_MARKETING * last_revenue(game))))
    go_public(game)  # M13 (25.9)
    if appoint:  # M8 target 2's vacant arm turns this off
        appoint_executives(game)  # from stage 3


BLITZ_EARLY = 15  # employees by month 12
BLITZ_EARLY_TURNS = 12
BLITZ_RUNWAY = 12  # after month 12, hire while runway is above this
# M10d (product manager, 2026-11-02): every round as soon as allowed includes M10's C and D.
BLITZ_ROUNDS = {
    "seed": 300_000_000,
    "a": 1_000_000_000,
    "b": 3_000_000_000,
    "c": 8_000_000_000,  # $80M, the top of the typical band, as "largest amount"
    "d": 20_000_000_000,  # $200M
}
BLITZ_MARKETING_MIN = 2_500_000  # at least $25,000 a month, else 40% of revenue
BLITZ_MARKETING = 0.40


def blitzscale(game: Game, second: tuple[str, str, tuple[str, ...]] = SECOND_PRODUCT) -> None:
    """15 staff by month 12, then hires while runway is above 12 months; every round as soon
    as allowed (seed, A, B, C, D), largest amount; a second product at Series A."""
    accept_bridges(game)
    fundraise(game, BLITZ_ROUNDS, pick="amount")
    ensure_product(game, 0)
    if "a" in closed_series(game):
        ensure_product(game, 1, second)
    launch_ready(game)
    if game.state.turn < BLITZ_EARLY_TURNS:
        hire(game, BLITZ_EARLY, per_month=3)
    else:
        months = runway(game)
        grow = months is None or months > BLITZ_RUNWAY
        hire(game, headcount(game) + (2 if grow else 0), per_month=2)
    set_marketing(game, max(BLITZ_MARKETING_MIN, round(BLITZ_MARKETING * last_revenue(game))))
    go_public(game)  # M13 (25.9)
    appoint_executives(game)  # M8: from stage 3


STRATEGIES: Final[dict[str, Strategy]] = {
    "do-nothing": do_nothing,
    "bootstrap-frugal": bootstrap_frugal,
    "steady": steady,
    "blitzscale": blitzscale,
}
