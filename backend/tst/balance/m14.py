"""docs/formulas.md 28.9 targets (M14), printed by tools/m14_targets.py and checked nightly
(tests/balance/test_m14_balance.py). True values are read here; this is a tool.

- Targets 2-4 (scripted deals): each seed's steady game at month 36, funded for the deals,
  bids for up to three private companies (the displayed midpoint, then the counter; two
  integrated, one kept as a brand) and one listed company (a friendly bid stepping the
  premium by 5 points until its board agrees), then plays 12 more months.
- Target 5: "steady + regions" (M13b's arm from the first month) against "acquirer" (the
  same plus one startup a year in its categories when cash covers 18 months, integrated),
  120 months.
- Target 6: a deal at a 40% combined share after 2020, reviewed on each seed.
- Target 7: startups bought by incumbents in 120 months of do-nothing games.
"""

from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from statistics import median
from typing import Final

from tst.balance.game import PLAYER, Game, start_game
from tst.balance.m13b import _energy, _launch_region
from tst.balance.report import SCENARIO, _loaded
from tst.balance.strategies import do_nothing, steady
from tst.sim.hiring.formulas import benefits_cents, monthly_salary_cents
from tst.sim.ledger import CASH, COMMON_EQUITY, LedgerEntry, apply_entries
from tst.sim.mna import antitrust, deals, valuation
from tst.sim.mna.deals import BidForCompany
from tst.sim.mna.models import Deal
from tst.sim.rng import RngFactory

SEEDS: Final = tuple(range(1, 11))
MONTHS: Final = 120
SCRIPT_TURN: Final = 36  # deals are scripted from the steady game's month 36
AFTER: Final = 12  # months played after the deals
FUNDING: Final = 50_000_000_000_00  # $50B: the scripted deals are about prices, not cash
PRIVATE_DEALS: Final = 3
REGION_GAP: Final = 24
BUY_CASH_MONTHS: Final = 18  # the acquirer buys when cash covers this many months
STEP: Final = 0.05  # the listed bid's premium step
START_PREMIUM: Final = 0.20
MAX_PREMIUM: Final = 1.0
REVIEW_SHARE: Final = 0.40
REVIEW_YEAR_TURN: Final = 132  # January 2021


@dataclass(frozen=True, slots=True)
class DealRun:
    seed: int
    private_ratios: tuple[float, ...]  # accepted price / V_f
    listed_premiums: tuple[float, ...]  # accepted premium over market cap
    integrated_lost: tuple[float, ...]  # share of acquired key people gone after 12 months
    brand_lost: tuple[float, ...]
    savings: tuple[float, ...]  # 1 - kept people's monthly cost / the target's cost before


@dataclass(frozen=True, slots=True)
class ArmRun:
    seed: int
    arm: str
    arr: int  # cents at month 120; 0 if the game ended
    bought: int
    savings: tuple[float, ...] = ()  # the acquirer's startup integrations, 12 months on
    lost: tuple[float, ...] = ()


@dataclass(frozen=True, slots=True)
class Results:
    deals: list[DealRun]
    arms: list[ArmRun]
    reviews: list[bool]  # blocked after review, by seed
    rival_buys: list[int]  # incumbents' startup purchases in 120 do-nothing months, by seed


def _fund(game: Game, cents: int) -> None:
    entry = LedgerEntry.transfer(
        turn=game.state.turn,
        company_id=PLAYER,
        memo="Target funding",
        debit=CASH,
        credit=COMMON_EQUITY,
        amount=cents,
    )
    game.balances = apply_entries(game.balances, (entry,))


def _bid(game: Game, target: int, price: int, mode: str = "integrate") -> bool:
    _energy(game)
    return game.act(BidForCompany(game.founder_id, target, price, mode=mode))  # type: ignore[arg-type]


def _deal(game: Game, target: int) -> Deal | None:
    return next((d for d in game.state.deals if d.target_id == target), None)


PAYROLL: Final = ("6000_salaries", "6010_benefits", "6100_rent")


def payroll_cents(game: Game, company_id: int) -> int:
    """A company's monthly staff cost: salaries, benefits and offices (pools included)."""
    from tst.sim.hiring.phases import monthly_cost_lines

    lines = monthly_cost_lines(game.state, company_id, game.loaded.balance, game.loaded.game_data)
    tools = game.loaded.balance.costs.tools_per_head_cents * len(game.state.staff(company_id))
    pools = sum(p.headcount for p in game.state.company_pools(company_id))
    tools += round(game.loaded.balance.costs.tools_per_head_cents * pools)
    return sum(amount for _, account, amount, _ in lines if account in PAYROLL) + tools


def buy_private(game: Game, target: int, mode: str = "integrate") -> tuple[int, int] | None:
    """Bid the displayed midpoint, then the counter (28.3); (price, V_f) once agreed."""
    b, g = game.loaded.balance, game.loaded.game_data
    value = valuation.fundamental_value_cents(game.state, target, game.balances, b, g)
    estimate = deals.estimate_cents(game.state, PLAYER, target, game.balances, b, g)
    _bid(game, target, estimate, mode)
    deal = _deal(game, target)
    if deal is None:
        found = next(
            (f for f in game.state.target_files if f.target_id == target and f.counter_cents),
            None,
        )
        if found is None or found.counter_cents is None:
            return None
        _bid(game, target, found.counter_cents, mode)
        deal = _deal(game, target)
    if deal is None or deal.status not in ("accepted", "review"):
        return None
    return deal.price_cents, value


def buy_listed(game: Game, target: int) -> float | None:
    """A friendly bid stepping the premium until the board agrees (28.3)."""
    b, g = game.loaded.balance, game.loaded.game_data
    cap = valuation.market_cap_cents(game.state, target, game.balances, b, g)
    if not cap:
        return None
    premium = START_PREMIUM
    while premium <= MAX_PREMIUM + 1e-9:
        _bid(game, target, round(cap * (1 + premium)))
        deal = _deal(game, target)
        if deal is not None:
            return premium if deal.status in ("accepted", "review") else None
        premium += STEP
    return None


def _people_cost(game: Game, person_ids: tuple[int, ...]) -> int:
    b = game.loaded.balance
    total = 0
    for pid in person_ids:
        e = game.state.employment_of(pid)
        if e is None or not e.counts_as_staff:
            continue
        salary = monthly_salary_cents(e.salary_cents)
        total += salary + benefits_cents(salary, b.payroll) + b.payroll.office_cost_per_head_cents
        total += b.costs.tools_per_head_cents
    return total


def play_deals(seed: int) -> DealRun:
    game = start_game(_loaded("data"), seed, SCENARIO)
    while game.state.turn < SCRIPT_TURN and not game.state.ended:
        steady(game)
        game.turn()
    _fund(game, FUNDING)
    ratios, premiums = [], []
    private = [
        c.id
        for c in game.state.rivals()
        if not valuation.is_listed(game.state, c.id, game.loaded.game_data)
        and c.parent_id is None
        and game.state.company_products(c.id)
    ]
    modes = ["integrate", "integrate", "brand"]
    payroll: dict[int, int] = {}
    bought = 0
    for target in private:
        if bought >= PRIVATE_DEALS:
            break
        got = buy_private(game, target, modes[bought])
        deal = _deal(game, target)
        if got is None or deal is None or deal.status != "accepted":
            if deal is not None and deal.status in ("review", "blocked"):
                from tst.sim.mna.deals import AbandonDeal

                game.act(AbandonDeal(game.founder_id, deal.id))
            continue
        ratios.append(got[0] / got[1])
        payroll[target] = payroll_cents(game, target)
        bought += 1
    listed = [
        c.id
        for c in game.state.rivals()
        if valuation.is_listed(game.state, c.id, game.loaded.game_data)
        and antitrust.combined_share(
            game.state, PLAYER, c.id, game.loaded.balance, game.loaded.game_data
        )[0]
        < game.loaded.balance.antitrust.review
    ]
    if listed:
        premium = buy_listed(game, listed[0])
        if premium is not None:
            premiums.append(premium)
    for _ in range(AFTER + 1):
        if game.state.ended:
            break
        steady(game)
        game.turn()
    lost_i: list[float] = []
    lost_b: list[float] = []
    savings: list[float] = []
    for a in game.state.acquisitions:
        if a.acquirer_id != PLAYER or a.key_people == 0:
            continue
        share = a.departed / a.key_people
        (lost_b if a.mode == "brand" else lost_i).append(share)
        before = payroll.get(a.target_id, 0)
        if a.mode == "integrate" and before > 0:
            savings.append(1 - _people_cost(game, a.person_ids) / before)
    return DealRun(
        seed, tuple(ratios), tuple(premiums), tuple(lost_i), tuple(lost_b), tuple(savings)
    )


def _acquire_yearly(game: Game, payroll: dict[int, int]) -> bool:
    """Once a year, when cash covers 18 months: one startup in the player's categories."""
    if game.state.turn % 12 != 0 or game.state.turn == 0:
        return False
    b, g = game.loaded.balance, game.loaded.game_data
    costs = deals.monthly_costs_cents(game.state, PLAYER, b, g)
    if costs <= 0 or game.cash < BUY_CASH_MONTHS * costs:
        return False
    mine = {p.category for p in game.state.company_products(PLAYER)}
    startups = [
        c
        for c in game.state.rivals()
        if c.is_startup
        and c.parent_id is None
        and any(p.category in mine for p in game.state.company_products(c.id))
    ]
    ranked = sorted(
        startups,
        key=lambda c: (deals.estimate_cents(game.state, PLAYER, c.id, game.balances, b, g), c.id),
    )
    for c in ranked:
        estimate = deals.estimate_cents(game.state, PLAYER, c.id, game.balances, b, g)
        if estimate * 2 > game.cash:
            continue
        before = payroll_cents(game, c.id)
        if buy_private(game, c.id) is not None:
            payroll[c.id] = before
            return True
    return False


def play_arm(seed: int, arm: str) -> ArmRun:
    game = start_game(_loaded("data"), seed, SCENARIO)
    last: int | None = None
    bought = 0
    payroll: dict[int, int] = {}
    savings: list[float] = []
    lost: list[float] = []
    while game.state.turn < MONTHS and not game.state.ended:
        steady(game)
        due = last is None or game.state.turn - last >= REGION_GAP
        if due and _launch_region(game):
            last = game.state.turn
        if arm == "acquirer" and _acquire_yearly(game, payroll):
            bought += 1
        for a in game.state.acquisitions:
            if a.acquirer_id == PLAYER and game.state.turn == a.closed_turn + AFTER:
                if payroll.get(a.target_id):
                    savings.append(1 - _people_cost(game, a.person_ids) / payroll[a.target_id])
                if a.key_people:
                    lost.append(a.departed / a.key_people)
        game.turn()
    arr = game.snapshots[-1].arr_cents if game.snapshots and not game.state.ended else 0
    return ArmRun(seed, arm, arr, bought, tuple(savings), tuple(lost))


def review_blocked(seed: int) -> bool:
    """A deal at a 40% combined share with Zoho in North American mid-market, in January
    2021, reviewed on this seed (28.4): blocked if the review's drawn uniform is below the
    block probability."""
    from tst.sim.mna import formulas as mf
    from tst.sim.products.models import Product, ProductSegment
    from tst.sim.state import with_product, with_product_segment

    loaded = _loaded("data")
    b, g = loaded.balance, loaded.game_data
    game = start_game(loaded, seed, SCENARIO)
    state = replace(game.state, turn=REVIEW_YEAR_TURN)
    zoho = next(c.id for c in state.companies if c.name == "Zoho")
    market = ("b2b_saas", "mid_market", "north_america")
    owners = antitrust.customers_by_market(state, b, g)[market]
    total, theirs = sum(owners.values()), owners[zoho]
    mine = (REVIEW_SHARE * total - theirs) / (1 - REVIEW_SHARE)
    pid, ids = state.next_ids.take("product")
    product = Product(pid, PLAYER, "b2b_saas", "Pipeline", "live", 50.0, 0.0, 30.0, 0, 0, 0)
    state = with_product(replace(state, next_ids=ids), product)
    state = with_product_segment(state, ProductSegment(pid, "mid_market", 40000, mine))
    deal = Deal(1, PLAYER, zoho, 10**10, 1.0, state.turn, close_turn=state.turn + 1)
    screened, _ = antitrust.screen(state, deal, RngFactory(seed), b, g)
    assert screened.status == "review" and screened.blocked_draw is not None
    year = 2010 + state.turn // 12
    return screened.blocked_draw < mf.block_probability(screened.combined_share, year, b.antitrust)


def rival_buys(seed: int) -> int:
    game = start_game(_loaded("data"), seed, SCENARIO)
    while game.state.turn < MONTHS and not game.state.ended:
        do_nothing(game)
        game.turn()
    return sum(1 for d in game.state.deals if d.status == "closed" and d.acquirer_id != PLAYER)


def _play(seed: int) -> tuple[DealRun, ArmRun, ArmRun, int]:
    return (
        play_deals(seed),
        play_arm(seed, "steady_regions"),
        play_arm(seed, "acquirer"),
        rival_buys(seed),
    )


def run(seeds: tuple[int, ...] = SEEDS, jobs: int = 1) -> Results:
    if jobs <= 1:
        out = [_play(s) for s in seeds]
    else:
        with ProcessPoolExecutor(jobs) as pool:
            out = list(pool.map(_play, seeds))
    return Results(
        deals=[o[0] for o in out],
        arms=[a for o in out for a in o[1:3]],
        reviews=[review_blocked(s) for s in seeds],
        rival_buys=[o[3] for o in out],
    )


# --- Targets (28.9) -------------------------------------------------------------------------

T2_PRIVATE: Final = (1.0, 1.6)
T2_LISTED: Final = (0.25, 0.50)
T3_INTEGRATED: Final = (0.10, 0.30)
T3_BRAND_MAX: Final = 0.10
T4_SAVINGS: Final = (0.15, 0.35)
T5_RATIO: Final = (1.0, 1.4)
T6_BLOCKED: Final = (0.15, 0.50)
T7_BUYS: Final = (1, 4)


def _median(values: list[float]) -> float | None:
    return median(values) if values else None


def target_2(r: Results) -> tuple[float | None, float | None]:
    private = [x for d in r.deals for x in d.private_ratios]
    listed = [x for d in r.deals for x in d.listed_premiums]
    return _median(private), _median(listed)


def target_3(r: Results) -> tuple[float | None, float | None]:
    integrated = [x for d in r.deals for x in d.integrated_lost]
    integrated += [x for a in r.arms for x in a.lost]
    brand = [x for d in r.deals for x in d.brand_lost]
    return _median(integrated), _median(brand)


def target_4(r: Results) -> tuple[float | None, float | None]:
    """(scripted deals' median saving, the acquirer's startup integrations' median)."""
    scripted = [x for d in r.deals for x in d.savings]
    startups = [x for a in r.arms for x in a.savings]
    return _median(scripted), _median(startups)


def target_5(r: Results) -> float | None:
    acq = [a.arr for a in r.arms if a.arm == "acquirer"]
    base = [a.arr for a in r.arms if a.arm == "steady_regions"]
    under = median(base) if base else 0
    return median(acq) / under if acq and under else None


def target_6(r: Results) -> float:
    return sum(r.reviews) / len(r.reviews) if r.reviews else 0.0


def target_7(r: Results) -> float | None:
    return _median([float(x) for x in r.rival_buys])


def _fmt(x: float | None, pct: bool = False) -> str:
    if x is None:
        return "-"
    return f"{x:.0%}" if pct else f"{x:.2f}"


def report(r: Results) -> str:
    p, listed = target_2(r)
    lost_i, lost_b = target_3(r)
    sav_s, sav_a = target_4(r)
    lines = [
        f"28.9 target 2: private deals at {_fmt(p)} x V_f (1.0-1.6); listed premium {_fmt(listed, True)} (25-50%)",
        f"28.9 target 3: integrated deals lose {_fmt(lost_i, True)} of key people (10-30%); brands {_fmt(lost_b, True)} (<= 10%)",
        f"28.9 target 4: integration cuts the staff cost base {_fmt(sav_s, True)} (scripted), {_fmt(sav_a, True)} (the acquirer's startups) (15-35%)",
        f"28.9 target 5: acquirer / steady + regions median ARR at year 10: {_fmt(target_5(r))} (1.0-1.4)",
        f"28.9 target 6: deals at 40% blocked after review on {target_6(r):.0%} of seeds after 2020 (15-50%)",
        f"28.9 target 7: incumbents buy {_fmt(target_7(r))} startups a decade, median (1-4)",
        "deal runs: "
        + "; ".join(
            f"seed {d.seed} ratios {[round(x, 2) for x in d.private_ratios]} premium "
            f"{d.listed_premiums} lost {[round(x, 2) for x in d.integrated_lost]}/"
            f"{[round(x, 2) for x in d.brand_lost]} savings {[round(x, 2) for x in d.savings]}"
            for d in r.deals
        ),
        "arms: "
        + "; ".join(f"seed {a.seed} {a.arm} ${a.arr / 100:,.0f} bought {a.bought}" for a in r.arms),
        f"rival buys by seed: {r.rival_buys}; reviews blocked: {r.reviews}",
    ]
    return "\n".join(lines)
