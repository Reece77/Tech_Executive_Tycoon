"""M15b sub-task 7 (glossary and History audit): every numeric field the API sends to a v2
screen (M8-M15b schemas) has a glossary entry, so every number has its tooltip (spec 13).

A field is covered by the glossary key of its own name, `field.<name>`, or its name without a
unit suffix (_cents, _pct, _bp, _months); `*_energy` fields by `energy_cost`. Ids and dates
(`id`, `*_id`, `turn`, `*_turn`, `year`) are not numbers a player reads."""

from __future__ import annotations

import importlib
import re
import types
import typing

from pydantic import BaseModel

from tst.loader import LoadedData

V2_SCHEMAS = (
    "scaleup",  # M8
    "geo",  # M9
    "capital",  # M10
    "research",  # M11
    "facilities",  # M12a
    "hardware",  # M12b
    "public",  # M13
    "mna",  # M14
    "press",  # M14b
    "modes",  # M15b
    "exploration",  # M18 (v3)
)
SUFFIX = re.compile(r"_(cents|pct|bp|months)$")


def _numeric(t: object) -> bool:
    if typing.get_origin(t) in (typing.Union, types.UnionType):
        return any(_numeric(a) for a in typing.get_args(t) if a is not type(None))
    return t in (int, float)


def numeric_fields() -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for name in V2_SCHEMAS:
        mod = importlib.import_module(f"tst.api.schemas.{name}")
        for cls_name, cls in vars(mod).items():
            if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
                continue
            if cls.__module__ != mod.__name__:
                continue
            for field, info in cls.model_fields.items():
                if _numeric(info.annotation):
                    out.setdefault(field, set()).add(f"{name}.{cls_name}")
    return out


def covered(field: str, keys: set[str]) -> bool:
    if field in ("id", "turn", "year") or field.endswith(("_id", "_turn")):
        return True
    if field == "energy" or field.endswith("_energy"):
        return "energy_cost" in keys
    return bool({field, f"field.{field}", SUFFIX.sub("", field)} & keys)


def test_every_v2_number_has_a_glossary_entry(loaded: LoadedData) -> None:
    keys = set(loaded.glossary)
    missing = {f: sorted(w) for f, w in numeric_fields().items() if not covered(f, keys)}
    assert missing == {}, f"add glossary entries (field.<name>) for: {missing}"


def test_the_audit_scans_real_fields() -> None:
    fields = numeric_fields()
    assert {"score", "combined_share", "royalty_pct"} <= set(fields)
    assert not covered("not_a_field_ever", set())


def test_every_event_type_writes_a_history_line_or_is_a_notice() -> None:
    """Every inbox kind is a History line (17.2) or a named routine notice, never neither:
    a new v2 event type has to choose."""
    from tst.api.history_views import CATEGORIES, INBOX_CATEGORY, NOT_HISTORY
    from tst.sim.data_models import INBOX_TEMPLATE_KEYS

    keys = set(INBOX_TEMPLATE_KEYS)
    assert keys - set(INBOX_CATEGORY) - NOT_HISTORY == set()
    assert not (set(INBOX_CATEGORY) & NOT_HISTORY)
    assert set(INBOX_CATEGORY.values()) <= set(CATEGORIES)
