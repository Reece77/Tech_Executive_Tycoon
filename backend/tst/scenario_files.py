"""Custom scenario files (M52, ADR-0026, docs/formulas.md 66.2): reading, validating,
canonicalising, hashing and writing `<saves>/scenarios/<slug>.yaml`. Outside `tst.sim`: the
engine only receives the validated spec (`tst.sim.modes.custom`).

**Canonical YAML** (ADR-0026 point 4) is the spec's fields with their defaults left out, every
number as its field's type (a quality of 40 is written 40.0), keys sorted, block style, UTF-8
and LF line endings: two specs that mean the same thing have the same text. Its SHA-256 (hex)
is the scenario's hash, kept in the mode record of every game started from it; the save also
keeps the text itself (table `custom_scenario`), so editing or deleting the file later never
changes the game.

**Refusals** (point 7): text that is not YAML, a duplicate key, an unknown or mistyped field,
or a value outside its `editor.*` range is refused with every reason named; nothing is
written."""

from __future__ import annotations

import hashlib
import logging
import os
import re
import tempfile
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import ValidationError

from tst.sim.data_models import Balance, GameData
from tst.sim.errors import (
    CustomScenarioExistsError,
    InvalidCustomScenarioError,
    InvalidModeError,
    UnknownCustomScenarioError,
)
from tst.sim.modes.custom import check
from tst.sim.modes.custom_config import SLUG_PATTERN, CustomScenario

log = logging.getLogger(__name__)

SCENARIOS_DIR: Final = "scenarios"
SUFFIX: Final = ".yaml"
SLUG_RE: Final = re.compile(SLUG_PATTERN)
MAX_BYTES: Final = 256 * 1024  # an imported file's size at most (a spec is a few kB)


def scenarios_dir(save_dir: Path) -> Path:
    return save_dir / SCENARIOS_DIR


def check_slug(slug: str) -> str:
    if not SLUG_RE.match(slug):
        raise InvalidCustomScenarioError(
            "a scenario name is 1 to 48 lower-case letters, digits, - or _, starting with a"
            " letter or digit"
        )
    return slug


def scenario_path(save_dir: Path, slug: str) -> Path:
    return scenarios_dir(save_dir) / f"{check_slug(slug)}{SUFFIX}"


def slug_of(label: str) -> str:
    """A file name from a label: lower case, runs of other characters as one '-'."""
    slug = re.sub(r"[^a-z0-9]+", "-", label.lower()).strip("-")[:48].strip("-")
    return slug or "scenario"


# --- Canonical text and hash ------------------------------------------------------------------


def canonical(spec: CustomScenario) -> str:
    body = spec.model_dump(mode="json", exclude_defaults=True)
    body["format"] = spec.format  # always written, so a reader knows the format
    return yaml.safe_dump(
        body, sort_keys=True, default_flow_style=False, allow_unicode=True, width=10**6
    )


def sha256(spec: CustomScenario) -> str:
    return hashlib.sha256(canonical(spec).encode("utf-8")).hexdigest()


# --- Parsing and validation -------------------------------------------------------------------


def _pydantic_reasons(exc: ValidationError) -> list[str]:
    out = []
    for e in exc.errors():
        where = ".".join(str(p) for p in e["loc"]) or "the file"
        if e["type"] == "extra_forbidden":
            out.append(f"{where}: not a field a custom scenario can set")
        else:
            out.append(f"{where}: {e['msg']}")
    return out


def parse(text: str) -> CustomScenario:
    """The spec in `text`, its structure and types checked (not yet its ranges)."""
    from tst.loader import _UniqueKeyLoader

    if len(text.encode("utf-8")) > MAX_BYTES:
        raise InvalidCustomScenarioError(f"a scenario file has at most {MAX_BYTES:,} bytes")
    try:
        raw = yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise InvalidCustomScenarioError(f"not valid YAML: {exc}") from exc
    if not isinstance(raw, dict):
        raise InvalidCustomScenarioError("a scenario file is a YAML mapping of fields")
    return from_dict(raw)


def from_dict(raw: dict[str, Any]) -> CustomScenario:
    try:
        return CustomScenario.model_validate(raw)
    except ValidationError as exc:
        raise InvalidCustomScenarioError("; ".join(_pydantic_reasons(exc))) from exc


def validate(spec: CustomScenario, balance: Balance, data: GameData) -> CustomScenario:
    """`spec` checked against the editor's ranges and the loaded data."""
    try:
        return check(spec, balance, data)
    except InvalidModeError as exc:
        raise InvalidCustomScenarioError(str(exc)) from exc


def read_text(text: str, balance: Balance, data: GameData) -> CustomScenario:
    return validate(parse(text), balance, data)


# --- Files ------------------------------------------------------------------------------------


def read(save_dir: Path, slug: str, balance: Balance, data: GameData) -> CustomScenario:
    path = scenario_path(save_dir, slug)
    if not path.is_file():
        raise UnknownCustomScenarioError(f"no custom scenario named {slug!r}")
    spec = read_text(path.read_text(encoding="utf-8"), balance, data)
    if spec.key != slug:  # the file's own name wins (a file renamed by hand)
        spec = spec.model_copy(update={"key": slug})
    return spec


def list_specs(save_dir: Path, balance: Balance, data: GameData) -> list[CustomScenario]:
    """Every readable custom scenario, by name; an unreadable file is logged and skipped."""
    found = []
    for path in sorted(scenarios_dir(save_dir).glob(f"*{SUFFIX}")):
        if not SLUG_RE.match(path.stem):
            continue
        try:
            found.append(read(save_dir, path.stem, balance, data))
        except InvalidCustomScenarioError as exc:
            log.warning("Skipping custom scenario %s: %s", path.name, exc)
    return found


def write(
    save_dir: Path,
    spec: CustomScenario,
    balance: Balance,
    data: GameData,
    *,
    overwrite: bool,
) -> CustomScenario:
    """Validate, then write the canonical text atomically. Refused (nothing written) when
    invalid, or when the name exists and `overwrite` is off."""
    validate(spec, balance, data)
    path = scenario_path(save_dir, spec.key)
    if path.exists() and not overwrite:
        raise CustomScenarioExistsError(f"a custom scenario named {spec.key!r} already exists")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{spec.key}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as f:
            f.write(canonical(spec))
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
    return spec


def delete(save_dir: Path, slug: str) -> None:
    path = scenario_path(save_dir, slug)
    if not path.is_file():
        raise UnknownCustomScenarioError(f"no custom scenario named {slug!r}")
    path.unlink()


def import_text(
    save_dir: Path,
    text: str,
    balance: Balance,
    data: GameData,
    *,
    slug: str | None = None,
    overwrite: bool = False,
) -> CustomScenario:
    """A shared file read, validated and saved (under `slug`, else its own name)."""
    spec = parse(text)
    if slug is not None:
        spec = spec.model_copy(update={"key": check_slug(slug)})
    return write(save_dir, spec, balance, data, overwrite=overwrite)


def export_text(save_dir: Path, slug: str, balance: Balance, data: GameData) -> str:
    """The canonical text to share (ADR-0026 point 7)."""
    return canonical(read(save_dir, slug, balance, data))
