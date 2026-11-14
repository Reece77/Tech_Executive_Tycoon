"""The monthly digest (docs/formulas.md 40.4).

At month end each company with at least one automated area gets one inbox item of kind
`digest`: for each area, the owner, what they did (a count and up to three lines), money
committed against the limit, visible mistakes, proposals waiting, the area's KPIs against last
month and any target, and "no time" or "over budget" notes; then up to three "worth your
attention" lines across areas. The opening paragraph is a template the LLM may reword from
these facts only (16.8). Nothing here is a true score, a probability or a draw (40.11).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tst.sim.automation import owners
from tst.sim.automation.kpis import LABELS, MONEY, kpi_target
from tst.sim.automation.models import AreaDecision
from tst.sim.calendar import format_turn
from tst.sim.data_models import Balance, GameData
from tst.sim.log import LogItem, inbox_item
from tst.sim.money import format_money
from tst.sim.state import GameState

DIGEST = "digest"
DID = frozenset({"decision", "mistake", "event"})
QUARTER = 3  # tunable-exempt: calendar
NOTE_WEIGHT = 0.5  # tunable-exempt: a "no time" note ranks as half a KPI's full miss


@dataclass(frozen=True, slots=True)
class KpiLine:
    key: str
    label: str
    now: int
    last: int | None
    target: int | None
    money: bool


@dataclass(frozen=True, slots=True)
class AreaLine:
    area: str
    label: str
    person_id: int
    owner: str  # "Name (Role)"
    did: int
    lines: tuple[str, ...]
    committed_cents: int
    limit_cents: int
    mistakes: tuple[str, ...]
    proposals: tuple[int, ...]  # proposal or pitch ids waiting
    kpis: tuple[KpiLine, ...]
    notes: tuple[str, ...]  # "no time this month", "over this month's budget"


@dataclass(frozen=True, slots=True)
class Digest:
    turn: int
    company_id: int
    opening: str
    areas: tuple[AreaLine, ...]
    attention: tuple[str, ...]
    quarter_reports: bool


def owner_name(state: GameState, person_id: int, data: GameData) -> str:
    """ "Name (CTO)" for a seat holder, else "Name (Role)" (40.8's header)."""
    from tst.sim.data_models import AUTHORITY_SEATS

    person = state.person(person_id)
    e = state.employment_of(person_id)
    seat = next(
        (
            s
            for s in AUTHORITY_SEATS
            if e is not None and state.seat_holder(e.company_id, s) == person_id
        ),
        None,
    )
    if seat is not None:
        role = seat.upper()
    elif e is not None and e.role in {r.key for r in data.roles}:
        role = data.role(e.role).label
    else:
        role = "former employee"
    return f"{person.first_name} {person.last_name} ({role})"


def _value(k: KpiLine, v: int) -> str:
    return format_money(v) if k.money else f"{v:,}"


def kpi_text(k: KpiLine) -> str:
    text = f"{k.label}: {_value(k, k.now)}"
    if k.last is not None and k.last != k.now:
        text += f" (was {_value(k, k.last)})"
    if k.target is not None:
        text += f", target {_value(k, k.target)}"
    return text


def build(state: GameState, turn: int, b: Balance, data: GameData) -> Digest | None:
    """The digest for the player's company and month `turn`, from the month's records."""
    company = state.player.id
    owned = state.owners_of(company)
    if not owned:
        return None
    month = [d for d in state.area_decisions if d.company_id == company and d.turn == turn]
    before = [d for d in state.area_decisions if d.company_id == company and d.turn == turn - 1]
    pending = {p.id for p in state.pending_proposals(company)} | {
        p.id for p in state.pending_pitches(company)
    }
    areas: list[AreaLine] = []
    attention: list[tuple[float, str]] = []
    n = b.automation.digest_lines
    for o in sorted(owned, key=lambda o: owners.area_index(b, o.area)):
        mine = [d for d in month if d.area == o.area]
        acted = [d for d in mine if d.kind in DID]
        label = owners.area_def(b, o.area).label
        kpis = tuple(_kpis(state, company, o.area, mine, before, b))
        waiting = tuple(d.ref_id for d in mine if d.kind == "proposal" and d.ref_id in pending)
        line = AreaLine(
            area=o.area,
            label=label,
            person_id=o.person_id,
            owner=owner_name(state, o.person_id, data),
            did=len(acted),
            lines=tuple(d.text for d in acted[:n]),
            committed_cents=sum(d.commitment_cents for d in acted),
            limit_cents=o.limit_cents,
            mistakes=tuple(d.text for d in mine if d.kind == "mistake"),
            proposals=tuple(x for x in waiting if x is not None),
            kpis=kpis,
            notes=tuple(sorted({d.text for d in mine if d.kind in ("no_time", "over_budget")})),
        )
        areas.append(line)
        for d in mine:
            if d.kind == "proposal" and d.ref_id in pending:
                share = d.commitment_cents / max(o.limit_cents, 1)
                attention.append(
                    (max(share, 1.0), f"{label}: {owner_name(state, o.person_id, data)} {d.text}")
                )
        for k in kpis:
            if k.target is not None and k.target > 0 and k.now < k.target:
                attention.append(((k.target - k.now) / k.target, f"{label}: {kpi_text(k)}"))
            elif k.last not in (None, 0) and k.last is not None:
                move = abs(k.now - k.last) / abs(k.last)
                if move > 0:
                    attention.append((move, f"{label}: {kpi_text(k)}"))
        for note in line.notes:
            attention.append((NOTE_WEIGHT, f"{label}: {line.owner} had {note}"))
    attention.sort(key=lambda t: -t[0])
    did = sum(a.did for a in areas)
    asks = sum(len(a.proposals) for a in areas)
    opening = (
        f"Your team ran {len(areas)} area{'s' if len(areas) != 1 else ''} this month and "
        f"made {did} decision{'s' if did != 1 else ''}"
        + (f"; {asks} proposal{'s' if asks != 1 else ''} wait for you." if asks else ".")
    )
    return Digest(
        turn=turn,
        company_id=company,
        opening=opening,
        areas=tuple(areas),
        attention=tuple(text for _, text in attention[:n]),
        quarter_reports=turn % QUARTER == QUARTER - 1,
    )


def _kpis(
    state: GameState,
    company: int,
    area: str,
    mine: list[AreaDecision],
    before: list[AreaDecision],
    b: Balance,
) -> list[KpiLine]:
    last = {d.text: d.commitment_cents for d in before if d.area == area and d.kind == "kpi"}
    out = []
    for d in mine:
        if d.kind != "kpi":
            continue
        out.append(
            KpiLine(
                key=d.text,
                label=LABELS.get(d.text, d.text),
                now=d.commitment_cents,
                last=last.get(d.text),
                target=kpi_target(state, company, d.text, b),
                money=d.text in MONEY,
            )
        )
    return out


def body_text(d: Digest) -> str:
    """The digest's text: the opening paragraph, then each area and the attention lines."""
    parts = [d.opening]
    if d.attention:
        parts.append("Worth your attention:\n" + "\n".join(f"- {a}" for a in d.attention))
    for a in d.areas:
        head = f"{a.label}: run by {a.owner}. {a.did} decision{'s' if a.did != 1 else ''}"
        limit = format_money(a.limit_cents)
        head += f", {format_money(a.committed_cents)} committed (limit {limit} each)."
        rows = [f"- {line}" for line in a.lines]
        rows += [f"- Misstep: {m}" for m in a.mistakes]
        rows += [f"- {len(a.proposals)} proposal(s) waiting"] if a.proposals else []
        rows += [f"- {kpi_text(k)}" for k in a.kpis]
        rows += [f"- {note.capitalize()}" for note in a.notes]
        parts.append("\n".join([head, *rows]))
    if d.quarter_reports:
        parts.append("Your executives' quarterly reports are in the inbox.")
    return "\n\n".join(parts)


def facts(d: Digest) -> list[str]:
    """The engine facts the LLM may write the opening from (16.8; never a hidden value)."""
    out = [d.opening, *d.attention]
    for a in d.areas:
        out.append(f"{a.label}: {a.owner} made {a.did} decisions")
        out += list(a.lines) + [f"Misstep: {m}" for m in a.mistakes]
    return out


# Inbox templates an area produces (40.4): while the area is automated they are filed with the
# digest (`in_digest`) instead of the inbox's default view. Proposals, pitches waiting, critical
# and major events, board, earnings and press items are never here.
AREA_TEMPLATES: dict[str, str] = {
    "candidates_arrived": "hiring",
    "offer_accepted": "hiring",
    "offer_declined": "hiring",
    "plan_activity": "hiring",
    "plan_filled": "hiring",
    "search_closed": "hiring",
    "sales_capacity_limited": "pricing",
    "region_live": "regions",
    "exec_decisions": "",  # an executive's monthly decisions: filed when any area is automated
}


def file_with_digest(state: GameState, items: tuple[LogItem, ...]) -> tuple[LogItem, ...]:
    """Flag the month's items that automated areas produced (40.4). No owners: unchanged."""
    company = state.player.id
    owned = {o.area for o in state.owners_of(company)}
    if not owned:
        return items
    out = []
    for i in items:
        area = AREA_TEMPLATES.get(i.template or "-") if i.company_id == company else None
        if area is not None and not i.in_digest and (area in owned or area == ""):
            i = replace(i, in_digest=True)
        out.append(i)
    return tuple(out)


def digest_item(state: GameState, turn: int, b: Balance, data: GameData) -> LogItem | None:
    """Phase 12: the month's digest item (minor; it never blocks Continue)."""
    d = build(state, turn, b, data)
    if d is None:
        return None
    return inbox_item(
        turn,
        d.company_id,
        DIGEST,
        link_kind="automation",
        month=format_turn(turn),
        body=body_text(d),
    )
