"""M23c sub-task 9: every practice-save mode opens People and Org.

Each fixture tool in tools/e2e_*_save.py is run as Reece runs it (its command line, in
process), and the save's People, Org and main screen are opened through the API, with a
person's profile. Playtest 5 found fixtures whose hand-built staff had no knowledge record, so
People and Org failed ("no person 2"). The v3 tools (M18-M22) also give stage-3 saves a
believable team (tst.balance.fixtures): checked here as a CTO, product and sales staff.

Modes that edit an existing save (advance, ripen, drain, ...) are left out: they need one of
the modes here first."""

from __future__ import annotations

import importlib
import sys
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType

import pytest
from fastapi.testclient import TestClient

from tests.integration.test_api_hiring import Client
from tst.api.app import create_app
from tst.config import Settings, get_settings

TOOLS = Path(__file__).resolve().parents[3] / "tools"

# (tool, mode or None for a tool without modes, main screen, prog: main takes sys.argv whole)
V3 = [
    ("e2e_m18_save", m, "/exploration", True)
    for m in ("explorer", "sampled", "protest", "permitted")
] + [
    *[("e2e_m19_save", m, "/mines", True) for m in ("holder", "building", "crash", "accident")],
    *[("e2e_m20_save", m, "/refineries", True) for m in ("smelter", "wafers", "curb", "gallium")],
    *[("e2e_m21_save", m, "/fabs", True) for m in ("nodes", "mature", "euv", "slots", "chipfab")],
    *[("e2e_m22_save", m, "/world", True) for m in ("chips", "gallium", "influence")],
]
OLDER = [
    ("e2e_approach_save", None, "/overview", False),
    ("e2e_event_save", None, "/events", False),
    ("e2e_series_a_save", None, "/finance/summary", False),
    *[("e2e_m8_save", m, "/org", False) for m in ("stage3",)],
    *[("e2e_m9_save", m, "/geo", False) for m in ("geo", "small")],
    *[("e2e_m10_save", m, "/overview", False) for m in ("spinout", "breach")],
    *[("e2e_m10c_save", m, "/scaleup", False) for m in ("cro", "cfo")],
    *[("e2e_m11_save", m, "/research", False) for m in ("lab", "ahead", "rival")],
    *[("e2e_m12a_save", m, "/infrastructure", False) for m in ("product", "cloud", "outage")],
    *[("e2e_m12b_save", m, "/hardware", False) for m in ("device", "live_device", "chip")],
    *[("e2e_m13_save", m, "/overview", False) for m in ("eligible", "listed", "miss")],
    *[("e2e_m13b_save", m, "/scaleup", False) for m in ("cpo", "holiday")],
    *[("e2e_m14_save", m, "/overview", False) for m in ("startup", "blocked", "exit")],
    *[("e2e_m14b_save", m, "/overview", False) for m in ("launch", "layoffs", "jab", "poached")],
    *[("e2e_m15b_save", m, "/overview", False) for m in ("deadline", "december", "pitch")],
    *[("e2e_m16_save", m, "/group", False) for m in ("eligible", "formed", "complaint")],
    *[("e2e_m17_save", m, "/commodities", False) for m in ("y2023", "device2020", "power")],
    *[("e2e_m24_save", m, "/overview", False) for m in ("fresh", "december", "over")],
    *[("e2e_m25_save", m, "/overview", False) for m in ("ready", "live")],
    *[("e2e_m26_save", m, "/founder/investments", False) for m in ("rounds", "leaver", "dividend")],
]


def _tool(name: str) -> ModuleType:
    if str(TOOLS) not in sys.path:
        sys.path.insert(0, str(TOOLS))
    return importlib.import_module(name)


@pytest.fixture
def saves(tmp_path: Path) -> Path:
    return tmp_path / "saves"


@pytest.fixture
def api(saves: Path) -> Iterator[Client]:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(save_dir=saves)
    with TestClient(app) as client:
        yield Client(client)


def _build(saves: Path, tool: str, mode: str | None, prog: bool) -> str:
    name = f"{tool[4:-5]}-{mode or 'save'}".replace("_", "-")
    args = [mode] if mode else []
    argv = [*args, str(saves), name]
    code = _tool(tool).main([f"{tool}.py", *argv] if prog else argv)
    assert code == 0, f"{tool} {mode} exited {code}"
    return name


def _opens(api: Client, name: str, screen: str) -> list[dict[str, object]]:
    base = f"/api/saves/{name}"
    people = api.get(f"{base}/people")
    assert people, f"{name}: People is empty"
    api.get(f"{base}/org")
    api.get(f"{base}{screen}")
    api.get(f"{base}/people/{people[-1]['person_id']}")  # the newest hire's profile
    return list(people)


@pytest.mark.parametrize(("tool", "mode", "screen", "prog"), V3)
def test_every_v3_practice_save_opens_people_and_org_with_a_team(
    api: Client, saves: Path, tool: str, mode: str | None, screen: str, prog: bool
) -> None:
    name = _build(saves, tool, mode, prog)
    people = _opens(api, name, screen)
    roles = {p["role"] for p in people}
    assert {"product_manager", "sales_representative", "software_engineer"} <= roles, roles
    org = api.get(f"/api/saves/{name}/scaleup")
    cto = next((s for s in org["seats"] if s["seat"] == "cto"), None)
    assert cto is not None and cto["holder_id"] is not None, "no CTO appointed"


# The 49 pre-v3 modes take about 30 CPU-minutes to build: `make check` and the nightly CI run
# them; CI's `check` runs the v3 ones above (M23c decision, see the brief).
@pytest.mark.nightly
@pytest.mark.parametrize(("tool", "mode", "screen", "prog"), OLDER)
def test_every_older_practice_save_opens_people_and_org(
    api: Client, saves: Path, tool: str, mode: str | None, screen: str, prog: bool
) -> None:
    _opens(api, _build(saves, tool, mode, prog), screen)


def test_the_chip_company_makes_its_own_chips(api: Client, saves: Path) -> None:
    name = _build(saves, "e2e_m21_save", "chipfab", True)
    base = f"/api/saves/{name}"
    api.post(f"{base}/advance")  # the fab's first production month
    fab = api.get(f"{base}/fabs")["fabs"][0]
    assert fab["chips"], "the fab supplies none of its own chips"
    hardware = api.get(f"{base}/hardware")
    assert [c["name"] for c in hardware["chips"]] == ["Lithos SoC"]
