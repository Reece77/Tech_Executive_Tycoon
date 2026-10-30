"""LLM settings and the monthly budget meter (ADR-0005 sections 6 and 7).

Both live next to the saves, not in a save: the budget is real money across every save.
`saves/llm_settings.json` holds the player's choices (adapter, budget, model ids, prices);
`saves/llm_spend.json` holds spend and counts per real calendar month, the only wall-clock
use in the game. The API key comes from the environment (`ANTHROPIC_API_KEY`, `.env`) and is
never stored or returned.
"""

from __future__ import annotations

import json
import logging
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from tst.llm.anthropic_adapter import AnthropicAdapter
from tst.llm.base import LLMAdapter
from tst.llm.offline import MockLLMAdapter, TemplateAdapter

log = logging.getLogger(__name__)

SETTINGS_FILE = "llm_settings.json"
SPEND_FILE = "llm_spend.json"
MICRO = 1_000_000  # tunable-exempt: prices are per million tokens

type AdapterChoice = Literal["claude", "templates", "mock"]


class ModelPrice(BaseModel):
    input: float = Field(ge=0)  # cents per million input tokens
    output: float = Field(ge=0)  # cents per million output tokens


class LLMSettings(BaseModel):
    """Defaults: Claude when a key is found, $10 a calendar month (Reece, 2026-10-27), a
    small model for events and a larger one for storylines, at 2026 list prices."""

    adapter: AdapterChoice = "claude"
    monthly_budget_cents: int = Field(default=1000, ge=0)
    model_events: str = "claude-haiku-5-5"
    model_story: str = "claude-sonnet-5-5"
    price_per_mtok_cents: dict[str, ModelPrice] = Field(
        default_factory=lambda: {
            "claude-haiku-5-5": ModelPrice(input=10, output=50),
            "claude-sonnet-5-5": ModelPrice(input=200, output=1000),
            "mock": ModelPrice(input=0, output=0),
        }
    )

    def cost_cents(self, model: str, input_tokens: int, output_tokens: int) -> float:
        price = self.price_per_mtok_cents.get(model)
        if price is None:
            log.warning("No price for model %s; counting it at the story model's price", model)
            price = self.price_per_mtok_cents.get(self.model_story, ModelPrice(input=0, output=0))
        return (input_tokens * price.input + output_tokens * price.output) / MICRO


class MonthSpend(BaseModel):
    cents: float = 0.0
    calls: int = 0
    events_claude: int = 0  # events written by Claude
    events_rejected: int = 0  # drafts rejected twice, replaced by templates
    event_cents: float = 0.0  # spend on events, for the average cost per event


_lock = threading.Lock()


def load_settings(save_dir: Path) -> LLMSettings:
    path = save_dir / SETTINGS_FILE
    try:
        return LLMSettings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return LLMSettings()


def save_settings(save_dir: Path, settings: LLMSettings) -> None:
    save_dir.mkdir(parents=True, exist_ok=True)
    (save_dir / SETTINGS_FILE).write_text(
        settings.model_dump_json(indent=2) + "\n", encoding="utf-8"
    )


def month_key(now: datetime | None = None) -> str:
    """The real calendar month spend counts toward (ADR-0005 section 6)."""
    return (now or datetime.now(UTC)).strftime("%Y-%m")


def reset_date(now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    year, month = (
        (now.year + 1, 1) if now.month == 12 else (now.year, now.month + 1)
    )  # tunable-exempt: calendar
    return f"{year:04d}-{month:02d}-01"


def _read_spend(save_dir: Path) -> dict[str, MonthSpend]:
    try:
        raw = json.loads((save_dir / SPEND_FILE).read_text(encoding="utf-8"))
        return {k: MonthSpend.model_validate(v) for k, v in raw.items()}
    except (OSError, ValueError):
        return {}


def month_spend(save_dir: Path, now: datetime | None = None) -> MonthSpend:
    return _read_spend(save_dir).get(month_key(now), MonthSpend())


def add_spend(
    save_dir: Path,
    cents: float,
    *,
    calls: int = 0,
    claude_events: int = 0,
    rejected: int = 0,
    event_cents: float = 0.0,
    now: datetime | None = None,
) -> MonthSpend:
    with _lock:
        spend = _read_spend(save_dir)
        key = month_key(now)
        month = spend.get(key, MonthSpend())
        month = MonthSpend(
            cents=month.cents + cents,
            calls=month.calls + calls,
            events_claude=month.events_claude + claude_events,
            events_rejected=month.events_rejected + rejected,
            event_cents=month.event_cents + event_cents,
        )
        spend[key] = month
        save_dir.mkdir(parents=True, exist_ok=True)
        tmp = save_dir / f"{SPEND_FILE}.tmp"
        tmp.write_text(
            json.dumps({k: v.model_dump() for k, v in sorted(spend.items())}, indent=2) + "\n",
            encoding="utf-8",
        )
        tmp.replace(save_dir / SPEND_FILE)
        return month


def active_adapter(
    settings: LLMSettings, api_key: str | None, forced: str | None = None
) -> LLMAdapter:
    """The adapter in use: `forced` (TST_LLM_ADAPTER; tests set "mock") wins; Claude only
    with a key; otherwise templates (ADR-0005: fully playable offline)."""
    choice = forced or settings.adapter
    if choice == "mock":
        return MockLLMAdapter()
    if choice == "claude" and api_key:
        return AnthropicAdapter(api_key, settings.model_events, settings.model_story)
    return TemplateAdapter()
