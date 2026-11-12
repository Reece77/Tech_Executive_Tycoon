"""How to unlock a greyed-out action (M23c, playtest 5: "Greyed-out stages say what's missing,
not how to get it"). Every disallowed option the Exploration, Mines, Refineries and Fabs screens
show carries a `how`: the next step in the player's words ("drill 12 more holes (20 in total),
then re-estimate"). Read only: each reads the same public rules the engine checks
(tst.sim.exploration.pipeline._stage_problem, tst.sim.fabs.actions.quote) and never a hidden
value."""

from __future__ import annotations

from tst.loader import LoadedData
from tst.sim.calendar import format_turn
from tst.sim.exploration.config import CATEGORIES, LEVELS
from tst.sim.exploration.models import Project
from tst.sim.fabs import market as fm
from tst.sim.fabs.plants import node_label
from tst.sim.state import GameState


def _words(stage: str) -> str:
    return stage.replace("_", "-") if stage in LEVELS else stage.replace("_", " ")


def holes_drilled(state: GameState, project: Project) -> int:
    return sum(1 for h in state.holes if h.project_id == project.id)


def holes_for(category: str, data: LoadedData) -> int:
    """Holes an estimate needs for `category` (inferred, indicated, measured; 34.2)."""
    est = data.balance.exploration.estimate
    return int(getattr(est, category))


def next_category(project: Project) -> str | None:
    """The resource category after the project's current one (None: measured already)."""
    have = project.category
    i = -1 if have is None else CATEGORIES.index(have)
    return CATEGORIES[i + 1] if i + 1 < len(CATEGORIES) else None


def _reach(state: GameState, project: Project, category: str, data: LoadedData) -> str:
    """How to reach a resource category: drill to its hole count, then (re-)estimate."""
    need = holes_for(category, data)
    have = holes_drilled(state, project)
    again = "re-run the resource estimate" if project.category else "run a resource estimate"
    if have < need:
        return f"drill {need - have} more holes ({need} in total), then {again}"
    return f"{again} to upgrade it to {category} ({have} holes drilled is enough)"


def exploration_how(
    state: GameState, project: Project, stage: str, reason: str, data: LoadedData
) -> str:
    """The next step that unlocks `stage` on `project` ('' when it is allowed)."""
    if not reason:
        return ""
    eb = data.balance.exploration
    if not project.is_open:
        return f"none: the project is {project.status}; licence another block to explore again"
    if project.stage is not None:
        due = project.stage_due
        when = f" (reports {format_turn(due)})" if due is not None else ""
        return f"wait for the {_words(project.stage)} to finish{when}, then Continue"
    if project.holes_left:
        return f"wait for the drilling programme to finish ({project.holes_left} holes to go)"
    if project.commodity is None and stage in ("drilling", "estimate", *LEVELS):
        return "run sampling on the block to choose the commodity (the survey's anomaly helps)"
    if stage == "estimate":
        return _reach(state, project, "inferred", data).replace(
            ", then run a resource estimate", ", then run the estimate"
        )
    if stage in LEVELS:
        need = eb.feasibility.min_category[stage]
        return f"{_reach(state, project, need, data)}, then start the {_words(stage)} study"
    if stage == "permitting":
        if project.permit_start is not None:
            return "wait for the permit decision (Continue; its range shows on the project)"
        req = eb.permitting.requires
        have = project.level
        if have is None or LEVELS.index(have) < LEVELS.index(req):
            steps = LEVELS[: LEVELS.index(req) + 1]
            todo = [s for s in steps if have is None or LEVELS.index(s) > LEVELS.index(have)]
            nxt = todo[0]
            need = eb.feasibility.min_category[nxt]
            cat_ok = project.category is not None and CATEGORIES.index(
                project.category
            ) >= CATEGORIES.index(need)
            first = (
                f"start the {_words(nxt)} study"
                if cat_ok
                else f"{_reach(state, project, need, data)}, then start the {_words(nxt)} study"
            )
            rest = " and ".join(_words(s) for s in todo[1:])
            then = f"; then the {rest} study" if rest else ""
            return f"{first}{then}; a permit needs a {_words(req)} study"
    return f"{reason}: finish what is running first"


def mine_quote_how(reason: str) -> str:
    """The next step that makes a permitted project buildable as a mine."""
    if not reason:
        return ""
    if "feasibility" in reason:
        return "finish a feasibility study on the project (Exploration), then build"
    if "already stands" in reason:
        return "none: a mine is already built on it (see Your mines)"
    if "capacity is" in reason:
        return f"choose a capacity inside the range ({reason.split('capacity is ')[-1]})"
    if "permitted" in reason:
        return "win the permit on Exploration first (a definitive study, then apply)"
    return f"fix this first: {reason}"


def stage_how(need: int, have: int, what: str) -> str:
    """A stage gate: what the stage needs and how to grow into it."""
    if have >= need:
        return ""
    return (
        f"reach company stage {need} (you are at {have}): grow revenue and headcount "
        f"(Overview shows the next stage's bar) to open {what}"
    )


def fab_quote_how(
    state: GameState, node: str, need: float, level: float, reason: str | None, data: LoadedData
) -> str:
    """The next step that lets a fab of `node` be ordered."""
    if not reason:
        return ""
    b, d = data.balance, data.game_data
    research = (
        f"raise process research to level {need:.0f} ({need - level:.0f} to go): run a "
        "process project on the Research screen, or license process know-how in"
    )
    if fm.orderable(state, node, b, d):
        return research
    known = fm.public_arrival(state, node, b, d)
    start = known if known is not None else fm.window_start(d, node)
    label = node_label(d, node)
    when = (
        f"wait: {label} can be ordered from {format_turn(start - b.fab.preorder_months)}"
        if start is not None
        else f"wait for {node_label(d, node)} to near volume (see the node timeline)"
    )
    return f"{when}; meanwhile {research}" if level < need else when


def fab_upgrade_how(reason: str | None, live_turn: int | None, state: GameState) -> str:
    if not reason:
        return ""
    if "in production" in reason:
        if live_turn is not None and live_turn > state.turn:
            return f"wait until the fab is in production ({format_turn(live_turn)})"
        return "wait until the fab is in production and not already converting"
    if "no newer node" in reason:
        return "none: this fab already runs the newest node"
    if "research level" in reason:
        return "raise process research on the Research screen to the level shown"
    if "not in volume" in reason:
        return "wait for the newer node to reach volume (see the node timeline)"
    return f"fix this first: {reason}"
