"""Automated areas in phase 2 (docs/formulas.md 40.2-40.3, 40.6; ADR-0015).

After the executives with authority and before the CEO, every person who owns areas of the
player's company runs them in the player's priority order with automation.owner_energy x the
support pool's coverage c a month; an area costs its `energy`, and the rest are skipped ("no
time this month"). Each decision goes through `AutoRun.attempt`: a one-off, or a commitment at
or above the owner's limit, becomes a proposal; an owner whose month has committed
monthly_limit_mult x its limit stops ("over this month's budget"); anything else is applied
through the same actions the player uses, as the owner.

Quality: a seat holder running its own seat's existing rule keeps stream `delegate` and the
key the seat rule always used (24.2); every other owner draws from stream `automation`, key
(person id, area index, n). A company with no owner rows is returned untouched (40.9).
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from typing import Final

import numpy as np

from tst.sim.actions import Action, action_payload, apply_action
from tst.sim.automation import limits, owners
from tst.sim.automation.config import AREA_SEAT_RULE
from tst.sim.automation.models import AreaDecision, AreaOwner, DecisionKind
from tst.sim.data_models import AUTHORITY_SEATS, Balance, GameData
from tst.sim.errors import SimError
from tst.sim.ledger import AccountCode, LedgerEntry, apply_entries
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import Cents
from tst.sim.org.delegates import DelegateAction, DelegateRun, delegate_draws
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import Authority, Proposal
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    with_area_decisions,
    with_person_state,
    with_proposal,
    without_area_owner,
)

ACTION_KEY: Final = 1_000  # tunable-exempt: stream-key offset for an owner's actions' own draws
QUALITY_KEY = 1_000_000  # tunable-exempt: authority.QUALITY_KEY, the seat rules' quality key
KPI: Final = "kpi"  # an AreaDecision kind that records a KPI's month-end value (40.4)


def automation_draws(
    rng: RngFactory, turn: int, person_id: int, key: int, n: int
) -> np.random.Generator:
    """Stream `automation` keyed (person id, area index or ACTION_KEY + index, n): the one call
    site (ADR-0013, stream 56)."""
    return rng.stream(turn, "automation", person_id, key, n)


@dataclass(slots=True)
class AutoRun(DelegateRun):
    """One area's month for its owner: every action passes the limit and one-off tests."""

    owner: AreaOwner | None = None
    area_index: int = 0
    committed: int = 0  # this area's commitments this month
    n: int = 0  # decisions drawn this month
    text: str = ""  # what the rule says it is doing (for a proposal)
    decisions: list[tuple[DecisionKind, str, int, int | None]] = field(default_factory=list)
    over_budget: bool = False
    fired: int = 0
    last_cost: int = 0  # the last applied action's commitment

    def draw(self) -> float:
        """One quality uniform for a new-area decision (40.3)."""
        assert self.owner is not None
        u = float(
            automation_draws(
                self.rng, self.state.turn, self.owner.person_id, self.area_index, self.n
            ).random()
        )
        self.n += 1
        return u

    def attempt(self, company_id: int, action: Action) -> bool:
        assert self.owner is not None
        o, b = self.owner, self.balance
        if limits.is_one_off(self.state, company_id, action, b, fired_this_month=self.fired):
            self.propose(action, 0, "it is a one-off")
            return False
        cost = limits.commitment(self.state, action, b, self.data)
        if cost >= o.limit_cents and cost > 0:
            self.propose(action, cost, "it is at or above the limit")
            return False
        cap = b.automation.monthly_limit_mult * o.limit_cents
        if self.committed + cost > cap:
            if not self.over_budget:
                self.decisions.append(("over_budget", "over this month's budget", 0, None))
                self.over_budget = True
            return False
        turn, actor, key, n = self.state.turn, action.actor_id, ACTION_KEY + self.area_index, self.n

        def draws() -> np.random.Generator:
            return automation_draws(self.rng, turn, actor, key, n)

        try:
            out = apply_action(
                self.state, action, self.rng, b, self.data, self.balances, seq=0, draws=draws
            )
        except SimError:
            return False
        self.n += 1
        self.state = out.new_state
        self.balances = apply_entries(self.balances, out.ledger_entries)
        self.entries += out.ledger_entries
        self.logs += [replace(i, in_digest=True) for i in out.log_items]
        self.taken.append((company_id, action))
        self.committed += cost
        if action.kind == "fire":
            self.fired += 1
        self.last_cost = cost
        return True

    def propose(self, action: Action, cost: int, why: str) -> None:
        """40.2: a proposal for the player, unless the same move is pending or was declined or
        expired within automation.repropose_months."""
        assert self.owner is not None
        o, b, state = self.owner, self.balance, self.state
        payload = json.dumps(action_payload(action), sort_keys=True, default=list)
        quiet = b.automation.repropose_months
        for p in state.proposals:
            if p.company_id != o.company_id or p.kind != "auto":
                continue
            if dict(p.params).get("action") != payload:
                continue
            if p.status == "pending" or (
                p.status in ("declined", "expired")
                and (p.resolved_turn or p.turn) > state.turn - quiet
            ):
                return
        pid, ids = state.next_ids.take("proposal")
        text = self.text or action.kind.replace("_", " ")
        params: tuple[tuple[str, int | str], ...] = (
            ("action", payload),
            ("area", o.area),
            ("commitment_cents", cost),
            ("expires_turn", state.turn + b.automation.proposal_months),
            ("why", why),
        )
        seat = owners.area_def(b, o.area).seat or "lead"
        proposal = Proposal(pid, o.company_id, seat, o.person_id, state.turn, "auto", params, text)
        self.state = with_proposal(replace(state, next_ids=ids), proposal)
        person = state.person(o.person_id)
        self.logs.append(
            inbox_item(
                state.turn,
                o.company_id,
                "exec_proposal",
                link_kind="person",
                link_id=o.person_id,
                name=f"{person.first_name} {person.last_name}",
                what=owners.area_def(b, o.area).label,
                detail=f"{person.first_name} proposes to {text} ({why}).",
            )
        )
        self.decisions.append(("proposal", f"proposed to {text} ({why})", cost, pid))


class AutoSeat:
    """The seat rules' `_Seat` for an owned area: act() remembers the text for a proposal and
    records the decision with its commitment."""

    def __init__(self, run: AutoRun, a: Authority, holder: int, right: bool) -> None:
        self.run, self.a, self.holder, self.right = run, a, holder, right
        self.notes: list[tuple[str, bool]] = []

    @property
    def state(self) -> GameState:
        return self.run.state

    def act(self, action: Action, text: str, mistake: bool = False) -> bool:
        self.run.text = text
        if self.run.attempt(self.a.company_id, action):
            self.notes.append((text, mistake))
            kind: DecisionKind = "mistake" if mistake else "decision"
            self.run.decisions.append((kind, text, self.run.last_cost, None))
            return True
        return False


# --- Workload (40.3) ---------------------------------------------------------------------------


def month_energy(state: GameState, person_id: int, b: Balance, data: GameData) -> int:
    """automation.owner_energy x the coverage c of the owner's support pool (18.4)."""
    from tst.sim.org.divisions import is_scaleup
    from tst.sim.org.rules import org_view
    from tst.sim.org.scaleup import delegate_energy_factor

    base = b.automation.owner_energy
    company = state.player
    if not is_scaleup(company, b):
        return base
    view = org_view(state, company.id)
    if person_id not in view.unit_of:
        return base
    return int(base * delegate_energy_factor(state, view, person_id, b, data))


def seat_authority(state: GameState, owner: AreaOwner, seat: str, b: Balance) -> Authority:
    """The guardrails an owner runs a seat rule under: the seat's own (its record, else the
    defaults) with the anchors the area was given at (40.6)."""
    from tst.sim.actions.authority import guardrails_for

    current = state.authority(owner.company_id, seat)
    rails = guardrails_for(current, seat, (), state, owner.company_id, b)
    anchors = current.price_anchors if current is not None else ()
    return Authority(owner.company_id, seat, True, rails, owner.since_turn, anchors)


def _seat_right(run: AutoRun, owner: AreaOwner, kind: str | None, seat: str) -> bool:
    """A seat holder in its own seat keeps the seat rule's own draw (stream `delegate`, 24.2);
    anyone else draws from stream `automation`."""
    b, state = run.balance, run.state
    score = owners.true_area_score(state, owner.company_id, owner.area, owner.person_id, b)
    if kind == "seat":
        index = AUTHORITY_SEATS.index(seat)
        from tst.sim.org.executives import acting_seats

        positions = [a.seat for a, _ in acting_seats(state, owner.company_id)]
        index = positions.index(seat) if seat in positions else index
        u = float(
            delegate_draws(run.rng, state.turn, owner.person_id, QUALITY_KEY + index).random()
        )
        return u < decision_quality(score, b.exec_authority.quality)
    return run.draw() < decision_quality(score, b.automation.quality)


def run_area(run: AutoRun, owner: AreaOwner, data: GameData) -> None:
    """One area's rule for one month."""
    from tst.sim.automation import rules
    from tst.sim.org.authority import _cfo, _cmo, _coo, _cpo, _cro, _cto

    b = run.balance
    a = owners.area_def(b, owner.area)
    kind = owners.owner_kind(run.state, owner.company_id, owner.area, owner.person_id, b)
    seat_rule = AREA_SEAT_RULE.get(owner.area)
    if seat_rule is not None:  # an existing area: its seat's rule (24.1), plus 40.6's pricing
        seat = seat_rule
        right = _seat_right(run, owner, kind if a.seat == seat else None, seat)
        s = AutoSeat(run, seat_authority(run.state, owner, seat, b), owner.person_id, right)
        match seat:
            case "cto":
                _cto(s, data)  # type: ignore[arg-type]
            case "cro":
                _cro(s, data)  # type: ignore[arg-type]
            case "cmo":
                history = run.state.company(owner.company_id).mrr_history
                _cmo(s, data, history[-1] if history else 0)  # type: ignore[arg-type]
            case "coo":
                _coo(s, data)  # type: ignore[arg-type]
            case "cfo":
                _cfo(s, data)  # type: ignore[arg-type]
            case "cpo":
                _cpo(s, data)  # type: ignore[arg-type]
        if owner.area == "pricing":
            rules.pricing(run, owner, data)
        return
    rules.RULES[a.rule](run, owner, data)


# --- Phase 2 -----------------------------------------------------------------------------------


def _gone(state: GameState, b: Balance) -> tuple[GameState, list[LogItem]]:
    """Owners who left or lost their seat or role: the area returns to the player (40.1)."""
    logs: list[LogItem] = []
    for o in state.owners_of(state.player.id):
        if owners.valid_owner(state, o, b):
            continue
        state = without_area_owner(state, o.company_id, o.area)
        person = state.person(o.person_id)
        logs.append(
            inbox_item(
                state.turn,
                o.company_id,
                "area_returned",
                name=f"{person.first_name} {person.last_name}",
                area=owners.area_def(b, o.area).label,
            )
        )
    return state, logs


def automation_month(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...], tuple[DelegateAction, ...]]:
    """Phase 2 for every owned area of the player's company, owner by owner (40.3)."""
    company = state.player.id
    if not state.owners_of(company):
        return state, (), (), ()
    from tst.sim.automation.kpis import kpi_values

    state, gone_logs = _gone(state, balance)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = list(gone_logs)
    taken: list[DelegateAction] = []
    current = dict(balances)
    lines: list[AreaDecision] = []
    seq = 0
    by_person: dict[int, list[AreaOwner]] = {}
    for o in state.owners_of(company):
        by_person.setdefault(o.person_id, []).append(o)

    def note(o: AreaOwner, kind: DecisionKind, text: str, cost: int, ref: int | None) -> None:
        nonlocal seq
        lines.append(
            AreaDecision(company, state.turn, seq, o.area, o.person_id, kind, text, cost, ref)
        )
        seq += 1

    for person_id in sorted(by_person):
        areas = sorted(
            by_person[person_id], key=lambda o: (o.priority, owners.area_index(balance, o.area))
        )
        ps = state.person_state(person_id)
        if ps.energy is None:  # an owner acts with an executive's energy (24.1)
            state = with_person_state(
                state, replace(ps, energy=balance.exec_authority.energy_per_month)
            )
        energy = month_energy(state, person_id, balance, data)
        for o in areas:
            cost = owners.area_def(balance, o.area).energy
            if energy < cost:
                note(o, "no_time", "no time this month", 0, None)
                continue
            energy -= cost
            run = AutoRun(
                state=state,
                balances=current,
                rng=rng,
                balance=balance,
                data=data,
                owner=o,
                area_index=owners.area_index(balance, o.area),
            )
            run_area(run, o, data)
            state, current = run.state, run.balances
            entries += run.entries
            logs += run.logs
            taken += run.taken
            for kind, text, c, ref in run.decisions:
                note(o, kind, text, c, ref)
    for o in state.owners_of(company):  # month-start KPIs; the digest compares them (40.4)
        for key, value in kpi_values(state, current, o.area, balance, data).items():
            note(o, KPI, key, value, None)
    state = with_area_decisions(state, lines)
    return state, tuple(entries), tuple(logs), tuple(taken)
