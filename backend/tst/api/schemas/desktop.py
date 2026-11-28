"""The desktop build's routes (M58): health, status, the API key, import and update."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class HealthOut(BaseModel):
    status: Literal["ok"] = "ok"
    version: str = Field(description="The build's version; dev when run from the repository")


class ImportOfferOut(BaseModel):
    folder: str = Field(description="The repository saves folder found on this computer")
    saves: list[str] = Field(description="Saves there that the game's own folder lacks")


class UpdateOut(BaseModel):
    version: str
    notes: str = Field(description="What's new: the release notes, from CHANGELOG")
    page_url: str
    size_bytes: int


class DesktopOut(BaseModel):
    desktop: bool = Field(description="False outside the installed game (make dev, launcher)")
    version: str
    saves_dir: str | None = None
    key_saved: bool = Field(default=False, description="An API key is stored; never the key")
    import_offer: ImportOfferOut | None = None
    update_state: Literal[
        "none", "checking", "available", "downloading", "backing_up", "installing", "failed"
    ] = "none"
    update: UpdateOut | None = None
    update_message: str = ""
    backup_folder: str | None = None
    write_token: str | None = Field(
        default=None,
        description="M57r-B: sent back as X-TST-Instance on the desktop routes' writes. Only "
        "the game's own page can read it (the local API refuses foreign hosts)",
    )


class ApiKeyIn(BaseModel):
    key: str = Field(default="", max_length=400, description="Empty removes the stored key")


class ImportIn(BaseModel):
    accept: bool = Field(description="True copies the saves; false never asks again")


class ImportOut(BaseModel):
    imported: list[str]
