"""The conglomerate view's ledger read (M43 sub-task 2): the group's lines summed by company,
year, account and memo in one query, and the names its memos use, for
`tst.sim.group.conglomerate.books`. Read-only."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from sqlalchemy import ColumnElement, and_, func, or_, select
from sqlalchemy.orm import Session

from tst.db.models import LedgerEntryRow, LedgerLineRow
from tst.loader import LoadedData
from tst.sim.calendar import turn_to_ym
from tst.sim.facilities.lifecycle import facility_name
from tst.sim.finance.statements import INTEREST_PREFIX, TAX_PREFIX
from tst.sim.group.conglomerate import Books, LineSum, books, industry_maps
from tst.sim.mining.actions import mine_name
from tst.sim.power.plants import plant_name
from tst.sim.state import GameState, group_members, listed_id

CENTURY_MONTHS = 1200  # tunable-exempt: shifts turns positive for SQL division (M50)

MONTHS_A_YEAR = 12  # tunable-exempt: calendar
START_YEAR = 2010  # tunable-exempt: turn 0 is January 2010


type Run = tuple[int, int | None]  # [first turn counted, the turn it left) ; None: inside now


@dataclass(frozen=True, slots=True)
class Member:
    company_id: int
    parent_id: int | None
    start: int  # first turn counted
    end: int | None  # the turn it last left; None while inside
    # M43r (Codex review 9 finding 4): every run it was inside, coalesced; a company sold and
    # bought again has two, and the months between belong to someone else.
    runs: tuple[Run, ...] = ()

    def spans(self) -> tuple[Run, ...]:
        return self.runs or ((self.start, self.end),)


def coalesce(runs: list[Run]) -> tuple[Run, ...]:
    """The union of half-open runs, sorted: overlapping or touching runs merge (the operating
    and holding-company paths to one company), disjoint ones stay apart."""
    out: list[Run] = []
    for start, end in sorted(runs, key=lambda r: r[0]):
        if out:
            last_start, last_end = out[-1]
            if last_end is None or start <= last_end:
                merged = None if last_end is None or end is None else max(last_end, end)
                out[-1] = (last_start, merged)
                continue
        out.append((start, end))
    return tuple(out)


def members(state: GameState) -> list[Member]:
    """The group's root (the listed entity: the holding company once formed), the player's
    company and every company inside either (31.1), each with the runs of turns it was inside.
    The player's company counts from the start, and what it owned counts from when it bought
    it, before the holding company was formed as after."""
    root = listed_id(state)
    player = state.player.id
    fixed = {root: Member(root, None, 0, None)}
    fixed.setdefault(player, Member(player, root if player != root else None, 0, None))
    found: dict[int, list[Run]] = {}
    parents: dict[int, int | None] = {}
    for top in dict.fromkeys((player, root)):
        for m in group_members(state, top):
            if m.company_id in fixed:
                continue
            found.setdefault(m.company_id, []).append((m.start + 1, m.end))
            parents[m.company_id] = m.parent_id
    runs = dict(fixed)
    for cid, spans in found.items():
        merged = coalesce(spans)
        runs[cid] = Member(cid, parents[cid], merged[0][0], merged[-1][1], merged)
    order = [root, *([player] if player != root else [])]
    rest = sorted((c for c in runs if c not in order), key=lambda c: (runs[c].start, c))
    return [runs[c] for c in (*order, *rest)]


def names(state: GameState, ids: set[int], data: LoadedData) -> dict[int, dict[str, str]]:
    """Each company's product, facility, plant and mine names -> industry key."""
    categories, kinds, _, plants, mines = industry_maps(data.balance.conglomerate)
    gd = data.game_data
    out: dict[int, dict[str, str]] = defaultdict(dict)
    for p in state.products:
        if p.company_id in ids and p.category in categories:
            out[p.company_id][p.name] = categories[p.category]
    for f in state.facilities:
        if f.company_id in ids and f.kind in kinds:
            out[f.company_id][facility_name(f, data.balance, gd)] = kinds[f.kind]
    for plant in state.plants:
        if plant.company_id in ids:
            out[plant.company_id][plant_name(state, plant, gd)] = plants
    if gd.geology is not None:
        for mine in state.mines:
            if mine.company_id in ids:
                out[mine.company_id][mine_name(mine, gd)] = mines
    return dict(out)


def _inside(run: Run) -> ColumnElement[bool]:
    start, end = run
    turn = LedgerEntryRow.turn
    return turn >= start if end is None else and_(turn >= start, turn < end)


def line_sums(session: Session, group: list[Member]) -> list[LineSum]:
    """The members' ledger lines while inside the group (each run, each entry once), summed by
    year, account and memo."""
    out: list[LineSum] = []
    # M50: SQLite's integer division truncates toward zero, so a negative turn (2008-2009) is
    # shifted a century forward first; for turns from 0 the year is the same
    year = (LedgerEntryRow.turn + CENTURY_MONTHS) // MONTHS_A_YEAR - CENTURY_MONTHS // MONTHS_A_YEAR
    for m in group:
        q = (
            select(
                year.label("year"),
                LedgerLineRow.account_code,
                LedgerEntryRow.memo,
                func.sum(LedgerLineRow.amount_cents),
            )
            .join(LedgerLineRow.entry)
            .where(LedgerEntryRow.company_id == m.company_id, or_(*map(_inside, m.spans())))
            .group_by("year", LedgerLineRow.account_code, LedgerEntryRow.memo)
        )
        for y, account, memo, cents in session.execute(q):
            out.append(
                LineSum(m.company_id, START_YEAR + int(y), str(account), str(memo), int(cents))
            )
    return out


def read_books(session: Session, state: GameState, data: LoadedData) -> tuple[Books, list[Member]]:
    group = members(state)
    ids = {m.company_id for m in group}
    types = {a.code: a.type for a in data.game_data.accounts}
    figures = books(
        line_sums(session, group),
        names(state, ids, data),
        types,
        data.balance.conglomerate,
        INTEREST_PREFIX,
        TAX_PREFIX,
        root=listed_id(state),
    )
    return figures, group


def current_year(state: GameState) -> int:
    return turn_to_ym(state.turn)[0]
