"""Saved column views (M7b sub-task 5; spec 13: "every table supports saved column views").

`saves/ui_settings.json` sits beside the saves like the LLM settings and is shared across
them: a view saved on one save's People table shows on every save's. It is UI state only,
never written into a save file, and never read by the game.
"""

from __future__ import annotations

import json
import logging
import threading
from pathlib import Path

from pydantic import BaseModel, Field, model_validator

log = logging.getLogger(__name__)

SETTINGS_FILE = "ui_settings.json"
DEFAULT_VIEW = "Default"  # built in: every column, no sort; it cannot be saved or deleted
MAX_VIEWS = 20  # saved views per table
NAME_MAX = 40  # characters in a view name
TABLE_ID = r"^[a-z][a-z0-9_.-]{0,63}$"


class SortKey(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    desc: bool = False


class TableView(BaseModel):
    name: str = Field(min_length=1, max_length=NAME_MAX)
    visibility: dict[str, bool] = Field(
        default_factory=dict, description="Column id -> shown; missing columns are shown"
    )
    order: list[str] = Field(default_factory=list, description="Column ids, left to right")
    sort: list[SortKey] = Field(default_factory=list)


class TableViews(BaseModel):
    views: list[TableView] = Field(default_factory=list, max_length=MAX_VIEWS)
    current: str = Field(default=DEFAULT_VIEW, description="The view last used")

    @model_validator(mode="after")
    def _check(self) -> TableViews:
        names = [v.name.strip() for v in self.views]
        if DEFAULT_VIEW in names:
            raise ValueError(f"{DEFAULT_VIEW!r} is built in and cannot be saved")
        if len(set(names)) != len(names):
            raise ValueError("view names must be different")
        if self.current != DEFAULT_VIEW and self.current not in names:
            raise ValueError(f"current view {self.current!r} is not saved")
        return self


class UISettings(BaseModel):
    tables: dict[str, TableViews] = Field(default_factory=dict)


_lock = threading.Lock()


def load_ui(save_dir: Path) -> UISettings:
    path = save_dir / SETTINGS_FILE
    try:
        return UISettings.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return UISettings()


def save_table(save_dir: Path, table_id: str, views: TableViews) -> UISettings:
    """Replace one table's views; the other tables' stay as they are."""
    with _lock:
        settings = load_ui(save_dir)
        settings.tables[table_id] = views
        save_dir.mkdir(parents=True, exist_ok=True)
        tmp = save_dir / (SETTINGS_FILE + ".tmp")
        tmp.write_text(json.dumps(settings.model_dump(), indent=2) + "\n", encoding="utf-8")
        tmp.replace(save_dir / SETTINGS_FILE)
    return settings
