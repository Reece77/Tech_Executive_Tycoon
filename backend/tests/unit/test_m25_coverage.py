"""M25 sub-task 1 (breakdowns everywhere): every numeric field the main screens' schemas
send has an Explain metric or is exempt with a reason, as M15b's glossary audit does for
tooltips. A new number on these screens has to choose."""

from __future__ import annotations

import importlib
import types
import typing

from pydantic import BaseModel

from tst.advisor.coverage import EXEMPT, SCREEN_FIELDS
from tst.advisor.metrics import METRICS


def _numeric(t: object) -> bool:
    if typing.get_origin(t) in (typing.Union, types.UnionType):
        return any(_numeric(a) for a in typing.get_args(t) if a is not type(None))
    return t in (int, float)


def _skip(field: str) -> bool:
    return field in ("id", "turn", "year") or field.endswith(("_id", "_turn"))


def _model(path: str) -> type[BaseModel]:
    module, name = path.split(".")
    cls = getattr(importlib.import_module(f"tst.api.schemas.{module}"), name)
    assert isinstance(cls, type) and issubclass(cls, BaseModel)
    return cls


def test_every_main_screen_number_has_a_breakdown_or_an_exemption() -> None:
    missing: dict[str, list[str]] = {}
    for path, fields in SCREEN_FIELDS.items():
        numbers = {f for f, info in _model(path).model_fields.items() if _numeric(info.annotation)}
        if gap := sorted(f for f in numbers if not _skip(f) and f not in fields):
            missing[path] = gap
        assert set(fields) <= numbers, f"{path}: mapped fields that are not numbers"
    assert missing == {}, f"map these to a metric or exempt them with a reason: {missing}"


def test_every_mapping_names_a_metric_or_a_reason() -> None:
    for path, fields in SCREEN_FIELDS.items():
        for field, covered in fields.items():
            if covered.startswith(EXEMPT):
                assert len(covered) > len(EXEMPT) + 10, f"{path}.{field}: give a reason"
            else:
                assert covered in METRICS, f"{path}.{field}: unknown metric {covered!r}"


def test_every_metric_explains_something_on_a_screen() -> None:
    used = {c for fields in SCREEN_FIELDS.values() for c in fields.values()}
    assert set(METRICS) - used == set()
