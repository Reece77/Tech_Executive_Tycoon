"""Old history rows summarised, not lost (M30 sub-task 4; data-dictionary.md).

A save gains a month-end snapshot per company, log items and World news every month. Past a
retention window (balance.yaml `retention`) they are thinned, at the month's commit (ADR-0004:
in the turn's transaction), for the months that just left the window:

- **Snapshots** older than `snapshot_months` keep the quarter's last month (March, June,
  September, December), every month of the company's first year (an achievement reads it),
  and every month that set a new high of a value the Hall of Fame shows (`PEAK_KEYS`): the
  earliest month of each peak is such a record, so the peaks are exactly what they were.
- **Log items** (`turn_log`) older than `log_months` become a count a company, kind and year
  (`turn_log_summary`), a year at a time once all its months are past the window.
- **World news** leaves the state after `world.news_months` (the engine's window, unchanged);
  the items of the `major_news` kinds go to `world_news_archive` as they leave, and the World
  news screen shows them after the state's.
- **Candidates' records** (M45, for 60-year dynasty saves): each June, a person who was
  only ever a candidate, whose candidacy closed more than `candidate_people_months` ago, who
  is not in the state and whom no other row names, keeps their `person` row (the Timeline
  names them) but loses the rows nothing reads once they are gone: skills, personality,
  hidden traits, interests, tags, city, records of what an observer knew, their state and
  relocation (`CANDIDATE_RECORDS`). The engine loads people in the state only.

The engine never reads these rows back (the turn reads the last month's snapshot at most), so
results are unchanged. `save_meta.history_pruned_through` is the last month already thinned.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict
from typing import Final

from sqlalchemy import Table, delete, func, insert, select, text
from sqlalchemy.orm import Session

from tst.db.models import (
    Base,
    CompanyRow,
    SaveMetaRow,
    TurnLogRow,
    TurnLogSummaryRow,
    TurnSnapshotRow,
    WorldNewsArchiveRow,
)
from tst.sim.calendar import MONTHS_PER_YEAR
from tst.sim.data_models import RetentionBalance
from tst.sim.world.models import WorldNews

# M45: a closed candidate's rows that only describe them (nothing reads them once they have
# left the state); the person row stays, and so do their candidate and offer rows
CANDIDATE_RECORDS: Final = (
    "person_skill",
    "person_personality",
    "person_hidden",
    "person_interest",
    "person_tag",
    "person_tag_reveal",
    "person_reveal",
    "person_profile_reveal",
    "person_state",
    "person_city",
    "candidate_relocation",
)
# at most this many people a June, the longest-closed first: an older save's backlog of
# decades is worked off over a few years, not in one month (M45: 42,000 people took 2.6 s)
PRUNE_BATCH: Final = 3000  # tunable-exempt: a bound on one month's work, not a game rule
# references to a person that a closed candidate has as a candidate (kept with them)
CANDIDATE_OWN: Final = frozenset({("candidate", "person_id"), ("offer", "candidate_id")})
# June, half a year from the periodic backup that follows each December's commit: on a slow
# disk the year's deletes and the backup's copy of the save, together, made one month 2x slow
PRUNE_MONTH: Final = 5  # tunable-exempt: month index in the year (0 = January); not a game rule
PEAK_KEYS: Final = ("arr_cents", "headcount")  # the Hall of Fame's peaks (history_views)
QUARTER_END: Final = 2  # tunable-exempt: month index within a quarter that is kept (Mar, Jun..)
FIRST_YEAR: Final = 12  # tunable-exempt: months of a company's first year, all kept


Peaks = dict[tuple[int, str], float]  # (company, key) -> the highest value so far

# M30: per save, (its seed, the last month thinned, the peaks of every month up to it): the
# peaks only grow, so the next month's prune carries them on instead of scanning the history.
_PEAKS: dict[str, tuple[int, int, Peaks]] = {}


def prune(session: Session, played: int, keep: RetentionBalance) -> None:
    """Thin the months that have left the windows by the month `played` (module docstring),
    from the month after `save_meta.history_pruned_through`."""
    meta = session.scalars(select(SaveMetaRow)).one()
    done = -1 if meta.history_pruned_through is None else meta.history_pruned_through
    last = played - max(keep.snapshot_months, keep.log_months)
    if last <= done:
        return
    session.flush()
    founded = {i: t for i, t in session.execute(select(CompanyRow.id, CompanyRow.founded_turn))}
    where = str(session.connection().engine.url.database)
    kept = _PEAKS.get(where)
    if kept is not None and kept[:2] == (meta.master_seed, done):
        peaks = dict(kept[2])
    else:
        peaks = _peaks_through(session, done)
    for month in range(done + 1, last + 1):
        _thin_snapshots(session, month, founded, peaks)
        if month % MONTHS_PER_YEAR == MONTHS_PER_YEAR - 1:
            _summarise_log_year(session, month // MONTHS_PER_YEAR)
    meta.history_pruned_through = last
    _PEAKS[where] = (meta.master_seed, last, peaks)  # a rolled-back turn leaves `done` behind


def prune_candidates(
    session: Session, played: int, keep: RetentionBalance, live: Iterable[int]
) -> int:
    """Each June (`PRUNE_MONTH`, the month `played`), drop the records of people who
    were only ever candidates and closed more than `candidate_people_months` ago (module
    docstring). `live`: the people in the state, never touched. Returns how many people
    lost their records."""
    if played % MONTHS_PER_YEAR != PRUNE_MONTH:
        return 0
    cutoff = played - keep.candidate_people_months
    if cutoff < 0:
        return 0
    tables = {
        name
        for (name,) in session.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
    }
    session.flush()
    session.execute(text("DROP TABLE IF EXISTS temp.m45_gone"))
    session.execute(text("CREATE TEMP TABLE m45_gone (id INTEGER PRIMARY KEY, closed INTEGER)"))
    # closed candidates past the window that still have records (a pruned person has none)
    session.execute(
        text(
            "INSERT INTO temp.m45_gone (id, closed) "
            "SELECT c.person_id, COALESCE(c.resolved_turn, c.expires_turn) FROM candidate c "
            "JOIN person p ON p.id = c.person_id "
            "WHERE c.status != 'open' AND COALESCE(c.resolved_turn, c.expires_turn) <= :cutoff "
            "AND NOT p.is_founder "
            "AND EXISTS (SELECT 1 FROM person_skill s WHERE s.person_id = c.person_id)"
        ),
        {"cutoff": cutoff},
    )
    live_rows = [{"id": i} for i in live]
    if live_rows:
        session.execute(text("DELETE FROM temp.m45_gone WHERE id = :id"), live_rows)
    # anyone another row names is not only a candidate: every foreign key to person.id
    # (tables added later included) but their own records and candidacy
    for table in Base.metadata.sorted_tables:
        if table.name in CANDIDATE_RECORDS or table.name not in tables:
            continue
        for fk in table.foreign_keys:
            target = fk.column
            if target.table.name != "person" or target.name != "id":
                continue
            if (table.name, fk.parent.name) in CANDIDATE_OWN:
                continue
            session.execute(
                text(
                    f'DELETE FROM temp.m45_gone WHERE id IN (SELECT "{fk.parent.name}" '
                    f'FROM "{table.name}" WHERE "{fk.parent.name}" IS NOT NULL)'
                )
            )
    session.execute(  # the longest-closed first, at most PRUNE_BATCH of them
        text(
            "DELETE FROM temp.m45_gone WHERE id NOT IN (SELECT id FROM temp.m45_gone "
            "ORDER BY closed, id LIMIT :batch)"
        ),
        {"batch": PRUNE_BATCH},
    )
    gone = int(session.scalar(text("SELECT count(*) FROM temp.m45_gone")) or 0)
    if gone:
        for name in CANDIDATE_RECORDS:
            if name in tables:
                session.execute(
                    text(f'DELETE FROM "{name}" WHERE person_id IN (SELECT id FROM temp.m45_gone)')
                )
    session.execute(text("DROP TABLE temp.m45_gone"))
    return gone


def _peaks_through(session: Session, month: int) -> Peaks:
    """Every company's highest `PEAK_KEYS` values over the months up to `month`."""
    peaks: Peaks = {}
    if month < 0:
        return peaks
    columns = [func.max(func.json_extract(TurnSnapshotRow.kpis, f"$.{k}")) for k in PEAK_KEYS]
    for company_id, *values in session.execute(
        select(TurnSnapshotRow.company_id, *columns)
        .where(TurnSnapshotRow.turn <= month)
        .group_by(TurnSnapshotRow.company_id)
    ):
        for key, value in zip(PEAK_KEYS, values, strict=True):
            if value is not None:
                peaks[(company_id, key)] = value
    return peaks


def _thin_snapshots(session: Session, month: int, founded: dict[int, int], peaks: Peaks) -> None:
    rows = session.execute(
        select(TurnSnapshotRow.id, TurnSnapshotRow.company_id, TurnSnapshotRow.kpis).where(
            TurnSnapshotRow.turn == month
        )
    ).all()
    gone = []
    for row_id, company_id, kpis in rows:
        record = _sets_a_record(peaks, company_id, kpis)
        if month % 3 == QUARTER_END or record:
            continue
        start = founded.get(company_id)
        if start is not None and start <= month < start + FIRST_YEAR:
            continue
        gone.append(row_id)
    if gone:
        session.execute(delete(TurnSnapshotRow).where(TurnSnapshotRow.id.in_(gone)))


def _sets_a_record(peaks: Peaks, company_id: int, kpis: dict[str, object]) -> bool:
    """Whether a peak value this month beats every earlier month of the company; the month's
    values join the peaks (the kept rows hold every earlier record, so they are the true
    highs, as a query over the kept rows would find)."""
    record = False
    for key in PEAK_KEYS:
        value = kpis.get(key)
        if not isinstance(value, int | float) or isinstance(value, bool):
            continue
        best = peaks.get((company_id, key))
        if best is None or value > best:
            if value:
                record = True
            peaks[(company_id, key)] = value
    return record


def _summarise_log_year(session: Session, year: int) -> None:
    first, last = year * MONTHS_PER_YEAR, (year + 1) * MONTHS_PER_YEAR - 1
    where = (TurnLogRow.turn >= first, TurnLogRow.turn <= last)
    counts = session.execute(
        select(TurnLogRow.company_id, TurnLogRow.kind, func.count())
        .where(*where)
        .group_by(TurnLogRow.company_id, TurnLogRow.kind)
        .order_by(TurnLogRow.company_id, TurnLogRow.kind)
    ).all()
    if not counts:
        return
    session.execute(
        insert(TurnLogSummaryRow),
        [{"year": year, "company_id": c, "kind": k, "items": n} for c, k, n in counts],
    )
    session.execute(delete(TurnLogRow).where(*where))


def archive_news(
    session: Session,
    before: Iterable[WorldNews],
    after: Iterable[WorldNews],
    keep: RetentionBalance,
) -> None:
    """Major items that left the state's World news this month, kept in the archive."""
    still = {n.id for n in after}
    major = set(keep.major_news)
    leaving = [n for n in before if n.id not in still and n.kind in major]
    if not leaving:
        return
    known = set(
        session.scalars(
            select(WorldNewsArchiveRow.id).where(
                WorldNewsArchiveRow.id.in_([n.id for n in leaving])
            )
        )
    )
    rows = [asdict(n) for n in leaving if n.id not in known]
    if rows:
        session.execute(insert(_archive()), rows)


def _archive() -> Table:
    table: Table = WorldNewsArchiveRow.__table__  # type: ignore[assignment]
    return table


def archived_news(session: Session) -> list[WorldNews]:
    """The archive, oldest first (World news shows it after the state's items); none in a
    save from before 0054."""
    from tst.db.state_io import has_table

    if not has_table(session, WorldNewsArchiveRow):
        return []
    return [
        WorldNews(
            id=r.id,
            turn=r.turn,
            kind=r.kind,  # type: ignore[arg-type]
            message=r.message,
            company_id=r.company_id,
            other_id=r.other_id,
            region=r.region,
            good=r.good,
        )
        for r in session.scalars(select(WorldNewsArchiveRow).order_by(WorldNewsArchiveRow.id))
    ]
