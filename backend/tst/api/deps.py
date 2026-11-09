"""FastAPI dependencies. Tests override these with app.dependency_overrides."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

from tst.config import Settings, get_settings
from tst.loader import LoadedData, load_all


@lru_cache(maxsize=4)
def _load(data_dir: str) -> LoadedData:
    return load_all(Path(data_dir))


def get_data(request: Request, settings: Annotated[Settings, Depends(get_settings)]) -> LoadedData:
    """The base data, or for a route on a save started with a mod (M25), the base files
    with that save's own overlay copy: a save always plays with the data it began with."""
    base = _load(str(settings.data_dir))
    save_id = request.path_params.get("save_id")
    if not save_id:
        return base
    from tst.db.backup import SAVE_SUFFIX
    from tst.mods.store import data_for_save

    path = settings.resolved_save_dir() / f"{save_id}{SAVE_SUFFIX}"
    return data_for_save(path, settings.data_dir, base)


SettingsDep = Annotated[Settings, Depends(get_settings)]
DataDep = Annotated[LoadedData, Depends(get_data)]
