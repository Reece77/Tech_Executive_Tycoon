"""Inbox: render templated log items for the player company, list them, mark them read."""

from __future__ import annotations

import string
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, select
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
    items: Iterable[LogItem], player_id: int, templates: dict[str, InboxTemplate]
) -> list[InboxItemRow]:
    """Rows for the player company's templated items, in emission order."""
    rows = []
    for item in items:
        if item.template is None or item.company_id != player_id:
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
            )
        )
    return rows


def list_inbox(
    session: Session,
    company_id: int,
    *,
    unread_only: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> list[InboxMessage]:
    """Newest first; `offset` skips that many (paging, M2b)."""
    stmt = select(InboxItemRow).where(InboxItemRow.company_id == company_id)
    if unread_only:
        stmt = stmt.where(InboxItemRow.read.is_(False))
    stmt = stmt.order_by(InboxItemRow.id.desc()).offset(offset)
    if limit is not None:
        stmt = stmt.limit(limit)
    return [_message(r) for r in session.scalars(stmt)]


def inbox_total(session: Session, company_id: int, *, unread_only: bool = False) -> int:
    stmt = (
        select(func.count()).select_from(InboxItemRow).where(InboxItemRow.company_id == company_id)
    )
    if unread_only:
        stmt = stmt.where(InboxItemRow.read.is_(False))
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
    )
