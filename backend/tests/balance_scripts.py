"""Scripted games for the M3a balance checks (earn-and-burn band, incumbent equilibrium).

Pure sim, no persistence: each turn applies the script's actions and `advance_turn`.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from tests.helpers import fresh_game, make_person, rival_cash, with_employee
from tst.loader import LoadedData
from tst.sim.actions import (
    Action,
    AssignUnit,
    ChooseEvent,
    CreateProduct,
    LaunchProduct,
    SetMarketing,
    SetPrice,
    apply_action,
)
from tst.sim.actions.products import launch_problems
from tst.sim.decisions import Decisions
from tst.sim.ledger import CASH, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.snapshot import CompanySnapshot
from tst.sim.state import GameState, with_person
from tst.sim.turn import advance_turn

FOUNDER = 1
BUILDER_SKILL = 11.0  # d about 11 for the three builders (formulas.md 11.14 design check)
EARN_AND_BURN_PRICES = {"smb": 4000, "mid_market": 70_000}  # $40 and $700 a month
MARKETING_CENTS = 1_000_000  # $10,000 a month


@dataclass(slots=True)
class Run:
    loaded: LoadedData
    state: GameState
    balances: dict[tuple[int, str], int]
    seq: int = 0
    snapshots: list[CompanySnapshot] = field(default_factory=list)
    launched_turn: int | None = None
    events: bool = False  # M6: write events with MockLLMAdapter, as the service would
    event_requests: int = 0

    def act(self, action: Action) -> None:
        self.seq += 1
        out = apply_action(
            self.state,
            action,
            RngFactory(self.state.save_meta.master_seed),
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
            seq=self.seq,
        )
        self.state = out.new_state
        self.balances = dict(apply_entries(self.balances, out.ledger_entries))

    def turn(self) -> None:
        if self.events:  # a critical event must be answered first: take its first choice
            for event in self.state.open_events(1):
                if event.severity == "critical" and event.status == "open":
                    self.act(ChooseEvent(FOUNDER, event.id, event.choices[0].key))
        result = advance_turn(
            self.state,
            Decisions(),
            RngFactory(self.state.save_meta.master_seed),
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
        )
        self.state = result.new_state
        self.balances = dict(apply_entries(self.balances, result.ledger_entries))
        self.snapshots.append(result.snapshot.for_company(1))
        if self.events:
            self.event_requests += len(result.event_requests)
            self.write_events()

    def write_events(self) -> None:
        """The post-commit event service, in memory (formulas.md 16.5)."""
        from tst.events.context import Kpis
        from tst.events.service import Writer, write_event
        from tst.llm.offline import MockLLMAdapter
        from tst.llm.settings import LLMSettings

        writer = Writer(MockLLMAdapter(), LLMSettings(), lambda: 1_000_000.0)
        snap = self.snapshots[-1]
        kpis = Kpis(snap.cash_cents, None, snap.mrr_cents, snap.headcount, self.state.player.stage)
        for event in [e for e in self.state.events if e.status == "pending"]:
            self.state = write_event(
                self.state, event, kpis, writer, self.loaded.balance, self.loaded.game_data
            )


def start(loaded: LoadedData, seed: int, scenario: str = "funded_spinout") -> Run:
    state = fresh_game(loaded, seed=seed, scenario=scenario)
    cash = loaded.balance.scenario[scenario].starting_cash_cents
    return Run(loaded, state, {**rival_cash(state, loaded), (1, CASH): cash})


def hire(run: Run, person_id: int, role: str, flat_skill: float | None = None) -> None:
    """An employee on the role's mid-level market salary, in the company root."""
    person = replace(make_person(run.loaded, person_id, role), tags=())
    if flat_skill is not None:
        person = replace(
            person, skills=person.skills.updated(dict.fromkeys(person.skills.keys(), flat_skill))
        )
    salary = run.loaded.game_data.role(role).salary_band_mid_cents["mid"]
    run.state = with_person(with_employee(run.loaded, run.state, person, salary), person)
    run.state = replace(run.state, next_ids=replace(run.state.next_ids, person=person_id + 1))


FINTECH_PRICES = {"smb": 4800, "mid_market": 105_000}  # M8: the same share of p_ref ($60, $1,200)


def earn_and_burn(
    loaded: LoadedData,
    seed: int,
    turns: int,
    marketing: bool = True,
    events: bool = False,
    category: str = "b2b_saas",
    prices: dict[str, int] | None = None,
) -> Run:
    """The M3a brief's script: the founder, 3 builders, 1 account executive and 1 marketer on
    one B2B SaaS product (SMB $40, mid-market $700), $10,000 a month of marketing, launched
    as soon as it is allowed. M8 runs it in another category (18.9 target 4)."""
    prices = EARN_AND_BURN_PRICES if prices is None else prices
    run = start(loaded, seed)
    run.events = events
    for pid in (2, 3, 4):
        hire(run, pid, "software_engineer", BUILDER_SKILL)
    hire(run, 5, "account_executive")
    hire(run, 6, "marketer")
    product = run.state.next_ids.product
    run.act(CreateProduct(FOUNDER, "Pipeline", category, tuple(prices)))
    for segment, price in prices.items():
        run.act(SetPrice(FOUNDER, product, segment, price))
    run.act(AssignUnit(FOUNDER, product, None))
    if marketing:
        run.act(SetMarketing(FOUNDER, product, MARKETING_CENTS))
    for _ in range(turns):
        current = run.state.product(product)
        assert current is not None
        if current.status == "in_development" and not launch_problems(
            run.state, current, loaded.balance, loaded.game_data
        ):
            run.act(LaunchProduct(FOUNDER, product))
            run.launched_turn = run.state.turn
        if run.state.ended:
            break
        run.turn()
    return run
