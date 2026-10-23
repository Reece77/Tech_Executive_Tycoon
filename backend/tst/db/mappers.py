"""Convert between ORM rows and sim dataclasses. The sim never sees ORM objects."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, cast

from tst.db.models import (
    Base,
    CompanyRow,
    DecisionLogRow,
    EmploymentRow,
    LedgerEntryRow,
    LedgerLineRow,
    PersonHiddenRow,
    PersonInterestRow,
    PersonPersonalityRow,
    PersonProfileRevealRow,
    PersonRevealRow,
    PersonRow,
    PersonSkillRow,
    PersonTagRevealRow,
    PersonTagRow,
    SaveMetaRow,
    TurnLogRow,
    TurnSnapshotRow,
)
from tst.sim.decisions import Decisions
from tst.sim.ledger import LedgerEntry, LedgerLine
from tst.sim.people.models import (
    PA_KEY,
    Employment,
    EmploymentStatus,
    EndReason,
    HiddenTraits,
    Person,
    Personality,
    RevealRecord,
    RevealState,
    Skills,
)
from tst.sim.snapshot import CompanySnapshot, TurnSnapshot
from tst.sim.state import CompanyState, GameState, SaveMeta
from tst.sim.turn import LogItem


def company_to_state(row: CompanyRow) -> CompanyState:
    return CompanyState(
        id=row.id,
        name=row.name,
        is_player=row.is_player,
        stage=row.stage,
        founded_turn=row.founded_turn,
    )


def company_to_row(company: CompanyState) -> CompanyRow:
    return CompanyRow(
        id=company.id,
        name=company.name,
        is_player=company.is_player,
        stage=company.stage,
        founded_turn=company.founded_turn,
    )


def update_company_row(row: CompanyRow, company: CompanyState) -> None:
    row.name = company.name
    row.is_player = company.is_player
    row.stage = company.stage
    row.founded_turn = company.founded_turn


def game_state_from_rows(
    meta: SaveMetaRow,
    companies: list[CompanyRow],
    people: tuple[Person, ...] = (),
    employments: tuple[Employment, ...] = (),
    reveals: tuple[RevealState, ...] = (),
) -> GameState:
    return GameState(
        save_meta=SaveMeta(
            name=meta.name,
            master_seed=meta.master_seed,
            scenario_id=meta.scenario_id,
            difficulty=meta.difficulty,
        ),
        turn=meta.current_turn,
        companies=tuple(company_to_state(r) for r in sorted(companies, key=lambda r: r.id)),
        people=tuple(sorted(people, key=lambda p: p.id)),
        employments=tuple(sorted(employments, key=lambda e: e.id)),
        reveals=tuple(sorted(reveals, key=lambda r: (r.observer_company_id, r.person_id))),
    )


def entry_to_row(entry: LedgerEntry) -> LedgerEntryRow:
    return LedgerEntryRow(
        turn=entry.turn,
        company_id=entry.company_id,
        memo=entry.memo,
        lines=[
            LedgerLineRow(account_code=ln.account, amount_cents=ln.amount) for ln in entry.lines
        ],
    )


def entry_from_row(row: LedgerEntryRow) -> LedgerEntry:
    return LedgerEntry(
        turn=row.turn,
        company_id=row.company_id,
        memo=row.memo,
        lines=tuple(LedgerLine(ln.account_code, ln.amount_cents) for ln in row.lines),
    )


def snapshot_to_rows(snapshot: TurnSnapshot) -> list[TurnSnapshotRow]:
    return [
        TurnSnapshotRow(turn=snapshot.turn, company_id=s.company_id, kpis=s.kpis())
        for s in snapshot.companies
    ]


def company_snapshot_from_row(row: TurnSnapshotRow) -> CompanySnapshot:
    kpis: dict[str, Any] = row.kpis
    return CompanySnapshot(
        company_id=row.company_id,
        cash_cents=int(kpis["cash_cents"]),
        monthly_burn_cents=int(kpis["monthly_burn_cents"]),
        headcount=int(kpis["headcount"]),
    )


def log_item_to_row(item: LogItem) -> TurnLogRow:
    return TurnLogRow(
        turn=item.turn, company_id=item.company_id, kind=item.kind, message=item.message
    )


def decisions_to_row(turn: int, company_id: int, decisions: Decisions) -> DecisionLogRow:
    return DecisionLogRow(
        turn=turn, company_id=company_id, kind="turn_decisions", payload=asdict(decisions)
    )


# --- People (M1a) ---------------------------------------------------------------------------


def person_to_rows(person: Person) -> list[Base]:
    """The person row and its attribute rows. Positions keep data-file order (ADR-0013)."""
    rows: list[Base] = [
        PersonRow(
            id=person.id,
            first_name=person.first_name,
            last_name=person.last_name,
            region=person.region,
            birth_turn=person.birth_turn,
            role=person.role,
            level=person.level,
            work_style=person.work_style,
            salary_expectation_cents=person.salary_expectation_cents,
            is_founder=person.is_founder,
        )
    ]
    pid = person.id
    rows += [
        PersonSkillRow(person_id=pid, skill=k, position=i, value=v)
        for i, (k, v) in enumerate(person.skills.items)
    ]
    rows += [
        PersonPersonalityRow(person_id=pid, trait=k, position=i, value=v)
        for i, (k, v) in enumerate(person.personality.items)
    ]
    hidden = [*person.hidden.items, (PA_KEY, person.potential_ability)]
    rows += [
        PersonHiddenRow(person_id=pid, trait=k, position=i, value=v)
        for i, (k, v) in enumerate(hidden)
    ]
    rows += [
        PersonInterestRow(person_id=pid, interest=k, position=i)
        for i, k in enumerate(person.interests)
    ]
    rows += [PersonTagRow(person_id=pid, tag=k, position=i) for i, k in enumerate(person.tags)]
    return rows


def person_from_rows(
    row: PersonRow,
    skills: list[PersonSkillRow],
    personality: list[PersonPersonalityRow],
    hidden: list[PersonHiddenRow],
    interests: list[PersonInterestRow],
    tags: list[PersonTagRow],
) -> Person:
    hidden_items = [(h.trait, h.value) for h in sorted(hidden, key=lambda h: h.position)]
    pa = next(v for k, v in hidden_items if k == PA_KEY)
    return Person(
        id=row.id,
        first_name=row.first_name,
        last_name=row.last_name,
        region=row.region,
        birth_turn=row.birth_turn,
        role=row.role,
        level=row.level,
        skills=Skills(tuple((s.skill, s.value) for s in sorted(skills, key=lambda s: s.position))),
        personality=Personality(
            tuple((p.trait, p.value) for p in sorted(personality, key=lambda p: p.position))
        ),
        hidden=HiddenTraits(tuple((k, v) for k, v in hidden_items if k != PA_KEY)),
        potential_ability=pa,
        interests=tuple(i.interest for i in sorted(interests, key=lambda i: i.position)),
        work_style=row.work_style,
        tags=tuple(t.tag for t in sorted(tags, key=lambda t: t.position)),
        salary_expectation_cents=row.salary_expectation_cents,
        is_founder=row.is_founder,
    )


def employment_to_row(employment: Employment) -> EmploymentRow:
    return EmploymentRow(
        id=employment.id,
        person_id=employment.person_id,
        company_id=employment.company_id,
        role=employment.role,
        level=employment.level,
        salary_cents=employment.salary_cents,
        equity_bp=employment.equity_bp,
        start_turn=employment.start_turn,
        end_turn=employment.end_turn,
        status=employment.status,
        end_reason=employment.end_reason,
    )


def employment_from_row(row: EmploymentRow) -> Employment:
    return Employment(
        id=row.id,
        person_id=row.person_id,
        company_id=row.company_id,
        role=row.role,
        level=row.level,
        salary_cents=row.salary_cents,
        equity_bp=row.equity_bp,
        start_turn=row.start_turn,
        end_turn=row.end_turn,
        status=cast(EmploymentStatus, row.status),
        end_reason=cast(EndReason | None, row.end_reason),
    )


def reveal_to_rows(reveal: RevealState) -> list[Base]:
    key = {"person_id": reveal.person_id, "observer_company_id": reveal.observer_company_id}
    rows: list[Base] = [
        PersonRevealRow(
            **key,
            attribute=attr,
            position=i,
            hw=rec.hw,
            center_offset=rec.offset,
            last_updated_turn=rec.last_updated_turn,
        )
        for i, (attr, rec) in enumerate(reveal.attributes)
    ]
    if reveal.profile_revealed_turn is not None:
        rows.append(PersonProfileRevealRow(**key, revealed_turn=reveal.profile_revealed_turn))
    rows += [
        PersonTagRevealRow(**key, tag=tag, revealed_turn=turn) for tag, turn in reveal.revealed_tags
    ]
    return rows


def reveal_from_rows(
    observer_company_id: int,
    person_id: int,
    records: list[PersonRevealRow],
    profile: PersonProfileRevealRow | None,
    tags: list[PersonTagRevealRow],
) -> RevealState:
    return RevealState(
        observer_company_id=observer_company_id,
        person_id=person_id,
        attributes=tuple(
            (r.attribute, RevealRecord(r.hw, r.center_offset, r.last_updated_turn))
            for r in sorted(records, key=lambda r: r.position)
        ),
        profile_revealed_turn=None if profile is None else profile.revealed_turn,
        revealed_tags=tuple(
            (t.tag, t.revealed_turn) for t in sorted(tags, key=lambda t: (t.revealed_turn, t.tag))
        ),
    )
