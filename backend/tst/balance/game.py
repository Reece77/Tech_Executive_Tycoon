"""One scripted game over the pure sim: actions between turns, `advance_turn`, and the event
service in memory with `MockLLMAdapter` (as M6's balance scripts do). Records what the
balance targets need each month."""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field

from tst.events.context import Kpis
from tst.events.service import Writer, write_event
from tst.llm.offline import MockLLMAdapter
from tst.llm.settings import LLMSettings
from tst.loader import LoadedData
from tst.sim.actions import Action, ChooseEvent, apply_action
from tst.sim.decisions import Decisions
from tst.sim.errors import SimError
from tst.sim.finance import formulas as ff
from tst.sim.finance.captable import founder_bp
from tst.sim.finance.fundraising import arr_cents, base_value, climate, company_growth
from tst.sim.finance.statements import cash_before_financing
from tst.sim.ledger import CASH, apply_entries
from tst.sim.rng import RngFactory
from tst.sim.setup import DEFAULT_FOUNDER, new_game
from tst.sim.snapshot import CompanySnapshot
from tst.sim.state import GameState
from tst.sim.turn import advance_turn

log = logging.getLogger(__name__)

PLAYER = 1


@dataclass(slots=True)
class Game:
    """A player company driven by a strategy. `act` swallows rule errors: a script that tries
    something the rules refuse (no energy, no cash) simply does not do it that month."""

    loaded: LoadedData
    state: GameState
    balances: dict[tuple[int, str], int]
    seq: int = 0
    snapshots: list[CompanySnapshot] = field(default_factory=list)
    founder_value: dict[int, int] = field(default_factory=dict)  # turn -> cents (month end)
    traction_above_floor: dict[int, bool] = field(default_factory=dict)
    refused: Counter[str] = field(default_factory=Counter)  # action kind -> refusals
    event_requests: int = 0
    month_lines: list[tuple[int, str, int]] = field(default_factory=list)  # actions this month
    _writer: Writer = field(
        default_factory=lambda: Writer(MockLLMAdapter(), LLMSettings(), lambda: 1_000_000.0)
    )

    @property
    def founder_id(self) -> int:
        founder = self.state.founder_of(PLAYER)
        return founder.id if founder is not None else 0

    @property
    def cash(self) -> int:
        return self.balances.get((PLAYER, CASH), 0)

    def energy(self, person_id: int | None = None) -> int:
        ps = self.state.person_state(person_id or self.founder_id)
        return ps.energy or 0

    def act(self, action: Action) -> bool:
        """Apply one action; False when the rules refuse it."""
        self.seq += 1
        try:
            out = apply_action(
                self.state,
                action,
                RngFactory(self.state.save_meta.master_seed),
                self.loaded.balance,
                self.loaded.game_data,
                self.balances,
                seq=self.seq,
            )
        except SimError as exc:
            self.refused[action.kind] += 1
            log.debug("turn %d: %s refused: %s", self.state.turn, action.kind, exc)
            return False
        self.state = out.new_state
        self.balances = apply_entries(self.balances, out.ledger_entries)
        self.month_lines += [
            (e.turn, line.account, line.amount)
            for e in out.ledger_entries
            if e.company_id == PLAYER
            for line in e.lines
        ]
        return True

    def turn(self) -> None:
        """Answer an open critical event with its first choice, play the month, write the
        next month's events and record the month end."""
        for event in self.state.open_events(PLAYER):
            if event.severity == "critical" and event.status == "open":
                self.act(ChooseEvent(self.founder_id, event.id, event.choices[0].key))
        types = {a.code: a.type for a in self.loaded.game_data.accounts}
        result = advance_turn(
            self.state,
            Decisions(),
            RngFactory(self.state.save_meta.master_seed),
            self.loaded.balance,
            self.loaded.game_data,
            self.balances,
            prior_flow={PLAYER: cash_before_financing(self.month_lines, types)},  # as a save
        )
        self.month_lines = []
        self.state = result.new_state
        self.balances = apply_entries(self.balances, result.ledger_entries)
        snap = result.snapshot.for_company(PLAYER)
        self.snapshots.append(snap)
        self.event_requests += len(result.event_requests)
        self._write_events(snap)
        self.record_value()

    def _write_events(self, snap: CompanySnapshot) -> None:
        kpis = Kpis(snap.cash_cents, None, snap.mrr_cents, snap.headcount, self.state.player.stage)
        for event in [e for e in self.state.events if e.status == "pending"]:
            self.state = write_event(
                self.state, event, kpis, self._writer, self.loaded.balance, self.loaded.game_data
            )

    def record_value(self) -> None:
        """Founder value at this month end (balance-targets.md): ownership x V_base; 0 once
        the game has ended. Also whether V_traction > V_floor."""
        turn = self.state.turn
        if self.state.ended:
            self.founder_value[turn] = 0
            self.traction_above_floor[turn] = False
            return
        balance, data = self.loaded.balance, self.loaded.game_data
        value = base_value(self.state, PLAYER, balance, data)
        self.founder_value[turn] = value * founder_bp(self.state, PLAYER) // 10_000
        multiple = ff.arr_multiple(
            company_growth(self.state, PLAYER, balance), climate(self.state, data), balance.finance
        )
        traction = round(arr_cents(self.state, PLAYER, balance) * multiple)
        live = any(p.status == "live" for p in self.state.company_products(PLAYER))
        floor = ff.value_floor_cents(live, len(self.state.staff(PLAYER)), balance.finance)
        self.traction_above_floor[turn] = traction > floor


def start_game(
    loaded: LoadedData,
    seed: int,
    scenario: str = "ex_big_tech_founders",
    difficulty: str = "standard",
) -> Game:
    """A new game as `create_save` would make it, held in memory."""
    scenario_def = loaded.game_data.scenario(scenario)
    if scenario_def is None:
        raise ValueError(f"unknown scenario {scenario!r}")
    state, entries = new_game(
        save_name="balance",
        master_seed=seed,
        scenario=scenario_def,
        difficulty=difficulty,
        company_name="Balance Co",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    game = Game(loaded, state, apply_entries({}, entries))
    game.record_value()
    return game
