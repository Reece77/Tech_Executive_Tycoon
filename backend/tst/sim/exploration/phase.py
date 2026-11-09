"""Exploration's month (docs/formulas.md 34.2-34.3), in phase 4: desk studies and stages that
are due report; programmes drill their holes; permits face protests and are decided; licences
that ran out lapse. A game with no desk study or project skips it entirely, so a company that
never explores plays exactly as before (34.6 target 6)."""

from __future__ import annotations

import math
from dataclasses import replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.events.models import GameEvent, QueuedEvent
from tst.sim.exploration import pipeline as xp
from tst.sim.exploration.config import LEVELS
from tst.sim.exploration.formulas import half_width_pct
from tst.sim.exploration.geology import block_of
from tst.sim.exploration.models import Project
from tst.sim.ledger import CASH, EXPLORATION, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import format_money
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, life_of, with_life, with_queued

STEPS: Final = ("consult", "benefit", "push_on")  # 34.3: a protest's answers
LINK: Final = xp.LINK
SENSITIVITY_MID: Final = 0.5  # tunable-exempt: protest_rate is quoted at this sensitivity


def exploration_month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, tuple[LedgerEntry, ...], tuple[LogItem, ...]]:
    if not state.desk_studies and not state.projects:
        return state, (), ()
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    for study in state.desk_studies:
        if not study.done and study.done_turn <= state.turn:
            bands = xp.desk_bands(state, study, rng, balance)
            state = xp.with_study(state, replace(study, bands=bands))
            assert data.geology is not None
            logs.append(
                inbox_item(
                    state.turn,
                    study.company_id,
                    "desk_study_done",
                    link_kind=LINK,
                    region=study.region.replace("_", " ").title(),
                    commodity=data.geology.commodity(study.commodity).label,
                    high=bands.count("high"),
                )
            )
    protesting: set[int] = set()
    for project in sorted(state.projects, key=lambda p: p.id):
        if not project.is_open:
            continue
        state, posted, logged = _project_month(
            state, project, rng, balance, data, protesting
        )
        entries += posted
        logs += logged
    return state, tuple(entries), tuple(logs)


def _project_month(
    state: GameState,
    project: Project,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    protesting: set[int],
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    turn, label = state.turn, xp.label_of(project)
    # A licence that ran out lapses (34.2), unless the project is in permitting.
    if turn >= project.expires_turn and project.stage != "permitting":
        project = replace(project, status="lapsed", stage=None, holes_left=0, ended_turn=turn)
        logs.append(_item(turn, project, "licence_lapsed", block=label))
        return xp.with_project(state, project), entries, logs
    stage = project.stage
    if stage in ("survey", "sampling", "estimate", *LEVELS) and (project.stage_due or 0) <= turn:
        project, item = _report(state, project, stage, rng, balance, data)
        project = replace(project, stage=None, stage_start=None, stage_due=None)
        logs.append(item)
    elif stage == "drilling":
        state, project, posted, logged = _drill(state, project, rng, balance, data)
        entries += posted
        logs += logged
    elif stage == "permitting":
        state, project, posted, logged = _permit_month(
            state, project, rng, balance, data, protesting
        )
        entries += posted
        logs += logged
    return xp.with_project(state, project), entries, logs


def _item(turn: int, project: Project, template: str, **params: str | int) -> LogItem:
    return inbox_item(
        turn, project.company_id, template, link_kind=LINK, link_id=project.id, **params
    )


def _pct(hw: float) -> int:
    return round(100 * half_width_pct(hw))


def _report(
    state: GameState,
    project: Project,
    stage: str,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> tuple[Project, LogItem]:
    turn, label = state.turn, xp.label_of(project)
    assert data.geology is not None
    if stage == "survey":
        project = xp.survey_result(state, project, rng, balance, data)
        what = (
            data.geology.commodity(project.commodity).label
            if project.commodity and project.reading != "none"
            else "no commodity"
        )
        item = _item(turn, project, "survey_done", block=label, reading=project.reading or "none",
                     commodity=what)
    elif stage == "sampling":
        project = xp.sample_result(state, project, rng, balance, data)
        assert project.sample_hw is not None
        item = _item(turn, project, "sampling_done", block=label, pct=_pct(project.sample_hw))
    elif stage == "estimate":
        project = xp.estimate_result(state, project, rng, balance, data)
        item = _item(turn, project, "estimate_done", block=label,
                     category=project.category or "no")
    else:
        project = xp.study_result(state, project, stage, rng, balance, data)
        item = _item(
            turn,
            project,
            "study_done",
            block=label,
            level=stage.replace("_", "-"),
            npv=format_money(project.npv_mid_cents or 0),
        )
    return project, item


def _drill(
    state: GameState, project: Project, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, Project, list[LedgerEntry], list[LogItem]]:
    """The month's holes (34.2), then 34.3's minor events: an accident (a fine and a month's
    pause), a bonanza intercept and a dry streak (news)."""
    eb = balance.exploration
    turn, label = state.turn, xp.label_of(project)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    if project.paused_until is not None and turn <= project.paused_until:
        return state, project, entries, logs
    drilled = xp.holes_of(state, project.id)
    k = min(eb.drill.holes_per_month, project.holes_left)
    new = []
    for i in range(k):
        before = xp.running_estimate(
            replace(state, holes=(*state.holes, *new)), project, balance, data
        )
        hole = xp.drill_hole(state, project, len(drilled) + i + 1, rng, balance, data)
        new.append(hole)
        if before is not None and hole.assay >= eb.minor.bonanza_ratio * math.exp(before[0]):
            logs.append(_item(turn, project, "bonanza_intercept", block=label, hole=hole.n))
    cost = sum(h.cost_cents for h in new)
    if cost:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=project.company_id,
                memo=f"Drilling: {len(new)} holes, {label}",
                debit=EXPLORATION,
                credit=CASH,
                amount=cost,
            )
        )
    state = replace(state, holes=(*state.holes, *new))
    left = project.holes_left - len(new)
    project = replace(project, holes_left=left, spent_cents=project.spent_cents + cost)
    est = xp.running_estimate(state, project, balance, data)
    every = xp.holes_of(state, project.id)
    streak = eb.minor.dry_streak
    if est is not None and len(new) and len(every) >= streak + 1:
        recent = every[-streak:]
        mean = math.exp(est[0])
        if all(h.assay < mean / 2 for h in recent) and any(h in new for h in recent[-1:]):
            logs.append(_item(turn, project, "dry_streak", block=label, holes=streak))
    gen = rng.stream(turn, "exploration", xp.MINOR, project.id)
    if left > 0 and float(gen.random()) < eb.minor.accident_rate:
        fine = eb.minor.accident_fine_cents
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=project.company_id,
                memo=f"Drilling accident: a fine, {label}",
                debit=EXPLORATION,
                credit=CASH,
                amount=fine,
            )
        )
        project = replace(project, paused_until=turn + 1, spent_cents=project.spent_cents + fine)
        logs.append(_item(turn, project, "drilling_accident", block=label, fine=format_money(fine)))
    if left == 0:
        project = replace(project, stage=None, stage_start=None, paused_until=None)
        assert est is not None
        logs.append(
            _item(turn, project, "drilling_done", block=label, holes=len(every), pct=_pct(est[1]))
        )
    return state, project, entries, logs


def _permit_month(
    state: GameState,
    project: Project,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
    protesting: set[int],
) -> tuple[GameState, Project, list[LedgerEntry], list[LogItem]]:
    """34.3: while a permit is pending, a protest may come (a critical event, one a company a
    month); an earlier push on may bring an injunction; then the decision, once no protest is
    open: a permit, or a refusal with chance from the region and the block's difficulty."""
    assert data.geology is not None
    pb = balance.exploration.permitting
    turn, label = state.turn, xp.label_of(project)
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    block = block_of(state, project.region, project.block)
    assert block is not None and project.hidden_due_turn is not None
    if project.protest_turn is not None:
        return state, project, entries, logs  # waiting for the answer
    gen = rng.stream(turn, "exploration", xp.PROTEST, project.id)
    u_protest, u_kind = (float(x) for x in gen.random(2))
    chance = pb.protest_rate * block.true_sensitivity / SENSITIVITY_MID
    if project.benefit:
        chance *= 1 - pb.benefit_odds
    if project.company_id not in protesting and u_protest < chance:
        protesting.add(project.company_id)
        template = xp.EVENT_TEMPLATES[0 if u_kind < 0.5 else 1]
        qid, ids = state.next_ids.take("queued")
        state = with_queued(
            replace(state, next_ids=ids),
            QueuedEvent(
                id=qid,
                company_id=project.company_id,
                template_id=template,
                due_turn=turn + 1,
                source_event_id=None,
            ),
        )
        project = replace(project, protest_turn=turn + 1, protests=project.protests + 1)
        logs.append(_item(turn, project, "protest_started", block=label))
        return state, project, entries, logs
    if turn >= project.hidden_due_turn:
        u = float(rng.stream(turn, "exploration", xp.PERMIT, project.id, 1).random())
        refusal = data.geology.regions[project.region].refusal * block.true_difficulty
        if project.benefit:
            refusal *= 1 - pb.benefit_odds
        refusal = min(0.95, refusal + pb.refusal_on_push * project.pushes)
        granted = u >= refusal
        project = replace(
            project,
            status="permitted" if granted else "refused",
            stage=None,
            permit_turn=turn,
            ended_turn=None if granted else turn,
        )
        logs.append(_item(turn, project, "permit_granted" if granted else "permit_refused",
                          block=label))
    return state, project, entries, logs


def _project_for_event(state: GameState, event: GameEvent) -> Project | None:
    for p in sorted(state.projects, key=lambda p: p.id):
        if p.company_id == event.company_id and p.protest_turn == event.turn and p.is_open:
            return p
    return None


def exploration_step(
    state: GameState,
    event: GameEvent,
    step: str,
    balance: Balance,
    data: GameData,
) -> tuple[GameState, list[LedgerEntry], list[LogItem]]:
    """A protest's answer (34.3), applied by the engine: consult (money and months), a
    benefit agreement (money; better odds and fewer protests), or push on (persona Ruthless
    +5, M24's hook; a chance of an injunction: months and legal costs; worse odds)."""
    project = _project_for_event(state, event)
    if project is None or project.hidden_due_turn is None:
        return state, [], []
    pb = balance.exploration.permitting
    entries: list[LedgerEntry] = []
    logs: list[LogItem] = []
    turn, due = state.turn, project.hidden_due_turn
    cost = 0
    if step == "consult":
        cost = pb.consult_cents
        due += pb.consult_months
    elif step == "benefit":
        cost = pb.benefit_cents
        project = replace(project, benefit=True)
    elif step == "push_on":
        project = replace(project, pushes=project.pushes + 1)
        founder = state.founder_of(state.player.id)
        if founder is not None:
            from tst.sim.founder.persona import raise_trait
            from tst.sim.founder.stress import new_life

            life = life_of(state, founder.id) or new_life(founder.id, balance)
            life = raise_trait(
                life, "ruthless", pb.push_ruthless, "pushed on through a protest", turn, balance
            )
            state = with_life(state, life)
        rng = RngFactory(state.save_meta.master_seed)  # the save's own streams (ADR-0002)
        u = float(rng.stream(turn, "exploration", xp.PROTEST, project.id, 1).random())
        if u < pb.push_legal:
            cost = pb.push_legal_cents
            due += pb.push_delay_months
            logs.append(_item(turn, project, "injunction", block=xp.label_of(project)))
    if cost:
        entries.append(
            LedgerEntry.transfer(
                turn=turn,
                company_id=project.company_id,
                memo=f"Community and permits ({step.replace('_', ' ')}): {xp.label_of(project)}",
                debit=EXPLORATION,
                credit=CASH,
                amount=cost,
            )
        )
    project = replace(
        project, protest_turn=None, hidden_due_turn=due, spent_cents=project.spent_cents + cost
    )
    return xp.with_project(state, project), entries, logs
