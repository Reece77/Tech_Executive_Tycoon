"""FastAPI dependencies. Tests override these with app.dependency_overrides."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends

from tst.config import Settings, get_settings
from tst.loader import LoadedData, load_all


@lru_cache(maxsize=4)
def _load(data_dir: str) -> LoadedData:
    return load_all(Path(data_dir))


def get_data(settings: Annotated[Settings, Depends(get_settings)]) -> LoadedData:
    return _load(str(settings.data_dir))


SettingsDep = Annotated[Settings, Depends(get_settings)]
DataDep = Annotated[LoadedData, Depends(get_data)]
