"""Inbox: render templated log items for the player company, list them, mark them read,
archive them (M4c). Reading and archiving are UI state: no energy, no game effect, not in
decision_log."""

from __future__ import annotations

import string
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from tst.db.models import InboxItemRow
from tst.sim.data_models import InboxTemplate
from tst.sim.errors import NotFoundError
from tst.sim.log import LogItem
from tst.sim.money import format_money

MONEY_SUFFIX = "_cents"
ARTICLE_SPEC = "a"  # "{role:a}" renders "a Designer" or "an Account executive"
# Words that start with a vowel letter but a consonant sound, and the reverse.
CONSONANT_SOUND = ("uni", "use", "usu", "eu", "one")
VOWEL_SOUND = ("hour", "honest", "heir")


def indefinite_article(word: str) -> str:
    """'a' or 'an' by the sound of the first word (simple English rules)."""
    lower = word.strip().lower()
    if lower.startswith(VOWEL_SOUND):
        return "an"
    if lower.startswith(CONSONANT_SOUND):
        return "a"
    return "an" if lower[:1] in {"a", "e", "i", "o", "u"} else "a"


class _TemplateFormatter(string.Formatter):
    def format_field(self, value: Any, format_spec: str) -> Any:
        if format_spec == ARTICLE_SPEC:
            text = str(value)
            return f"{indefinite_article(text)} {text}"
        return super().format_field(value, format_spec)


_FORMATTER = _TemplateFormatter()


class UnknownInboxItemError(NotFoundError):
    code = "unknown_inbox_item"


@dataclass(frozen=True, slots=True)
class InboxMessage:
    id: int
    turn: int
    template: str
    title: str
    body: str
    link_kind: str | None
    link_id: int | None
    read: bool
    archived: bool = False
    bookmarked: bool = False  # M10b (23.1)
    event_links: tuple[tuple[int, str], ...] = ()  # (event id, label), M7c


def render(item: LogItem, templates: dict[str, InboxTemplate]) -> tuple[str, str]:
    """Title and body for a templated log item; *_cents parameters are shown as money."""
    assert item.template is not None
    template = templates[item.template]
    params = {
        key: format_money(int(value)) if key.endswith(MONEY_SUFFIX) else value
        for key, value in item.params
    }
    return (
        _FORMATTER.vformat(template.title, (), params),
        _FORMATTER.vformat(template.body, (), params),
    )


def inbox_rows(
    items: Iterable[LogItem],
    player_id: int,
    templates: dict[str, InboxTemplate],
    also: frozenset[int] = frozenset(),
) -> list[InboxItemRow]:
    """Rows for the player company's templated items, in emission order; items for `also`
    (the player's holding company, M16) reach the same inbox."""
    rows = []
    for item in items:
        if item.template is None or (item.company_id != player_id and item.company_id not in also):
            continue
        title, body = render(item, templates)
        rows.append(
            InboxItemRow(
                turn=item.turn,
                company_id=player_id,
                template=item.template,
                title=title,
                body=body,
                link_kind=item.link_kind,
                link_id=item.link_id,
                read=False,
                archived=False,
                bookmarked=False,
            )
        )
    return rows


def list_inbox(
    session: Session,
    company_id: int,
    *,
    unread_only: bool = False,
    kinds: Sequence[str] | None = None,
    limit: int | None = None,
    offset: int = 0,
    archived: bool | None = None,
) -> list[InboxMessage]:
    """Newest first; `offset` skips that many (paging, M2b); `kinds` keeps only those
    templates (M3b); `archived` keeps only archived (True) or unarchived (False) items, or
    both (None; M4c)."""
    stmt = select(InboxItemRow).where(InboxItemRow.company_id == company_id)
    if unread_only:
        stmt = stmt.where(InboxItemRow.read.is_(False))
    if kinds is not None:
        stmt = stmt.where(InboxItemRow.template.in_(kinds))
    if archived is not None:
        stmt = stmt.where(InboxItemRow.archived.is_(archived))
    stmt = stmt.order_by(InboxItemRow.id.desc()).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return _with_links(session, [_message(r) for r in session.scalars(stmt)])


def inbox_total(
    session: Session,
    company_id: int,
    *,
    unread_only: bool = False,
    kinds: Sequence[str] | None = None,
    archived: bool | None = None,
) -> int:
    stmt = (
        select(func.count()).select_from(InboxItemRow).where(InboxItemRow.company_id == company_id)
    )
    if unread_only:
        stmt = stmt.where(InboxItemRow.read.is_(False))
    if kinds is not None:
        stmt = stmt.where(InboxItemRow.template.in_(kinds))
    if archived is not None:
        stmt = stmt.where(InboxItemRow.archived.is_(archived))
    return int(session.scalar(stmt) or 0)


def unread_count(session: Session, company_id: int) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(InboxItemRow)
            .where(InboxItemRow.company_id == company_id, InboxItemRow.read.is_(False))
        )
        or 0
    )


def mark_read(
    session: Session, company_id: int, item_id: int, *, read: bool = True
) -> InboxMessage:
    """Set an item's read flag (read=False marks it unread again)."""
    row = session.get(InboxItemRow, item_id)
    if row is None or row.company_id != company_id:
        raise UnknownInboxItemError(f"no inbox item {item_id}")
    row.read = read
    return _message(row)


def _own(session: Session, company_id: int, item_id: int) -> InboxItemRow:
    row = session.get(InboxItemRow, item_id)
    if row is None or row.company_id != company_id:
        raise UnknownInboxItemError(f"no inbox item {item_id}")
    return row


def mark_all_read(session: Session, company_id: int) -> int:
    """Mark every unread item read; returns how many changed (M4c)."""
    result = session.execute(
        update(InboxItemRow)
        .where(InboxItemRow.company_id == company_id, InboxItemRow.read.is_(False))
        .values(read=True)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def archive(
    session: Session, company_id: int, item_id: int, *, archived: bool = True
) -> InboxMessage:
    """Archive an item (it is read too) or bring it back (M4c)."""
    row = _own(session, company_id, item_id)
    row.archived = archived
    if archived:
        row.read = True
    return _message(row)


def archive_read(session: Session, company_id: int) -> int:
    """Archive every read item still in the inbox; returns how many (M4c)."""
    result = session.execute(
        update(InboxItemRow)
        .where(
            InboxItemRow.company_id == company_id,
            InboxItemRow.read.is_(True),
            InboxItemRow.archived.is_(False),
        )
        .values(archived=True)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def bookmark(
    session: Session, company_id: int, item_id: int, *, bookmarked: bool = True
) -> InboxMessage:
    """Star an item so it is never auto-archived (23.1, M10b); a bookmarked item that was
    archived comes back to the inbox."""
    row = _own(session, company_id, item_id)
    row.bookmarked = bookmarked
    if bookmarked:
        row.archived = False
    return _message(row)


def archive_events(session: Session, company_id: int, event_ids: Iterable[int]) -> int:
    """Archive the inbox items of answered events (23.1, M10b); returns how many changed."""
    ids = sorted(set(event_ids))
    if not ids:
        return 0
    result = session.execute(
        update(InboxItemRow)
        .where(
            InboxItemRow.company_id == company_id,
            InboxItemRow.link_kind == "event",
            InboxItemRow.link_id.in_(ids),
            InboxItemRow.archived.is_(False),
            InboxItemRow.bookmarked.is_(False),
        )
        .values(archived=True, read=True)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def auto_archive(session: Session, company_id: int, turn: int, months: int) -> int:
    """At month end, archive read, unbookmarked items `months` or more old (23.1, M10b)."""
    result = session.execute(
        update(InboxItemRow)
        .where(
            InboxItemRow.company_id == company_id,
            InboxItemRow.read.is_(True),
            InboxItemRow.archived.is_(False),
            InboxItemRow.bookmarked.is_(False),
            InboxItemRow.turn <= turn - months,
        )
        .values(archived=True)
    )
    return int(result.rowcount or 0)  # type: ignore[attr-defined]


def _message(row: InboxItemRow) -> InboxMessage:
    return InboxMessage(
        id=row.id,
        turn=row.turn,
        template=row.template,
        title=row.title,
        body=row.body,
        link_kind=row.link_kind,
        link_id=row.link_id,
        read=row.read,
        archived=row.archived,
        bookmarked=row.bookmarked,
    )


def get_item(session: Session, company_id: int, item_id: int) -> InboxMessage:
    """One inbox item, archived or not (M7c deep links)."""
    row = session.get(InboxItemRow, item_id)
    if row is None or row.company_id != company_id:
        raise UnknownInboxItemError(f"no inbox item {item_id}")
    return _with_links(session, [_message(row)])[0]


def event_item(session: Session, company_id: int, event_id: int) -> InboxMessage:
    """The inbox item that carries an event's card (M7c deep links)."""
    row = session.scalars(
        select(InboxItemRow)
        .where(
            InboxItemRow.company_id == company_id,
            InboxItemRow.link_kind == "event",
            InboxItemRow.link_id == event_id,
        )
        .order_by(InboxItemRow.id)
        .limit(1)
    ).first()
    if row is None:
        raise UnknownInboxItemError(f"no inbox item for event {event_id}")
    return _message(row)


def _with_links(session: Session, messages: list[InboxMessage]) -> list[InboxMessage]:
    """Attach each message's event links (M7c); saves before 0021 have none."""
    from dataclasses import replace

    from tst.db.models import InboxEventLinkRow
    from tst.db.state_io import has_table

    ids = [m.id for m in messages]
    if not ids or not has_table(session, InboxEventLinkRow):
        return messages
    links: dict[int, list[tuple[int, str]]] = {}
    for row in session.scalars(
        select(InboxEventLinkRow)
        .where(InboxEventLinkRow.item_id.in_(ids))
        .order_by(InboxEventLinkRow.item_id, InboxEventLinkRow.position)
    ):
        links.setdefault(row.item_id, []).append((row.event_id, row.label))
    return [replace(m, event_links=tuple(links.get(m.id, ()))) for m in messages]
