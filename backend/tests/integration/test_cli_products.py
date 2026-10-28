"""M3a CLI: the brief's manual check, automated (products, launch, market, price, scout)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tests.integration.test_api_products import staff
from tst.cli import app
from tst.db.repository import create_save
from tst.loader import LoadedData

runner = CliRunner()
SAVE = "cliprod"
MAX_TURNS = 14


@pytest.fixture
def save_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, loaded: LoadedData) -> Path:
    path = tmp_path / "saves"
    monkeypatch.setenv("TST_SAVE_DIR", str(path))
    save = create_save(SAVE, 9, "funded_spinout", company_name="Cli Co", data=loaded, save_dir=path)
    staff(save, loaded, ("software_engineer",) * 3)
    return path


def run(*args: str, code: int = 0) -> str:
    result = runner.invoke(app, list(args))
    assert result.exit_code == code, result.output
    return result.output


def new_customers(out: str) -> float:
    """New customers in the newest history line of `tst product show`."""
    found = re.findall(r"customers [\d,]+ \(\+([\d,.]+) /", out)
    assert found, out
    return float(found[-1].replace(",", ""))


def test_manual_check_flow(save_dir: Path) -> None:
    out = run(
        "product", "create", "--save", SAVE, "--name", "Pipeline",
        "--category", "b2b_saas", "--segments", "smb",
    )  # fmt: skip
    assert "Pipeline" in out and "In development" in out and "energy 56/60" in out
    assert "Pipeline" in run("products", "--save", SAVE)
    run("product", "assign", "--save", SAVE, "--product", "13")
    out = run("product", "launch", "--save", SAVE, "--product", "13", code=1)
    assert "cannot launch yet" in out and "a price for SMB" in out
    run("product", "price", "--save", SAVE, "--product", "13", "--segment", "smb", "--price", "40")

    for _ in range(MAX_TURNS):
        if "Ready to launch" in run("product", "show", "--save", SAVE, "--product", "13"):
            break
        run("advance", "--save", SAVE)
    show = run("product", "show", "--save", SAVE, "--product", "13")
    assert "Ready to launch" in show and "builders:" in show
    assert "Live" in run("product", "launch", "--save", SAVE, "--product", "13")

    run("advance", "--save", SAVE, "--turns", "3")
    market = run("market", "--save", SAVE, "--category", "b2b_saas")
    assert "Sales Cloud" in market and "Zoho CRM" in market
    assert re.search(r"\* Pipeline\s+Cli Co", market), market
    before = new_customers(run("product", "show", "--save", SAVE, "--product", "13"))
    preview = run(
        "product", "price", "--save", SAVE, "--product", "13",
        "--segment", "smb", "--price", "30", "--preview",
    )  # fmt: skip
    assert "At $30.00: price score 83.3" in preview and "share*" in preview
    run("product", "price", "--save", SAVE, "--product", "13", "--segment", "smb", "--price", "30")
    run("advance", "--save", SAVE)
    after = new_customers(run("product", "show", "--save", SAVE, "--product", "13"))
    assert after > 0 and before > 0
    assert "MRR:" in run("inspect", "--save", SAVE)

    run("product", "marketing", "--save", SAVE, "--product", "13", "--budget", "10000")
    run("product", "segment", "--save", SAVE, "--product", "13", "--segment", "mid_market")
    run("product", "unassign", "--save", SAVE, "--product", "13")
    assert "Sunset" in run("product", "sunset", "--save", SAVE, "--product", "13")


def test_cancel_a_product_in_development(save_dir: Path) -> None:
    run(
        "product", "create", "--save", SAVE, "--name", "Sentinel",
        "--category", "cybersecurity", "--segments", "smb",
    )  # fmt: skip
    run("product", "assign", "--save", SAVE, "--product", "13")
    out = run("product", "sunset", "--save", SAVE, "--product", "13", code=1)
    assert "cancel its development instead" in out
    out = run("product", "cancel", "--save", SAVE, "--product", "13")
    assert "Cancelled Sentinel; energy 51/60" in out
    assert "No products" in run("products", "--save", SAVE)
    assert "no product 13" in run("product", "cancel", "--save", SAVE, "--product", "13", code=1)


def test_scout_a_search(save_dir: Path) -> None:
    run("search", "open", "--save", SAVE, "--role", "designer", "--channel", "network")
    run("advance", "--save", SAVE)
    out = run("scout", "--save", SAVE, "--search", "1")
    assert re.search(r"Scouted \d+ candidates; energy 40/60", out), out
    assert "no search 99" in run("scout", "--save", SAVE, "--search", "99", code=1)
