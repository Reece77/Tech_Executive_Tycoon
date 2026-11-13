"""M23a records (playtest 5): how a counterparty regards the player's group after a contract was
broken, and the foundry contracts a fab's owner signs with rival chip designers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

type ContractKind = Literal["commodity", "refining", "production", "mine", "foundry"]


@dataclass(frozen=True, slots=True)
class Relation:
    """A counterparty's willingness to deal with the player's group (M23a): `score` (0-1) as of
    `turn`, recovering contracts.relationship_recovery a month towards 1 (`score_at`)."""

    counterparty: str  # a supplier, manufacturer or foundry key, or a buyer's name
    score: float
    turn: int
    breaks: int = 0


@dataclass(frozen=True, slots=True)
class FoundryContract:
    """A fab's owner sells `monthly_starts` wafer starts a month to a rival chip designer at
    `price_millicents` a start (exact thousandths of a cent; M23r, Codex review 6 finding 5) from
    `signed_turn` to `end_turn` (38.2 with M23a): the starts come out
    of the fab's spare starts before spot slots; the buyer takes what the fab delivers, and pays
    contracts.foundry.take_or_pay of the contracted starts' value on any it does not take."""

    id: int
    fab_id: int  # the facility's id
    company_id: int  # the fab's owner
    customer: str  # a rival chip designer's name
    monthly_starts: float
    price_millicents: int  # a start, in thousandths of a cent
    signed_turn: int
    end_turn: int  # the last month it covers
    delivered: float = 0.0  # last month's starts
    status: Literal["active", "ended"] = "active"

    def running(self, turn: int) -> bool:
        return self.status == "active" and self.signed_turn <= turn <= self.end_turn
