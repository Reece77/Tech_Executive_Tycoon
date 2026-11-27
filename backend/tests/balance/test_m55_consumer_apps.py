"""M55 sub-task 2 (formulas.md 65.1, 65.8 target 1): `consumer_apps` before 2026 is identical to
`main`'s. tests/fixtures/m55_consumer_apps.json was recorded on main at 139979f (before M55) by
tools/m55_consumer_apps.py: every consumer_apps line's customers, prices, quality and brand and the
market's size, each month to December 2025, hashed by year, on seeds 1-3. Ad pricing is opt-in and
only from 2026, so nothing here may move."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest

from tst.sim.calendar import ym_to_turn

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / "backend" / "tests" / "fixtures" / "m55_consumer_apps.json"


def _tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("m55_ca", ROOT / "tools" / "m55_consumer_apps.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_consumer_apps_to_2012_is_mains() -> None:
    want = json.loads(FIXTURE.read_text())["1"]
    got = _tool().fingerprint(1, last_turn=ym_to_turn(2012, 12))
    assert got == {y: h for y, h in want.items() if int(y) <= 2012}  # tunable-exempt: a year


@pytest.mark.nightly
@pytest.mark.parametrize("seed", [1, 2, 3])
def test_consumer_apps_before_2026_is_mains(seed: int) -> None:
    want = json.loads(FIXTURE.read_text())[str(seed)]
    assert _tool().fingerprint(seed) == want
