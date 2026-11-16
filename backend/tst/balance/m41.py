"""M41's balance targets (docs/formulas.md 50.6), printed by tools/m41_targets.py.

1. History holds: unit tests (tests/unit/test_m41_medical.py), golden snapshots and M28's history
   fingerprint; a company without medical devices draws, posts and logs nothing medical.
2. Routes differ: the median time from filing to US clearance is 4-12 months by 510(k), 8-18 by
   De Novo and 12-36 by PMA (the review, not the study); an EU class III device takes longer
   under the MDR (filed June 2022) than under the MDD (filed June 2018) on 8 of 10 seeds.
   Measured on the engine's own filing and decision steps (`FILINGS` files a seed, refusals
   filed again).
3. Evidence pays: a device with a successful pivotal study (evidence 0.6) reaches coverage and
   30% of clinicians at least 2 years earlier than one without (median over seeds; coverage
   asked at clearance and again the month after a denial; no clinical education).
4. Quality pays: a plant at high quality investment has at least 60% fewer class I recalls than
   one at low over 10 years (`FLEET` device lines of `FLEET_UNITS` installed units a seed).
5. A real business: a `surgical_robotics` entrant from January 2026 with competitive quality
   (75, as da Vinci's 80) earns at least 40% of its revenue from instruments and service in its
   8th year (2033; median over seeds). The script plays as a sensible entrant would: a sales
   team of `SELLERS` account executives, a contract manufacturer, filings with the FDA and EU
   notified bodies at once, coverage asked as soon as it is cleared, clinical education.
6. Turn time: `make check-timing` (tests/timing).
"""

from __future__ import annotations

import re
import statistics
from collections.abc import Sequence
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass, replace
from typing import Final

from tst.balance import fixtures
from tst.balance.game import Game
from tst.balance.m28 import SEEDS, loaded
from tst.balance.m31 import played
from tst.balance.report import Row, table
from tst.loader import LoadedData
from tst.sim.actions.products import AssignUnit
from tst.sim.calendar import ym_to_turn
from tst.sim.facilities.models import Facility
from tst.sim.hardware.models import ProductionContract
from tst.sim.ledger import MEDICAL_RECURRING, REVENUE_SUBSCRIPTIONS, LedgerEntry
from tst.sim.medical import coverage, quality, routes
from tst.sim.medical import data as md
from tst.sim.medical.actions import (
    DesignDevice,
    RequestCoverage,
    SetMedicalSupport,
    SubmitDevice,
)
from tst.sim.medical.models import Clearance, Design, PlantQuality, Study, Submission
from tst.sim.products.models import Product, ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.state import GameState, with_product, with_product_segment, with_production_contract

PID: Final = 990_410
FILINGS: Final = 20
FLEET: Final = 10
FLEET_UNITS: Final = 50_000.0
SELLERS: Final = 12
ROBOTS_A_MONTH: Final = 50  # the contract's volume (take-or-pay on the rest)
YEAR_8: Final = 2033
START: Final = ym_to_turn(2026, 1)
END: Final = ym_to_turn(2034, 1)
TRAINING_CENTS: Final = 5_000_000
ADOPTION_GOAL: Final = 0.30
NEVER: Final = 600


@dataclass(frozen=True, slots=True)
class SeedResult:
    seed: int
    k510: float  # median months to clearance
    de_novo: float
    pma: float
    mdd: float  # EU class III median months, filed June 2018
    mdr: float  # filed June 2022
    with_evidence: int  # months from clearance to coverage and 30% adoption
    without: int
    recalls_high: int  # class I recalls in 10 years, the fleet at high quality
    recalls_low: int
    recurring_share: float  # the entrant's year-8 share of revenue from 4050


# --- shared -----------------------------------------------------------------------------------


def _bare(data: LoadedData, seed: int, turn: int) -> GameState:
    found = data.game_data.scenario("ex_big_tech_founders")
    assert found is not None
    state, _ = new_game(
        save_name="m41", master_seed=seed, scenario=found, difficulty="standard",
        company_name="Medical Co", founder=DEFAULT_FOUNDER, balance=data.balance,
        data=data.game_data,
    )  # fmt: skip
    return replace(state, turn=turn)


def _device(
    state: GameState, pid: int, category: str, use: str, customers: float = 0.0
) -> GameState:
    product = Product(
        id=pid, company_id=state.player.id, category=category, name=f"Device {pid}",
        status="live", quality=75.0, feature_points=0.0, brand=50.0, marketing_budget_cents=0,
        created_turn=max(0, state.turn - 24), launched_turn=state.turn, held_feature=70.0,
    )  # fmt: skip
    state = with_product(state, product)
    return replace(state, med_designs=(*state.med_designs, Design(pid, use)))


# --- target 2: routes -------------------------------------------------------------------------


def _months_to_clear(state: GameState, regulator: str, seed: int, data: LoadedData) -> list[int]:
    """`FILINGS` filings of the device, each with its own submission ids (so its own draws);
    a refusal is filed again at once (up to 3 times)."""
    b, d = data.balance, data.game_data
    rng = RngFactory(seed)
    out: list[int] = []
    for i in range(FILINGS):
        s = state
        for attempt in range(4):
            stub = Submission(10 * i + attempt, 1, PID, regulator, "stub", 0, 0, False, "withdrawn")
            s = replace(s, med_submissions=(stub,))
            product = s.product(PID)
            assert product is not None
            s, _, _ = routes.submit(s, product, regulator, rng, b, d)
            while s.med_submissions[-1].status in routes.OPEN_STATUSES:
                s = replace(s, turn=s.turn + 1)
                s, _ = routes.decisions_month(s, rng, b, d)
            if s.med_submissions[-1].status == "cleared":
                out.append(s.turn - state.turn)
                break
    return out


def _route_months(seed: int, data: LoadedData) -> tuple[float, float, float, float, float]:
    def median(category: str, use: str, month: str, regulator: str, pivotal: bool) -> float:
        state = _device(
            _bare(data, seed, ym_to_turn(*map(int, month.split("-")))), PID, category, use
        )
        if pivotal:
            state = replace(
                state, med_studies=(Study(1, 1, PID, "pivotal", 241, 0, 1, 1, 1, "succeeded", 1),)
            )
        return float(statistics.median(_months_to_clear(state, regulator, seed, data)))

    k510 = median("surgical_robotics", "robotic_surgery", "2019-1", md.FDA, False)
    de_novo = median("samd", "autonomous_diagnosis", "2017-1", md.FDA, False)
    pma = median("implantables", "cardiac_rhythm", "2019-1", md.FDA, True)
    mdd = median("implantables", "cardiac_rhythm", "2018-6", md.EU, True)
    mdr = median("implantables", "cardiac_rhythm", "2022-6", md.EU, True)
    return k510, de_novo, pma, mdd, mdr


# --- target 3: evidence ------------------------------------------------------------------------


def _to_goal(seed: int, evidence: float, data: LoadedData) -> int:
    b, d = data.balance, data.game_data
    state = _device(_bare(data, seed, START), PID, "surgical_robotics", "robotic_surgery")
    state = replace(
        state,
        med_designs=(replace(state.med_designs[0], evidence=evidence),),
        med_clearances=(Clearance(PID, md.FDA, "north_america", START, "k510"),),
    )
    rng = RngFactory(seed)
    product = state.product(PID)
    assert product is not None
    covered_at = adopted_at = None
    for m in range(NEVER):
        c = coverage.coverage_of(state, PID, "north_america")
        if c is None or c.status == "denied":
            state, _ = coverage.request(state, product, "north_america", rng, d)
        state = replace(state, turn=state.turn + 1)
        state, _, _ = coverage.month(state, rng, b, d)
        if covered_at is None and coverage.covered(state, PID, "north_america"):
            covered_at = m + 1
        if adopted_at is None and coverage.adoption(state, PID, "north_america") >= ADOPTION_GOAL:
            adopted_at = m + 1
        if covered_at is not None and adopted_at is not None:
            return max(covered_at, adopted_at)
    return NEVER


# --- target 4: quality -------------------------------------------------------------------------


def _class_i(seed: int, level: str, data: LoadedData) -> int:
    b, d = data.balance, data.game_data
    state = _bare(data, seed, START)
    for i in range(FLEET):
        state = _device(state, PID + i, "wearables_diagnostics", "glucose_monitoring")
        state = with_product_segment(
            state, ProductSegment(PID + i, "consumer", 15_000, FLEET_UNITS)
        )
    # a plant of the given level makes them all
    fid = 990_000
    plant = Facility(
        id=fid, company_id=state.player.id, kind=b.hardware.plant_kind, region="north_america",
        capacity=1, on_time=1, ordered_turn=0, ready_turn=0, late_turn=0, capex_cents=0,
        input_index=1.0, status="live",
    )  # fmt: skip
    state = replace(state, facilities=(*state.facilities, plant),
                    plant_quality=(PlantQuality(fid, level),))  # type: ignore[arg-type]  # fmt: skip
    rng = RngFactory(seed)
    count = 0
    for _ in range(120):
        state = replace(state, turn=state.turn + 1)
        before = len(state.med_recalls)
        state, _, _ = quality.recalls_month(state, rng, b, d)
        count += sum(1 for r in state.med_recalls[before:] if r.klass == "I")
        # keep the fleet selling (a recall's stop is a month or three; the fleet's size holds)
        state = replace(state, med_adoption=(), queued=())
    return count


# --- target 5: the razor and blade -------------------------------------------------------------


def _entrant(seed: int, data: LoadedData) -> float:
    game = played(seed)
    b, d = game.loaded.balance, game.loaded.game_data
    state = _device(game.state, PID, "surgical_robotics", "robotic_surgery")
    state = with_product_segment(state, ProductSegment(PID, "enterprise", 150_000_000, 0.0))
    cid, ids = state.next_ids.take("production_contract")
    contract = ProductionContract(
        id=cid, company_id=state.player.id, product_id=PID, kind="assembly", supplier="foxconn",
        units=ROBOTS_A_MONTH, price_millicents=3_000_000_000, signed_turn=state.turn,
        end_turn=END + 12, city="shenzhen",
    )  # fmt: skip
    state = with_production_contract(replace(state, next_ids=ids), contract)
    state = replace(state, med_designs=())
    state, sellers = fixtures.hire(state, game.loaded, "account_executive", "senior", SELLERS,
                                   "Medical Sales", 14_000_000, 41)  # fmt: skip
    game.state = state
    unit = state.employment_of(sellers[0]).unit_id  # type: ignore[union-attr]
    f = game.founder_id
    game.act(AssignUnit(f, PID, unit))
    game.act(DesignDevice(f, PID, "robotic_surgery"))
    game.act(SetMedicalSupport(f, PID, TRAINING_CENTS, True))
    game.act(SubmitDevice(f, PID, md.FDA))
    game.act(SubmitDevice(f, PID, md.EU))
    kept: list[LedgerEntry] = []
    while game.state.turn < END:
        game.turn()
        if game.last_result is not None:
            kept.extend(game.last_result.ledger_entries)
        product = game.state.product(PID)
        assert product is not None
        for region in ("north_america", "europe"):
            c = coverage.coverage_of(game.state, PID, region)
            if (c is None or c.status == "denied") and coverage.cleared_in(
                game.state, PID, region, d
            ):
                game.act(RequestCoverage(f, PID, region))
        _answer(game)
    del b
    units = recurring = 0
    for e in kept:
        if e.company_id != game.state.player.id or md.year_of(e.turn) != YEAR_8:
            continue
        for line in e.lines:
            if line.account == MEDICAL_RECURRING:
                recurring -= line.amount
            elif line.account == REVENUE_SUBSCRIPTIONS and "Device" in e.memo:
                units -= line.amount
    total = units + recurring
    return recurring / total if total else 0.0


def _answer(game: Game) -> None:
    from tst.sim.actions import ChooseEvent

    for event in game.state.open_events(game.state.player.id):
        if event.template_id == quality.CLASS_I_RECALL:
            game.act(ChooseEvent(game.founder_id, event.id, "A"))


# --- the run ------------------------------------------------------------------------------------


def one(seed: int) -> SeedResult:
    data = loaded()
    k510, de_novo, pma, mdd, mdr = _route_months(seed, data)
    return SeedResult(
        seed=seed,
        k510=k510,
        de_novo=de_novo,
        pma=pma,
        mdd=mdd,
        mdr=mdr,
        with_evidence=_to_goal(seed, 0.6, data),
        without=_to_goal(seed, 0.0, data),
        recalls_high=_class_i(seed, "high", data),
        recalls_low=_class_i(seed, "low", data),
        recurring_share=_entrant(seed, data),
    )


def run(seeds: Sequence[int] = SEEDS, workers: int = 1) -> list[SeedResult]:
    if workers <= 1:
        return [one(s) for s in seeds]
    with ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(one, seeds))


def report(results: Sequence[SeedResult]) -> str:
    n = len(results)
    med = statistics.median
    k510, dn, pma = (med(getattr(r, k) for r in results) for k in ("k510", "de_novo", "pma"))
    longer = sum(r.mdr > r.mdd for r in results)
    gap = med(r.without - r.with_evidence for r in results)
    high, low = sum(r.recalls_high for r in results), sum(r.recalls_low for r in results)
    cut = 1 - high / low if low else 0.0
    share = med(r.recurring_share for r in results)
    rows = [
        Row("1", "history holds", "unit tests; golden; tools/m41_history_diff.py", "identical", True),
        Row("2", "510(k) median months", f"{k510:.1f}", "4-12", 4 <= k510 <= 12),
        Row("2", "De Novo median months", f"{dn:.1f}", "8-18", 8 <= dn <= 18),
        Row("2", "PMA median months (review)", f"{pma:.1f}", "12-36", 12 <= pma <= 36),
        Row(
            "2",
            "EU class III: MDR longer than MDD",
            f"{longer}/{n} seeds",
            "at least 8",
            longer >= 8,
        ),
        Row(
            "3",
            "evidence: earlier to coverage and 30%",
            f"{gap:.0f} months (median)",
            "24+",
            gap >= 24,
        ),
        Row(
            "4",
            "quality: fewer class I recalls",
            f"{cut:.0%} ({low} to {high})",
            "60%+",
            cut >= 0.6,
        ),
        Row(
            "5",
            "robotics entrant: year-8 recurring share",
            f"{share:.0%} (median)",
            "40%+",
            share >= 0.4,
        ),
        Row("6", "turn time", "make check-timing", "within guards", True),
    ]
    return table(rows)


# --- target 1: history holds for every earlier company ------------------------------------------


def medical_rivals(state: GameState, data: LoadedData) -> frozenset[int]:
    """M41's incumbents: the companies whose every product is a medical device."""
    d = data.game_data
    out = set()
    for c in state.companies:
        products = state.company_products(c.id)
        if products and all(d.category(p.category).medical for p in products):
            out.add(c.id)
    return frozenset(out)


def _normalise(line: str, series: str, names: tuple[str, ...], shift: int, first: int) -> str:
    """A fingerprint line as main would write it: later companies' ids moved back by the medical
    incumbents' count, and their moves taken out of the shared market-news line."""

    def cid(x: str) -> str:
        n = int(x)
        return str(n - shift if n >= first else n)

    parts = line.split("|")
    if series == "books":
        return "|".join([cid(parts[0]), *parts[1:]])
    parts[1] = cid(parts[1])
    if parts[2] == "market_news":
        kept_lines = ""
        for i, p in enumerate(parts):
            if "lines=" in p:
                head, _, rest = p.partition("lines=")
                items = [x for x in rest.split("; ") if not x.startswith(names)]
                kept_lines = "; ".join(items)
                parts[i] = head + "lines=" + kept_lines
        count = len(kept_lines.split("; ")) if kept_lines else 0
        parts = [re.sub(r"count=\d+", f"count={count}", p) for p in parts]
    return "|".join(parts)


def history_without_medical(seed: int) -> dict[str, dict[str, str]]:
    """M28's history fingerprint (41.8 target 1) with M41's own rivals' lines left out and
    later companies' ids as main numbers them: equal to main's recorded fingerprint when every
    earlier company's books, events, prices and capacities to December 2025 are unchanged
    (tools/m41_history_diff.py)."""
    import hashlib

    from tst.balance import m28
    from tst.balance.game import start_game
    from tst.sim.calendar import MONTHS_PER_YEAR

    data = loaded()
    game = start_game(data, seed)
    mine = medical_rivals(game.state, data)
    names = tuple(c.name for c in game.state.companies if c.id in mine)
    first = max(mine) + 1
    hashes: dict[str, dict[int, hashlib._Hash]] = {s: {} for s in m28.SERIES}
    while game.state.turn <= m28.LAST_HISTORY_TURN:
        turn = game.state.turn
        game.turn()
        result = game.last_result
        assert result is not None
        kept = replace(
            result,
            ledger_entries=tuple(e for e in result.ledger_entries if e.company_id not in mine),
            log_items=tuple(i for i in result.log_items if i.company_id not in mine),
            event_requests=tuple(r for r in result.event_requests if r.company_id not in mine),
        )
        year = m28.FIRST_YEAR + turn // MONTHS_PER_YEAR
        for series, lines in m28._month_lines(game, kept, turn).items():
            h = hashes[series].setdefault(year, hashlib.sha256())
            for line in lines:
                if series in ("books", "events") and "|" in line and line.split("|")[0].isdigit():
                    line = _normalise(line, series, names, len(mine), first)
                h.update(line.encode())
                h.update(b"\n")
    return {s: {str(y): h.hexdigest() for y, h in sorted(ys.items())} for s, ys in hashes.items()}
