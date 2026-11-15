"""M34's balance targets (docs/formulas.md 48.5), printed by tools/m34_targets.py.

Every run starts from M31's do-nothing game played to January 2026 (history's markets, $50B).
The owner scripts then give the player a phone line on its own OS and store holding `SHARE` of
the device users of North America and Europe, held there each month (the targets' premise, as
M31's target 3), and answer the player's regulation events by strategy:

1. History holds: tests/unit/test_m34_regulation.py (the data's designations, fines and rulings)
   and every earlier guard (M28's fingerprint: nothing runs or posts before 2026).
2. Most big platforms meet a remedy (`default`: first answers; self-preferencing off): a duty or
   a fine by December 2034 on at least 7 of 10 seeds.
3. Break-ups are rare and warned: `defiant` (self-preferencing strong every month; contests the
   charges, appeals rulings) gets a structural order by December 2039 on at most 2 of 10 seeds,
   never with under 3 years of warning; `compliant` (self-preferencing off; settles at the
   inquiry) on none.
4. Compliance and influence help: `careful` (self-preferencing strong until it settles with an
   EU commitment, which it then keeps; settles at the charges; $500k a month of lobbying in
   Europe) pays 30-60% less in EU fines over 2026-2039 than
   `defiant`, on the mean over seeds.
5. Rivals are regulated too: a rival platform owner (Apple, Microsoft) faces a duty or fine the
   model made (a designation, a remedy, a commitment or a fine) from 2026 on at least 8 of 10
   seeds (read from the `default` runs to 2034 and `defiant` to 2039)."""

from __future__ import annotations

import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance.game import Game
from tst.balance.m28 import SEEDS
from tst.balance.m31 import CONTRACT_UNITS, LINE, _copy, _static, played
from tst.balance.report import Row, table
from tst.sim.actions import ChooseEvent
from tst.sim.actions.founder import SetLobbying
from tst.sim.calendar import ym_to_turn
from tst.sim.geo.models import RegionalSegment
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import FINES, LedgerEntry
from tst.sim.platforms.actions import on_launch
from tst.sim.platforms.models import DeviceRun
from tst.sim.platforms.phase import addressable_in, home_of
from tst.sim.products.models import Product, ProductSegment
from tst.sim.regulation import cases, structural
from tst.sim.state import (
    GameState,
    with_product,
    with_product_segment,
    with_production_contract,
    with_regional_segment,
)

SHARE: Final = 0.45
EUROPE: Final = "europe"
END_2034: Final = ym_to_turn(2034, 12)
END_2039: Final = ym_to_turn(2039, 12)
START: Final = 192
OS_ID: Final = LINE + 1
APP: Final = LINE + 2  # the player's consumer app: its booked revenue is the group's turnover
APP_CUSTOMERS: Final = 40_000_000.0  # in each of North America and Europe
APP_PRICE: Final = 500  # cents a month
LOBBY_DOLLARS: Final = 500_000
RIVAL_OWNERS: Final = ("Apple", "Microsoft")
STRATEGIES: Final = ("default", "defiant", "compliant", "careful")
# The answers each strategy gives (template -> choice key): A, B, C as in events/regulation.yaml
ANSWERS: Final[dict[str, dict[str, str]]] = {
    "default": {cases.INQUIRY: "A", cases.OBJECTIONS: "A", cases.RULING: "A"},
    "defiant": {cases.INQUIRY: "A", cases.OBJECTIONS: "B", cases.RULING: "B"},
    "compliant": {cases.INQUIRY: "B", cases.OBJECTIONS: "A", cases.RULING: "A"},
    "careful": {cases.INQUIRY: "A", cases.OBJECTIONS: "A", cases.RULING: "A"},
}
ORDER_ANSWER: Final = "C"  # appeal a structural order (none of the scripts sells)


def owner(seed: int, self_pref: str) -> tuple[Game, int]:
    """M31's played game with the player's phone on its own OS (module docstring)."""
    game = _copy(played(seed))
    d = game.loaded
    b, gd = d.balance, d.game_data
    state = _static(game.state, LINE, "devices", "Own Phone", 75.0)
    state = _hold(state, b, gd)
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid, company_id=state.player.id, product_id=LINE, kind="assembly", supplier="foxconn",
        units=CONTRACT_UNITS, price_millicents=1_300_000, signed_turn=state.turn,
        end_turn=END_2039, city="shenzhen",
    )  # fmt: skip
    state = with_production_contract(replace(state, next_ids=ids), contract)
    os_product = Product(
        id=OS_ID, company_id=state.player.id, category="os", name="Own OS", status="live",
        quality=60.0, feature_points=0.0, brand=40.0, marketing_budget_cents=0,
        created_turn=state.turn - 36, launched_turn=state.turn,
    )  # fmt: skip
    state = on_launch(with_product(state, os_product), os_product, gd)
    own = next(p for p in state.platforms if p.product_id == OS_ID)
    state = replace(
        state,
        device_runs=(*state.device_runs, DeviceRun(LINE, own.id, state.turn)),
        platforms=tuple(
            replace(p, self_pref=self_pref) if p.id == own.id else p  # type: ignore[arg-type]
            for p in state.platforms
        ),
    )
    game.state = state
    return game, own.id


def _hold(state: GameState, b: object, gd: object) -> GameState:
    """The phone at SHARE of North America's (home) and Europe's device users, and the app's
    APP_CUSTOMERS in each (the targets' premise: a dominant platform owner with a business)."""
    from tst.sim.data_models import Balance, GameData

    assert isinstance(b, Balance) and isinstance(gd, GameData)
    home = home_of(state, b, gd) or "north_america"
    n = SHARE * addressable_in(state, "devices", gd, home, home)
    seg = state.product_segment(LINE, "consumer")
    state = with_product_segment(
        state,
        replace(seg, customers=n) if seg else ProductSegment(LINE, "consumer", 45_000, n),
    )
    e = SHARE * addressable_in(state, "devices", gd, EUROPE, home)
    rows = [r for r in state.regional_segments_of(LINE, EUROPE) if r.segment == "consumer"]
    row = (
        replace(rows[0], customers=e)
        if rows
        else RegionalSegment(LINE, EUROPE, "consumer", 45_000, e)
    )
    state = with_regional_segment(state, row)
    if state.product(APP) is None:
        state = _static(state, APP, "consumer_apps", "Own Chat", 80.0)
    app = state.product_segment(APP, "consumer")
    state = with_product_segment(
        state,
        replace(app, customers=APP_CUSTOMERS)
        if app
        else ProductSegment(APP, "consumer", APP_PRICE, APP_CUSTOMERS),
    )
    rows = [r for r in state.regional_segments_of(APP, EUROPE) if r.segment == "consumer"]
    row = (
        replace(rows[0], customers=APP_CUSTOMERS)
        if rows
        else RegionalSegment(APP, EUROPE, "consumer", APP_PRICE, APP_CUSTOMERS)
    )
    return with_regional_segment(state, row)


def _answer(game: Game, strategy: str) -> None:
    for event in game.state.open_events(game.state.player.id):
        if event.status != "open" or event.category != "regulation":
            continue
        key = (
            ORDER_ANSWER
            if event.template_id == structural.ORDER_EVENT
            else ANSWERS[strategy].get(event.template_id, "A")
        )
        game.act(ChooseEvent(game.founder_id, event.id, key))


@dataclass(frozen=True, slots=True)
class Run:
    duties: int  # the player's duties in force at the end
    fines_eu: int  # the player's EU fines and settlements, cents (refunds net)
    fines: int  # all the player's fines, cents
    orders: int
    order_lead: int | None  # months of warning before the first order
    rival_model: bool  # a rival platform owner met a model-made duty or fine from 2026
    rival_any: bool  # ... or a duty dated from 2026 at all (history's designations included)
    cases: tuple[str, ...] = ()  # the player's cases: regulator/last step/outcome
    rival_cases: int = 0  # cases the model opened on rival platform owners


def play(seed: int, strategy: str, until: int) -> Run:
    pref = {"defiant": "strong", "careful": "strong"}.get(strategy, "off")
    game, platform_id = owner(seed, pref)
    d = game.loaded
    if strategy == "careful":
        game.act(SetLobbying(game.founder_id, EUROPE, LOBBY_DOLLARS))
    me = game.state.player.id
    rivals = {c.id for c in game.state.companies if c.name in RIVAL_OWNERS}
    kept: list[LedgerEntry] = []
    while game.state.turn <= until:
        _answer(game, strategy)
        committed = strategy == "careful" and any(
            x.company_id == me and x.source == "commitment" and x.regulator == "eu_commission"
            for x in game.state.duties
        )  # a careful player keeps the commitments it settled with (rule 2: a sensible player)
        if pref != "off" and not committed:  # keep the setting on whatever a duty forced
            game.state = replace(
                game.state,
                platforms=tuple(
                    replace(p, self_pref=pref) if p.id == platform_id else p  # type: ignore[arg-type]
                    for p in game.state.platforms
                ),
            )
        game.turn()
        if game.last_result is not None:
            kept.extend(game.last_result.ledger_entries)
        game.state = _hold(game.state, d.balance, d.game_data)
    s = game.state
    fines = [(e, line.amount) for e in kept for line in e.lines if line.account == FINES]
    # A settlement posts when the player answers (an action, outside the turn's entries): read
    # the cases' own fines (an annulled fine came back) and the 6970 balance.
    fines_eu = sum(
        c.fine_cents
        for c in s.reg_cases
        if c.company_id == me and c.regulator == "eu_commission" and c.outcome != "annulled"
    )
    orders = [o for o in s.reg_orders if o.company_id == me]
    lead = min((o.ordered_turn - o.warned_from for o in orders), default=None)
    made = any(x.company_id in rivals and x.source != "designation" for x in s.duties)
    rival_model = (
        made
        or any(e.company_id in rivals for e, _ in fines)
        or any(g.company_id in rivals for g in s.designations)
    )
    rival_any = rival_model or any(
        x.company_id in rivals and x.from_turn >= START for x in s.duties
    )
    return Run(
        duties=sum(1 for x in s.duties if x.company_id == me and x.from_turn <= s.turn),
        fines_eu=fines_eu,
        fines=game.balances.get((me, FINES), 0),
        orders=len(orders),
        order_lead=lead,
        rival_model=rival_model,
        rival_any=rival_any,
        cases=tuple(
            f"{c.regulator}/{c.steps[-1][0]}/{c.outcome}" for c in s.reg_cases if c.company_id == me
        ),
        rival_cases=sum(1 for c in s.reg_cases if c.company_id in rivals),
    )


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    default: Run
    defiant: Run
    compliant: Run
    careful: Run


def one(seed: int) -> SeedResult:
    return SeedResult(
        seed=seed,
        default=play(seed, "default", END_2034),
        defiant=play(seed, "defiant", END_2039),
        compliant=play(seed, "compliant", END_2039),
        careful=play(seed, "careful", END_2039),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> list[SeedResult]:
    if workers <= 1:
        return [one(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, seeds))


def report(results: Sequence[SeedResult]) -> str:
    n = len(results)
    met = sum(r.default.duties > 0 or r.default.fines > 0 for r in results)
    broken = sum(r.defiant.orders > 0 for r in results)
    leads = [r.defiant.order_lead for r in results if r.defiant.order_lead is not None]
    calm = sum(r.compliant.orders > 0 for r in results)
    base = statistics.mean(r.defiant.fines_eu for r in results)
    care = statistics.mean(r.careful.fines_eu for r in results)
    cut = 1 - care / base if base > 0 else 0.0
    rivals = sum(r.default.rival_model or r.defiant.rival_model for r in results)
    rivals_any = sum(r.default.rival_any or r.defiant.rival_any for r in results)
    rows = [
        Row("1", "history holds", "unit tests; M28 fingerprint", "identical", True),
        Row("2", "big platforms meet a remedy", f"{met}/{n} seeds", "at least 7", met >= 7),
        Row(
            "3",
            "defiant: structural orders",
            f"{broken}/{n} (shortest warning {min(leads, default=0)} months)",
            "at most 2, 36+ months",
            broken <= 2 and all(x >= 36 for x in leads),
        ),
        Row("3", "compliant: structural orders", f"{calm}/{n}", "none", calm == 0),
        Row(
            "4",
            "settling and influence cut EU fines",
            f"{cut:.0%} (mean ${base / 100 / 1e9:.2f}B to ${care / 100 / 1e9:.2f}B)",
            "30-60%",
            0.30 <= cut <= 0.60,
        ),
        Row(
            "5",
            "rivals regulated after 2026",
            f"{rivals}/{n} model-made ({rivals_any}/{n} with history's dated duties)",
            "at least 8",
            rivals >= 8,
        ),
    ]
    return table(rows)
