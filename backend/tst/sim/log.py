"""Log items produced by turns and actions. The player company's templated items become
inbox items when persisted (M1b)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type LinkKind = Literal[
    "person", "candidate", "search", "product", "finance", "rival"
]  # rival: M14 and M14b
type ParamValue = str | int


@dataclass(frozen=True, slots=True)
class LogItem:
    turn: int
    company_id: int | None
    kind: str
    message: str
    template: str | None = None  # inbox_templates.yaml key; None = turn log only
    params: tuple[tuple[str, ParamValue], ...] = ()  # names ending _cents render as money
    link_kind: LinkKind | None = None
    link_id: int | None = None


def inbox_item(
    turn: int,
    company_id: int,
    template: str,
    *,
    link_kind: LinkKind | None = None,
    link_id: int | None = None,
    **params: ParamValue,
) -> LogItem:
    """A log item that becomes an inbox entry for the player company."""
    return LogItem(
        turn=turn,
        company_id=company_id,
        kind=template,
        message=", ".join(f"{k}={v}" for k, v in sorted(params.items())),
        template=template,
        params=tuple(sorted(params.items())),
        link_kind=link_kind,
        link_id=link_id,
    )
