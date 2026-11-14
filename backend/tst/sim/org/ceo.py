"""Chair and CEO (docs/formulas.md 25.6, M13).

The appointed CEO is a super-delegate (ADR-0015, 24): each month in phase 2, after the seat
holders with authority, the CEO runs every function in its scopes that no seat holder with
authority covers: the five seats' rules (24.1) plus product priorities (launching ready
products). It acts through the player's own actions, as the actor, with its own energy, and
only through CEO_ACTIONS: capital, guidance, strategy and appointments stay with the Chair
(CHAIR_ONLY). Prices move only within ceo.price_band_pct of the player's last price, and hiring
plans stop at the seats' headcount guardrails.

Decision quality follows 24.2 with the CEO's true score (ceo.weights; never shown): the right
rule with probability clamp(0.55 + 0.03 s, 0.6, 0.98). Draws come from stream `delegate`
keyed (CEO person id, CEO_KEY + scope index).

The Chair can override a decision (energy ceo.override_energy): its `undo` action is applied
and the CEO's price anchor follows the Chair's price.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import replace
from typing import Final

from tst.sim.actions import Action, LaunchProduct
from tst.sim.actions.authority import guardrails_for
from tst.sim.actions.products import launch_problems
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import AccountCode, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.markets_public.config import CEO_SCOPES
from tst.sim.markets_public.formulas import ceo_score
from tst.sim.markets_public.models import Ceo, CeoDecision
from tst.sim.money import Cents
from tst.sim.org.authority import _cfo, _cmo, _coo, _cro, _cto, _Seat
from tst.sim.org.ceo_rules import Undo
from tst.sim.org.delegates import DelegateAction, DelegateRun, delegate_draws
from tst.sim.org.executives import acting_seats
from tst.sim.org.formulas import decision_quality
from tst.sim.org.models import Authority, GuardValue
from tst.sim.rng import RngFactory
from tst.sim.state import (
    GameState,
    ceo_of,
    player_companies,
    with_ceo,
    with_ceo_decision,
    with_person_state,
)

CEO_KEY: Final = 2_000_000  # tunable-exempt: delegate-stream key offset for the CEO's draws
# What a CEO may do (25.6): operating decisions only.
CEO_ACTIONS: Final = frozenset(
    {"create_plan", "close_plan", "move_person", "set_price", "set_marketing", "launch_product"}
)
# What only the Chair may do (25.6): capital, guidance, strategy and appointments.
CHAIR_ONLY: Final = frozenset(
    {
        "raise_safe",
        "start_round",
        "accept_term_sheet",
        "accept_bridge",
        "name_nominee",
        "take_loan",
        "repay_loan",
        "hire_banks",
        "set_guidance",
        "buyback",
        "declare_dividend",
        "secondary_offering",
        "appoint_ceo",
        "dismiss_ceo",
        "set_ceo_authority",
        "override_ceo",
        "appoint_executive",
        "remove_executive",
        "set_authority",
        "answer_proposal",
        "answer_pitch",  # M13b (27.1): the Chair answers pitches, the CEO's included
        "set_pitch_policy",
        "build_facility",
        "sell_facility",
        "sign_contract",
        "start_project",
        "license_in",
        "license_out",
    }
)


class _CeoSeat(_Seat):
    """A seat's month run by the CEO: only CEO_ACTIONS, each remembered with its undo."""

    def __init__(self, run: DelegateRun, a: Authority, holder: int, right: bool) -> None:
        super().__init__(run, a, holder, right)
        self.undo: dict[int, Undo] = {}

    def act(self, action: Action, text: str, mistake: bool = False) -> bool:
        if action.kind not in CEO_ACTIONS:
            return False
        undo = undo_of(self.run.state, action)
        if not super().act(action, text, mistake):
            return False
        if undo:
            self.undo[len(self.notes) - 1] = undo
        return True


def undo_of(state: GameState, action: Action) -> Undo:
    """The action and fields that reverse `action`, read before it is applied; () when it
    cannot be reversed (a launch)."""
    match action.kind:
        case "set_price":
            product = state.product(action.product_id)
            seg = state.product_segment(action.product_id, action.segment)
            if product is None or seg is None or seg.price_cents is None:
                return ()
            return (
                ("kind", "set_price"),
                ("price_cents", seg.price_cents),
                ("product_id", product.id),
                ("segment", seg.segment),
            )
        case "set_marketing":
            product = state.product(action.product_id)
            if product is None:
                return ()
            return (
                ("budget_cents", product.marketing_budget_cents),
                ("kind", "set_marketing"),
                ("product_id", product.id),
            )
        case "move_person":
            e = state.employment_of(action.person_id)
            if e is None:
                return ()
            back: int | str = e.unit_id if e.unit_id is not None else "root"
            return (("kind", "move_person"), ("person_id", e.person_id), ("unit_id", back))
        case "create_plan":
            return (("kind", "close_plan"), ("plan_id", state.next_ids.plan))
    return ()


def _authority(state: GameState, ceo: Ceo, seat: str, balance: Balance) -> Authority:
    """The CEO runs a seat's function under that seat's guardrails (the player's, else the
    defaults), with the CEO's price band and anchors (25.6)."""
    current = state.authority(ceo.company_id, seat)
    rails: dict[str, GuardValue] = dict(
        guardrails_for(current, seat, (), state, ceo.company_id, balance)
    )
    if "price_band_pct" in rails:
        rails["price_band_pct"] = balance.ceo.price_band_pct
    if "max_salary_ratio_bp" in rails:
        rails["max_salary_ratio_bp"] = min(
            int(rails["max_salary_ratio_bp"]),  # type: ignore[arg-type]
            balance.ceo.max_salary_ratio_bp,
        )
    return Authority(
        ceo.company_id,
        seat,
        True,
        tuple(sorted(rails.items())),
        ceo.since_turn,
        ceo.price_anchors,
    )


def _products(seat: _CeoSeat, balance: Balance, data: GameData) -> None:
    """Product priorities (25.6): launch every product that is ready; a misstep waits a
    month (24.2)."""
    state = seat.state
    if not seat.right:
        return
    for product in state.company_products(seat.a.company_id):
        if product.status != "in_development":
            continue
        if launch_problems(state, product, balance, data):
            continue
        seat.act(LaunchProduct(seat.holder, product.id), f"launched {product.name}")


def run_ceo(
    state: GameState,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    balances: Mapping[tuple[int, AccountCode], Cents],
    *,
    at_controls: bool = False,
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...], tuple[DelegateAction, ...]]:
    """Phase 2, after the executives with authority (25.6); then the CEO's quarterly pitch
    across the functions it runs (27.1, M13b)."""
    from tst.sim.automation.config import SEAT_AREA
    from tst.sim.ledger import CASH, account_balance
    from tst.sim.org.pitches import CEO_SCOPE_SEAT, SEAT_KINDS, pitch_month
    from tst.sim.org.reports import EXEC_REPORT, ceo_letter, is_report_month

    if not state.ceos:
        return state, (), (), ()
    run = DelegateRun(state=state, balances=dict(balances), rng=rng, balance=balance, data=data)
    for company in player_companies(state):
        ceo = ceo_of(run.state, company.id)
        if ceo is None:
            continue
        e = run.state.employment_of(ceo.person_id)
        if e is None or e.company_id != company.id or e.status != "active":
            run.state = with_ceo(run.state, replace(ceo, ended_turn=state.turn, end_reason="left"))
            person = run.state.person(ceo.person_id)
            name = f"{person.first_name} {person.last_name}"
            run.logs.append(inbox_item(state.turn, company.id, "ceo_left", name=name))
            continue
        ps = run.state.person_state(ceo.person_id)
        if ps.energy is None:
            energy = balance.exec_authority.energy_per_month
            run.state = with_person_state(run.state, replace(ps, energy=energy))
        skills = run.state.person(ceo.person_id).skills.as_dict()
        quality = decision_quality(
            ceo_score(skills, balance.ceo.weights), balance.exec_authority.quality
        )
        covered = {a.seat for a, _ in acting_seats(run.state, company.id)}
        if "cpo" in covered:  # a CPO with authority runs product priorities (M13b, 27.1)
            covered.add("products")
        for scope_seat, area in SEAT_AREA.items():  # M27a (40.1): owned areas run in automation
            if run.state.area_owner(company.id, area) is not None:
                covered.add("products" if scope_seat == "cpo" else scope_seat)
        lines: list[str] = []
        for index, scope in enumerate(CEO_SCOPES):
            if scope not in ceo.scopes or scope in covered:
                continue
            u = float(delegate_draws(rng, state.turn, ceo.person_id, CEO_KEY + index).random())
            seat_name = "cto" if scope == "products" else scope
            authority = _authority(run.state, ceo, seat_name, balance)
            seat = _CeoSeat(run, authority, ceo.person_id, u < quality)
            match scope:
                case "cto":
                    _cto(seat, data)
                case "cro":
                    _cro(seat, data)
                case "cmo":
                    history = run.state.company(company.id).mrr_history
                    _cmo(seat, data, history[-1] if history else 0)
                case "coo":
                    _coo(seat, data)
                case "cfo":
                    _cfo(seat, data)
                case "products":
                    _products(seat, balance, data)
            for i, (text, mistake) in enumerate(seat.notes):
                did, ids = run.state.next_ids.take("ceo_decision")
                run.state = with_ceo_decision(
                    replace(run.state, next_ids=ids),
                    CeoDecision(
                        did,
                        company.id,
                        ceo.person_id,
                        state.turn,
                        scope,
                        text,
                        mistake,
                        seat.undo.get(i, ()),
                    ),
                )
                lines.append(text + (" (a misstep)" if mistake else ""))
        if lines:
            person = run.state.person(ceo.person_id)
            summary = f"{person.first_name} {person.last_name}: " + "; ".join(lines) + "."
            run.logs.append(inbox_item(state.turn, company.id, "ceo_decisions", summary=summary))
        kinds = tuple(
            k
            for scope in CEO_SCOPES
            if scope in ceo.scopes and scope not in covered
            for k in SEAT_KINDS.get(CEO_SCOPE_SEAT.get(scope, scope), ())
        )
        score = ceo_score(skills, balance.ceo.weights)  # true, never shown
        pitch_month(run, company.id, "ceo", ceo.person_id, kinds, score, at_controls)
        if is_report_month(state.turn, balance):  # the letter to the Chair (27.2, M13b)
            person = run.state.person(ceo.person_id)
            cash = account_balance(run.balances, company.id, CASH)
            run.logs.append(
                inbox_item(
                    state.turn,
                    company.id,
                    EXEC_REPORT,
                    link_kind="person",
                    link_id=ceo.person_id,
                    seat="CEO",
                    name=f"{person.first_name} {person.last_name}",
                    report=ceo_letter(run.state, ceo.person_id, ceo.scopes, cash, balance, data),
                )
            )
    keep = state.turn - balance.ceo.memory_months
    run.state = replace(
        run.state, ceo_decisions=tuple(d for d in run.state.ceo_decisions if d.turn > keep)
    )
    return run.state, tuple(run.entries), tuple(run.logs), tuple(run.taken)
