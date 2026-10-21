"""Player and AI decisions for one turn. Empty in M0; the version lets old decision logs load."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

DECISIONS_VERSION: Final = 1


@dataclass(frozen=True, slots=True)
class Decisions:
    version: int = DECISIONS_VERSION
