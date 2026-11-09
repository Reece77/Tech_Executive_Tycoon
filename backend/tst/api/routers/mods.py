"""Data editor routes (M25 section 3): editable files, and named mods saved as overlays in
saves/mods after the loader has validated the merged data."""

from __future__ import annotations

from typing import Any

import yaml
from fastapi import APIRouter, status

from tst.api.deps import SettingsDep
from tst.api.routers.saves import ERRORS
from tst.api.schemas.mods import (
    EditorFileOut,
    EditorFileRefOut,
    ModChangeOut,
    ModIn,
    ModOut,
)
from tst.config import Settings
from tst.mods import schema, store
from tst.mods.hidden import path_withheld, strip
from tst.mods.overlay import OverlayError, changes_of, merge, overlay_of
from tst.sim.errors import NotFoundError

router = APIRouter(prefix="/api/mods", tags=["mods"])


class UnknownDataFileError(NotFoundError):
    code = "unknown_data_file"


def _base(settings: Settings) -> dict[str, Any]:
    return {
        f: yaml.safe_load((settings.data_dir / f).read_text(encoding="utf-8"))
        for f in schema.editable_files()
    }


def _out(mod: store.Mod, base: dict[str, Any]) -> ModOut:
    changes = [
        ModChangeOut(file=f, path=p, value=strip(v))
        for f, overlay in mod.files.items()
        for p, v in changes_of(base.get(f), overlay)
        if not path_withheld(p)
    ]
    return ModOut(
        name=mod.name, description=mod.description, files=sorted(mod.files), changes=changes
    )


@router.get("", response_model=list[ModOut], operation_id="listMods")
def list_mods(settings: SettingsDep) -> list[ModOut]:
    base = _base(settings)
    return [_out(m, base) for m in store.list_mods(settings.resolved_save_dir())]


@router.get("/files", response_model=list[EditorFileRefOut], operation_id="listDataFiles")
def list_files() -> list[EditorFileRefOut]:
    """The editable data files: rivals, entrants, categories, cities, scenarios and balance,
    then any file the loader adds later."""
    return [EditorFileRefOut(file=f, label=schema.label(f)) for f in schema.editable_files()]


@router.get(
    "/files/{file}", response_model=EditorFileOut, responses=ERRORS, operation_id="getDataFile"
)
def get_file(file: str, settings: SettingsDep, mod: str | None = None) -> EditorFileOut:
    """One file's form: its spec, base values, comments, and its values under `mod`."""
    if file not in schema.editable_files():
        raise UnknownDataFileError(f"{file!r} is not an editable data file")
    f = schema.editor_file(settings.data_dir, file)
    value = f.base
    if mod:
        overlay = store.read_mod(settings.resolved_save_dir(), mod).files.get(file)
        if overlay is not None:
            value = strip(merge(f.base, overlay))
    return EditorFileOut(
        file=f.file, label=f.label, spec=f.spec, base=f.base, value=value, comments=f.comments
    )


@router.get("/{name}", response_model=ModOut, responses=ERRORS, operation_id="getMod")
def get_mod(name: str, settings: SettingsDep) -> ModOut:
    return _out(store.read_mod(settings.resolved_save_dir(), name), _base(settings))


@router.put("/{name}", response_model=ModOut, responses=ERRORS, operation_id="saveMod")
def save_mod(name: str, body: ModIn, settings: SettingsDep) -> ModOut:
    """Save a mod from its changes. The merged data is validated exactly as the base files
    are; an invalid mod is refused with the loader's message and nothing is written."""
    store.check_name(name)
    base = _base(settings)
    if bad := [c for c in body.changes if path_withheld(c.path)]:
        raise store.InvalidModError(
            f"{'.'.join(bad[0].path)}: not editable here (a value the game keeps hidden)"
        )
    try:
        files = overlay_of([(c.file, c.path, c.value) for c in body.changes], base)
    except OverlayError as exc:
        raise store.InvalidModError(str(exc)) from exc
    mod = store.Mod(name, body.description.strip(), files)
    if len(mod.description) > store.DESCRIPTION_MAX:
        raise store.InvalidModError(
            f"a mod description has at most {store.DESCRIPTION_MAX} characters"
        )
    store.write_mod(settings.resolved_save_dir(), settings.data_dir, mod)
    return _out(mod, base)


@router.delete(
    "/{name}", status_code=status.HTTP_204_NO_CONTENT, responses=ERRORS, operation_id="deleteMod"
)
def delete_mod(name: str, settings: SettingsDep) -> None:
    """Delete a mod file. Saves started with it keep their own copy and play on unchanged."""
    store.delete_mod(settings.resolved_save_dir(), name)
