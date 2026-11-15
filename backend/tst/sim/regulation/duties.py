"""Duties (docs/formulas.md 48.2; ADR-0021 3), from `regulation.start`.

A duty binds a company in a regulator's reach: from a designation (the regime's duties, from its
`comply_months` after the designation), a ruling's behavioural remedy, or a settlement's
commitment. When it starts it changes each platform the company's group owns in the regulator's
region:

- side_loading, anti_steering, alt_payments and fee_cap add a dated row to the platform's
  `regulated` rows (read by M31's `schedule` and `rule_active`): other stores may serve its users;
  links to pay outside are allowed; an alternative payment path at the standard rate less
  `regulation.alt_discount`; a capped standard rate. A row platforms.yaml already has for that
  part and kind is not added twice.
- no_self_preferencing sets self-preferencing off, and anti_steering sets the owner's
  anti-steering rule off.
- interoperability and data_portability change no platform rule (their cost is compliance work).

Every duty costs `regulation.compliance_cents` a year, posted monthly (6900 against cash).

**Non-compliance.** The player may turn a forbidden setting back on (self-preferencing while a
no_self_preferencing duty binds it, or the anti-steering rule while an anti_steering duty does):
that raises an investigation's chance and its fine (48.3). Rivals always comply.

History's designations of in-game companies (Apple's under the DMA, for one) bind them as duties
from `regulation.start`, dated as the data has them, so their compliance costs start in 2026 and
nothing posts before (48.5 target 1)."""

from __future__ import annotations

from dataclasses import replace
from typing import Final

from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import Balance, GameData
from tst.sim.ledger import CASH, GENERAL_ADMIN, LedgerEntry
from tst.sim.log import LogItem, inbox_item
from tst.sim.platforms import data as pdata
from tst.sim.platforms.models import Platform
from tst.sim.regulation import data as rdata
from tst.sim.regulation.config import DutyKind, RegulatorDef
from tst.sim.regulation.models import Duty, DutySource
from tst.sim.state import GameState, owner_of

RULE_KIND: Final[dict[str, str]] = {  # a duty's row kind in platforms' `regulated`
    "side_loading": "side_loading",
    "anti_steering": "anti_steering_banned",
    "alt_payments": "alt_payments",
    "fee_cap": "fee_cap",
}
LINK: Final = "regulation"


def duties_of(state: GameState, company_id: int, regulator: str | None = None) -> list[Duty]:
    return [
        d
        for d in state.duties
        if d.company_id == company_id and (regulator is None or d.regulator == regulator)
    ]


def binding(state: GameState, company_id: int, regulator: str, kind: str) -> bool:
    return any(
        d.kind == kind and d.from_turn <= state.turn
        for d in duties_of(state, company_id, regulator)
    )


def platforms_in(state: GameState, company_id: int, region: str) -> list[Platform]:
    """Device platforms the company's group owns that serve the region."""
    owner = owner_of(state, company_id)
    return [
        p
        for p in state.platforms
        if p.owner_id is not None
        and owner_of(state, p.owner_id) == owner
        and region in p.regions
        and (p.ended_turn is None or p.ended_turn > state.turn)
    ]


def breaches(state: GameState, company_id: int, regulator: RegulatorDef) -> list[DutyKind]:
    """The duties the company breaches in the regulator's reach (48.2's non-compliance)."""
    out: list[DutyKind] = []
    owned = platforms_in(state, company_id, regulator.region)
    if binding(state, company_id, regulator.key, "no_self_preferencing") and any(
        p.self_pref != "off" for p in owned
    ):
        out.append("no_self_preferencing")
    if binding(state, company_id, regulator.key, "anti_steering") and any(
        p.anti_steering and not p.historical for p in owned
    ):
        out.append("anti_steering")
    return out


def noncompliant(state: GameState, company_id: int, regulator: RegulatorDef) -> bool:
    return bool(breaches(state, company_id, regulator))


def next_duty_id(state: GameState) -> int:
    return max([0, *(d.id for d in state.duties)]) + 1


def add_duty(
    state: GameState,
    company_id: int,
    regulator: str,
    kind: DutyKind,
    from_turn: int,
    source: DutySource,
    data: GameData,
    balance: Balance,
    *,
    regime: str | None = None,
    case_id: int | None = None,
) -> GameState:
    """A new duty (none if the same kind already binds the company there)."""
    if any(d.kind == kind for d in duties_of(state, company_id, regulator)):
        return state
    duty = Duty(
        next_duty_id(state), company_id, regulator, kind, from_turn, source, regime, case_id
    )
    state = replace(state, duties=(*state.duties, duty))
    if from_turn <= state.turn:
        state = apply(state, duty, balance, data)
    return state


def apply(state: GameState, duty: Duty, balance: Balance, data: GameData) -> GameState:
    """A duty's effect on the company's platforms in the regulator's region (module docstring)."""
    reg = rdata.file(data).regulator(duty.regulator)
    part = reg.part or ""
    changed = []
    for p in platforms_in(state, duty.company_id, reg.region):
        new = p
        if duty.kind == "no_self_preferencing":
            new = replace(new, self_pref="off")
        if duty.kind == "anti_steering":
            new = replace(new, anti_steering=False)
        kind = RULE_KIND.get(duty.kind)
        if kind is not None and not _has_row(new, reg.region, part, kind, data, state.turn):
            rate = 0.0
            if duty.kind == "alt_payments":
                sched = pdata.schedule(new, reg.region, state.turn, balance, data)
                rate = max(0.0, sched.standard - balance.regulation.alt_discount)
            elif duty.kind == "fee_cap":
                rate = balance.regulation.fee_cap
            row = (reg.region, part, kind, max(duty.from_turn, state.turn), rate)
            new = replace(new, regulated=(*new.regulated, row))
        if new != p:
            changed.append(new)
    if not changed:
        return state
    by_id = {p.id: p for p in changed}
    return replace(state, platforms=tuple(by_id.get(p.id, p) for p in state.platforms))


def _has_row(p: Platform, region: str, part: str, kind: str, data: GameData, turn: int) -> bool:
    if any(r[0] == region and r[1] == part and r[2] == kind for r in p.regulated):
        return True
    if not p.historical or data.platforms is None:
        return False
    if kind == "alt_payments":
        return any(
            rule.platform == p.key and rule.region == region and rule.part == (part or None)
            for rule in data.platforms.fee_rules
            if rule.kind == "regulated"
        )
    return any(
        r.kind == kind and r.region == region and r.part == (part or None) and p.key in r.platforms
        for r in data.platforms.rules
    )


def start_month(
    state: GameState, balance: Balance, data: GameData
) -> tuple[GameState, list[LogItem]]:
    """Duties whose month has come take effect; history's designations of in-game companies
    become duties (dated as the data has them) the first month the model runs."""
    logs: list[LogItem] = []
    for d in rdata.history_designations(state, data, state.turn):
        if d.company_id is None:
            continue
        regime = rdata.file(data).regime(d.regime)
        start = d.from_turn + regime.comply_months
        for kind in regime.duties:
            before = len(state.duties)
            state = add_duty(
                state, d.company_id, regime.regulator, kind, start, "designation", data, balance,
                regime=regime.key,
            )  # fmt: skip
            if len(state.duties) == before:
                continue
    for g in state.designations:
        regime = rdata.file(data).regime(g.regime)
        if g.duties_from > state.turn:
            continue
        for kind in regime.duties:
            state = add_duty(
                state, g.company_id, regime.regulator, kind, g.duties_from, "designation", data,
                balance, regime=regime.key,
            )  # fmt: skip
    for duty in state.duties:
        if duty.from_turn == state.turn:
            state = apply(state, duty, balance, data)
            if duty.company_id == state.player.id:
                reg = rdata.file(data).regulator(duty.regulator)
                logs.append(
                    inbox_item(
                        state.turn,
                        duty.company_id,
                        "regulation_duty",
                        link_kind=LINK,
                        regulator=reg.name,
                        duty=duty.kind.replace("_", " "),
                    )
                )
    return state, logs


def compliance_entries(state: GameState, balance: Balance) -> list[LedgerEntry]:
    """A month of compliance work for every company with books and duties in force (48.2)."""
    books = {c.id for c in state.ledger_companies()}
    counts: dict[int, int] = {}
    for d in state.duties:
        if d.from_turn <= state.turn and d.company_id in books:
            counts[d.company_id] = counts.get(d.company_id, 0) + 1
    monthly = balance.regulation.compliance_cents // MONTHS_PER_YEAR
    return [
        LedgerEntry.transfer(
            turn=state.turn,
            company_id=cid,
            memo=f"Regulatory compliance ({n} duties)",
            debit=GENERAL_ADMIN,
            credit=CASH,
            amount=n * monthly,
        )
        for cid, n in sorted(counts.items())
        if n * monthly > 0
    ]
