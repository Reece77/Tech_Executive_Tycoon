"""The player's own lithography programme (docs/formulas.md 47.4).

**Starting a stage** (`litho_1`, then `litho_2`, then `litho_3`, each needing the previous to have
succeeded) needs the company at `programme.min_stage` or later with a chip product and a fab, an
active research project in the `lithography` domain whose lab has at least the stage's `staff`
researchers, and a lithography level of at least the stage's `level`. At the start it draws, on
stream equipment key (1, company id, stage index, attempt), three uniforms: the work in months at
reference funding `W = U(months) x work_scale x (1 + overrun)`, the overrun in
`programme.overrun`, and the success draw `u`. All three are hidden.

**Each month** it spends `funding x cost / middle months` (research, 6500) and progresses
`funding x min(1, researchers / staff) x clamp(mean research skill / 10, 0.5, 1.5)` months of
work. When progress reaches W the stage ends: it **works** when `u < p`, `p = clamp(base +
success_funding x (mean funding - 1) + success_skill x (mean skill - 10) / 10, success_range)`, the
mean funding being what it spent over the months it ran against reference; otherwise it **fails**
(the money is gone; a new attempt draws again). A working stage draws (same key, two more
uniforms) its first tools' throughput in `programme.throughput` x ASML's and yield cut in
`programme.yield_cut` points (public from then on), and opens a tool line making the stage's
`tools_per_year` at `tool_cents` each.

**Own tools improve with use:** maturity `m = 1 - exp(-installed tool-months / learn_tool_months)`;
throughput `t0 + (1 - t0) x m`, uptime `uptime_start + (ASML's - uptime_start) x m`, yield cut
`c0 x (1 - m)`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from typing import Final

from tst.sim import dmath
from tst.sim.data_models import Balance, GameData
from tst.sim.equipment import data as ed
from tst.sim.equipment.config import EPS, MONTHS, ProgrammeDef
from tst.sim.equipment.draws import PROGRAMME, gen
from tst.sim.equipment.models import OwnTools, Programme
from tst.sim.ledger import CASH, RESEARCH, LedgerEntry
from tst.sim.org.rules import org_view
from tst.sim.research import levels
from tst.sim.research import projects as rp
from tst.sim.rng import RngFactory
from tst.sim.state import GameState

SKILL_NEUTRAL: Final = 10.0  # tunable-exempt: skills are 1-20, 10 the neutral point (11.3)
SKILL_FACTOR: Final = (0.5, 1.5)  # tunable-exempt: as 21.3's quality clamp
CHIPS_PREFIX: Final = "chips_"  # tunable-exempt: categories.yaml chip categories
START_DRAWS: Final = 3  # tunable-exempt: work, overrun and success, in that order (ADR-0013)


@dataclass(frozen=True, slots=True)
class Staffing:
    researchers: int
    mean_skill: float


def stage_index(data: GameData, stage: str) -> int:
    return [p.key for p in ed.equipment_file(data).programme].index(stage)


def reference_cents(p: ProgrammeDef, balance: Balance) -> float:
    """A stage's reference budget a month: its cost estimate over its middle months."""
    mid = (p.months[0] + p.months[1]) / 2 * balance.equipment.programme.work_scale
    return p.cost / mid


def staffing(state: GameState, company_id: int, balance: Balance, data: GameData) -> Staffing:
    """The lab of the company's active lithography project (none: no researchers)."""
    domain = balance.equipment.programme.domain
    for project in state.active_projects(company_id):
        if project.domain != domain or project.unit_id is None:
            continue
        work = rp.lab(state, org_view(state, company_id), project, balance, data)
        return Staffing(len(work.researchers), work.mean_skill)
    return Staffing(0, 0.0)


def level(state: GameState, company_id: int, balance: Balance, data: GameData) -> float:
    if data.tech is None:
        return 0.0
    return levels.level(state, data, balance, company_id, balance.equipment.programme.domain)


def group_stage(state: GameState, company_id: int) -> int:
    """The company's stage read through its group (M35b): a holding company takes stage 5
    (31.2) while its operating company, which keeps the chip and the fab, stays at 4."""
    from tst.sim.state import ultimate_owner

    top = ultimate_owner(state, company_id)
    return max(state.company(company_id).stage, state.company(top).stage)


def has_chip_and_fab(state: GameState, company_id: int) -> bool:
    chip = any(
        p.category.startswith(CHIPS_PREFIX) and p.status in ("live", "development", "sunset")
        for p in state.company_products(company_id)
    )
    fab = any(f.company_id == company_id for f in state.fabs)
    return chip and fab


def latest(state: GameState, company_id: int, stage: str) -> Programme | None:
    best: Programme | None = None
    for p in state.programmes:
        if (
            p.company_id == company_id
            and p.stage == stage
            and (best is None or p.attempt > best.attempt)
        ):
            best = p
    return best


def succeeded(state: GameState, company_id: int, stage: str) -> bool:
    p = latest(state, company_id, stage)
    return p is not None and p.status == "succeeded"


def why_not(
    state: GameState, company_id: int, stage: str, balance: Balance, data: GameData
) -> str | None:
    """Why the company cannot start `stage` now (None: it can)."""
    ef = ed.equipment_file(data)
    pb = balance.equipment.programme
    try:
        p = ef.stage(stage)
    except KeyError:
        return f"unknown programme stage {stage!r}"
    if group_stage(state, company_id) < pb.min_stage:
        return f"the lithography programme opens at stage {pb.min_stage}"
    if not has_chip_and_fab(state, company_id):
        return "the lithography programme needs a chip product and a fab"
    run = latest(state, company_id, stage)
    if run is not None and run.status in ("running", "succeeded"):
        return f"{p.label} is already {run.status}"
    if p.needs is not None and not succeeded(state, company_id, p.needs):
        return f"{p.label} needs {ef.stage(p.needs).label} first"
    staff = staffing(state, company_id, balance, data)
    if staff.researchers < p.staff:
        return (
            f"{p.label} needs a lithography research project with {p.staff} researchers"
            f" (yours {staff.researchers})"
        )
    have = level(state, company_id, balance, data)
    if have < p.level:
        return f"{p.label} needs lithography level {p.level:.0f} (yours {have:.0f})"
    return None


def start(
    state: GameState,
    company_id: int,
    stage: str,
    funding: float,
    rng: RngFactory,
    balance: Balance,
    data: GameData,
) -> Programme:
    """A new attempt at `stage` with its hidden draws (module docstring)."""
    pb = balance.equipment.programme
    p = ed.equipment_file(data).stage(stage)
    prev = latest(state, company_id, stage)
    attempt = 1 if prev is None else prev.attempt + 1
    g = gen(rng, state.turn, PROGRAMME, company_id, stage_index(data, stage), attempt)
    u_work, u_over, u_success = (float(x) for x in g.random(START_DRAWS))
    overrun = pb.overrun.lo + (pb.overrun.hi - pb.overrun.lo) * u_over
    months = p.months[0] + (p.months[1] - p.months[0]) * u_work
    return Programme(
        company_id=company_id,
        stage=stage,
        attempt=attempt,
        started_turn=state.turn,
        funding=funding,
        work=months * pb.work_scale * (1 + overrun),
        overrun=overrun,
        success_u=u_success,
    )


def success_chance(mean_funding: float, mean_skill: float, balance: Balance) -> float:
    pb = balance.equipment.programme
    p = (
        pb.success_base
        + pb.success_funding * (mean_funding - 1)
        + pb.success_skill * (mean_skill - SKILL_NEUTRAL) / SKILL_NEUTRAL
    )
    return min(pb.success_range.hi, max(pb.success_range.lo, p))


def month(
    state: GameState, rng: RngFactory, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry], list[tuple[Programme, str]]]:
    """Every running stage spends and progresses; those that end report (module docstring)."""
    if not state.programmes:
        return state, [], []
    pb = balance.equipment.programme
    ef = ed.equipment_file(data)
    out: list[Programme] = []
    entries: list[LedgerEntry] = []
    ended: list[tuple[Programme, str]] = []
    lines = list(state.own_tools)
    for prog in state.programmes:
        if prog.status != "running" or not state.company(prog.company_id).alive:
            out.append(prog)
            continue
        p = ef.stage(prog.stage)
        ref = reference_cents(p, balance)
        spend = round(ref * prog.funding)
        staff = staffing(state, prog.company_id, balance, data)
        skill = min(SKILL_FACTOR[1], max(SKILL_FACTOR[0], staff.mean_skill / SKILL_NEUTRAL))
        cover = min(1.0, staff.researchers / p.staff)
        step = prog.funding * cover * skill if staff.researchers else 0.0
        entries.append(
            LedgerEntry.transfer(
                turn=state.turn,
                company_id=prog.company_id,
                memo=f"Lithography programme: {p.label}",
                debit=RESEARCH,
                credit=CASH,
                amount=spend,
            )
        )
        prog = replace(prog, progress=prog.progress + step, spent_cents=prog.spent_cents + spend)
        if prog.progress >= prog.work:
            months_run = state.turn - prog.started_turn + 1
            # money-exact: ratio (funding as a multiple of the reference budget)
            mean_funding = prog.spent_cents / (ref * months_run)
            chance = success_chance(mean_funding, staff.mean_skill or SKILL_NEUTRAL, balance)
            if prog.success_u < chance:
                g = gen(
                    rng,
                    prog.started_turn,
                    PROGRAMME,
                    prog.company_id,
                    stage_index(data, p.key),
                    prog.attempt,
                )
                g.random(START_DRAWS)  # the start's draws, then success's two
                u_t, u_y = (float(x) for x in g.random(2))
                prog = replace(
                    prog,
                    status="succeeded",
                    ended_turn=state.turn,
                    throughput=pb.throughput.lo + (pb.throughput.hi - pb.throughput.lo) * u_t,
                    yield_cut=pb.yield_cut.lo + (pb.yield_cut.hi - pb.yield_cut.lo) * u_y,
                )
                lines.append(OwnTools(prog.company_id, p.key, p.generation))
                ended.append((prog, "succeeded"))
            else:
                prog = replace(prog, status="failed", ended_turn=state.turn)
                ended.append((prog, "failed"))
        out.append(prog)
    return replace(state, programmes=tuple(out), own_tools=tuple(lines)), entries, ended


# --- own tools -----------------------------------------------------------------------------------


def line(state: GameState, company_id: int, generation: str) -> OwnTools | None:
    return next(
        (x for x in state.own_tools if x.company_id == company_id and x.generation == generation),
        None,
    )


def maturity(tools: OwnTools, balance: Balance) -> float:
    return 1.0 - dmath.exp(-tools.tool_months / balance.equipment.programme.learn_tool_months)


def stage_of(state: GameState, tools: OwnTools) -> Programme | None:
    return latest(state, tools.company_id, tools.stage)


def own_throughput(state: GameState, tools: OwnTools, balance: Balance) -> float:
    prog = stage_of(state, tools)
    t0 = prog.throughput if prog is not None else balance.equipment.programme.throughput.lo
    m = maturity(tools, balance)
    return t0 + (1 - t0) * m


def own_uptime(state: GameState, tools: OwnTools, asml: float, balance: Balance) -> float:
    u0 = balance.equipment.programme.uptime_start
    return u0 + (asml - u0) * maturity(tools, balance)


def own_yield_cut(state: GameState, tools: OwnTools, balance: Balance) -> float:
    prog = stage_of(state, tools)
    c0 = prog.yield_cut if prog is not None else 0.0
    return c0 * (1 - maturity(tools, balance))


def produce(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LedgerEntry]]:
    """Each tool line makes `tools_per_year / 12` a month into the company's stock, at
    `tool_cents` each (capitalised as inventory of tools: cash to plant, 1510-style, at once)."""
    if not state.own_tools:
        return state, []
    from tst.sim.equipment import stock

    ef = ed.equipment_file(data)
    entries: list[LedgerEntry] = []
    lines = []
    for x in state.own_tools:
        p = ef.stage(x.stage)
        carry = x.carry + p.tools_per_year / MONTHS
        made = math.floor(carry + EPS)
        if made:
            state = stock.add(state, x.company_id, x.generation, made, "own", made * p.tool_cents)
            entries.append(
                LedgerEntry.transfer(
                    turn=state.turn,
                    company_id=x.company_id,
                    memo=f"Own lithography tools made: {made} {p.label}",
                    debit=stock.TOOLS_ACCOUNT,
                    credit=CASH,
                    amount=made * p.tool_cents,
                )
            )
        lines.append(replace(x, made=x.made + made, carry=carry - made))
    return replace(state, own_tools=tuple(lines)), entries
