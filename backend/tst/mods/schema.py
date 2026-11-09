"""What the Data editor shows (M25 section 3): the editable files, a form spec generated from
each file's loader schema (its Pydantic models), and each field's comment from the YAML.

Files the loader adds later (M17's and M18's) appear automatically: every data file the
loader reads is editable unless it is listed below as not editable, and a file without a
known model gets a spec inferred from its values (the loader still validates the result)."""

from __future__ import annotations

import re
import types
import typing
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml
from pydantic import BaseModel, create_model

from tst import loader
from tst.mods.hidden import strip, strip_spec, withheld
from tst.sim import data_models as dm
from tst.sim.modes.config import HistoricalScenario

LABELS: Final = {
    loader.INCUMBENTS_FILE: "Rivals (incumbents)",
    loader.ENTRANTS_FILE: "Rival entrants",
    loader.CATEGORIES_FILE: "Categories and segments",
    loader.CITIES_FILE: "Cities",
    loader.SCENARIOS_FILE: "Scenarios",
    loader.BALANCE_FILE: "Balance values",
}
# The brief's editable files first, in this order; then any file the loader adds later.
FEATURED: Final = tuple(LABELS)
# Files that exist today and are not offered: game structure rather than tuning (accounts,
# names, templates, skills, histories), which a mod should not change.
NOT_EDITABLE: Final = frozenset(
    {
        loader.ACCOUNTS_FILE,
        loader.BACKGROUNDS_FILE,
        loader.BANKS_FILE,
        loader.COMPONENTS_FILE,
        loader.COMPUTE_INDEX_FILE,
        loader.ERAS_FILE,
        loader.VOICES_FILE,
        loader.INBOX_FILE,
        loader.INVESTORS_FILE,
        loader.INTERESTS_FILE,
        loader.MACRO_HISTORY_FILE,
        loader.NAMES_FILE,
        loader.PERSONALITY_FILE,
        loader.REGIONS_FILE,
        loader.ROLES_FILE,
        loader.SKILLS_FILE,
        loader.TAGS_FILE,
        loader.TECH_FILE,
    }
)

_ScenariosFile = create_model(
    "ScenariosFile",
    scenarios=(tuple[dm.Scenario, ...], ...),
    historical=(tuple[HistoricalScenario, ...], ()),
)
MODELS: Final[dict[str, type[BaseModel]]] = {
    loader.INCUMBENTS_FILE: dm.IncumbentsFile,
    loader.ENTRANTS_FILE: dm.EntrantsFile,
    loader.CATEGORIES_FILE: dm.CategoriesFile,
    loader.CITIES_FILE: dm.CitiesFile,
    loader.SCENARIOS_FILE: _ScenariosFile,
    loader.BALANCE_FILE: dm.Balance,
}
MAX_DEPTH: Final = 12  # nesting levels a spec follows


def editable_files() -> list[str]:
    rest = sorted(f for f in loader.DATA_FILES if f not in NOT_EDITABLE and f not in FEATURED)
    return [f for f in FEATURED if f in loader.DATA_FILES] + rest


def label(file: str) -> str:
    return LABELS.get(file, file.removesuffix(".yaml").replace("_", " ").capitalize())


# --- form specs --------------------------------------------------------------------------------


def _strip_optional(t: Any) -> tuple[Any, bool]:
    if typing.get_origin(t) in (typing.Union, types.UnionType):
        args = [a for a in typing.get_args(t) if a is not type(None)]
        nullable = len(args) < len(typing.get_args(t))
        if len(args) == 1:
            return args[0], nullable
        return t, nullable
    return t, False


def _resolve(t: Any) -> Any:
    """A `type X = ...` alias resolves to its value."""
    value = getattr(t, "__value__", None)
    return _resolve(value) if value is not None else t


def spec_of(t: Any, depth: int = 0) -> dict[str, Any]:
    """A form spec for a type: kind object/list/map/number/integer/string/boolean/enum/any,
    with fields, item, value or options as the kind needs."""
    t = _resolve(t)
    t, nullable = _strip_optional(t)
    t = _resolve(t)
    out: dict[str, Any]
    origin = typing.get_origin(t)
    if depth > MAX_DEPTH:
        out = {"kind": "any"}
    elif isinstance(t, type) and issubclass(t, BaseModel):
        out = {
            "kind": "object",
            "fields": [
                {
                    "name": name,
                    "description": info.description,
                    "required": info.is_required(),
                    "spec": spec_of(info.annotation, depth + 1),
                }
                for name, info in t.model_fields.items()
            ],
        }
    elif origin in (tuple, list, frozenset, set):
        args = [a for a in typing.get_args(t) if a is not Ellipsis]
        item = args[0] if args else Any
        out = {"kind": "list", "item": spec_of(item, depth + 1)}
    elif origin is dict:
        kv = typing.get_args(t)
        out = {"kind": "map", "value": spec_of(kv[1] if len(kv) == 2 else Any, depth + 1)}
    elif origin is typing.Literal:
        out = {"kind": "enum", "options": [str(a) for a in typing.get_args(t)]}
    elif t is bool:
        out = {"kind": "boolean"}
    elif t is int:
        out = {"kind": "integer"}
    elif t is float:
        out = {"kind": "number"}
    elif t is str:
        out = {"kind": "string"}
    elif origin in (typing.Union, types.UnionType):
        out = {"kind": "any"}
    else:
        out = {"kind": "any"}
    if nullable:
        out["nullable"] = True
    return out


def spec_from_value(value: Any, depth: int = 0) -> dict[str, Any]:
    """A spec inferred from data, for a file without a known model."""
    if depth > MAX_DEPTH:
        return {"kind": "any"}
    if isinstance(value, bool):
        return {"kind": "boolean"}
    if isinstance(value, int):
        return {"kind": "integer"}
    if isinstance(value, float):
        return {"kind": "number"}
    if isinstance(value, str):
        return {"kind": "string"}
    if isinstance(value, dict):
        return {
            "kind": "object",
            "fields": [
                {"name": str(k), "description": None, "required": True, "spec": spec_from_value(v)}
                for k, v in value.items()
            ],
        }
    if isinstance(value, list):
        return {"kind": "list", "item": spec_from_value(value[0], depth + 1) if value else {}}
    return {"kind": "any"}


def file_spec(file: str, value: Any) -> dict[str, Any]:
    model = MODELS.get(file)
    return spec_of(model) if model is not None else spec_from_value(value)


# --- comments ---------------------------------------------------------------------------------

_KEY_LINE = re.compile(r"^(\s*)(- )?([A-Za-z0-9_]+):(.*)$")
_DOC_LINE = re.compile(r"^#\s*-\s*([a-z_][a-z0-9_]*)(?:\s*\([^)]*\))?:\s*(.+)$")


def _inline_comment(rest: str) -> str | None:
    """The comment after a value, ignoring # inside quotes."""
    quote = None
    for n, ch in enumerate(rest):
        if ch in "'\"":
            quote = None if quote == ch else (ch if quote is None else quote)
        elif ch == "#" and quote is None and (n == 0 or rest[n - 1] == " "):
            return rest[n + 1 :].strip() or None
    return None


def comments(text: str) -> dict[str, str]:
    """Each field's comment: `a.b.c` for an inline comment on a block-style key (list items
    as `[]`), and `field:<name>` for a "# - name: text" line in a file's header notes."""
    out: dict[str, str] = {}
    stack: list[tuple[int, str]] = []
    doc_key: str | None = None
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if m := _DOC_LINE.match(stripped):
                doc_key = m.group(1)
                out.setdefault(f"field:{doc_key}", m.group(2).strip())
            elif doc_key is not None and stripped.startswith("#  "):
                out[f"field:{doc_key}"] += " " + stripped.lstrip("# ").strip()
            else:
                doc_key = None
            continue
        doc_key = None
        m = _KEY_LINE.match(line)
        if not m:
            continue
        indent = len(m.group(1))
        if m.group(2):  # "- key:" starts a list item one level in
            while stack and stack[-1][0] >= indent:
                stack.pop()
            stack.append((indent, "[]"))
            indent += 2
        while stack and stack[-1][0] >= indent:
            stack.pop()
        key = m.group(3)
        path = ".".join([s for _, s in stack] + [key])
        if note := _inline_comment(m.group(4)):
            out[path] = note
        stack.append((indent, key))
    return out


@dataclass(frozen=True, slots=True)
class EditorFile:
    file: str
    label: str
    spec: dict[str, Any]
    base: Any
    comments: dict[str, str]


def editor_file(data_dir: Path, file: str) -> EditorFile:
    """One file for the editor, with every withheld field left out (tst.mods.hidden)."""
    text = (data_dir / file).read_text(encoding="utf-8")
    base = yaml.safe_load(text)
    notes = {
        k: v
        for k, v in comments(text).items()
        if not any(withheld(part) for part in k.removeprefix("field:").split("."))
    }
    return EditorFile(file, label(file), strip_spec(file_spec(file, base)), strip(base), notes)
