"""Create and edit saves for the M42 Playwright flows and the practice save (an e2e fixture tool).
Never used by the game.

Every mode plays 2010 to January 2026 with the engine (a do-nothing Helix, so the world is
history's), then gives Helix a stage-3 AI and devices business: an AI model (quality 85, live,
so AI discovery is ready), a smartwatch, an ML research team (research scientists and data
scientists) and $5B of funding.

- `pharma <save dir> <name>` (the practice save `pt-pharma`): as above, with no programme yet
  (flow a starts one with AI discovery).
- `phase2 <save dir> <name>`: as `pharma` plus a programme (`HX-201`, obesity) whose Phase II
  reads out this month with a weak molecule: the next Continue brings a failed readout (flow b
  redesigns or stops it). The tool plays the readout itself first and checks it fails.
- `cliff <save dir> <name>`: as `pharma` plus a marketed small molecule (`Helixor`, thrombosis)
  approved everywhere, whose exclusivity ended in every region 18 months ago, with its drug
  months played through its loss of exclusivity (flow c reads its revenue before and after).

Usage: uv run --project backend python tools/e2e_m42_save.py <mode> <save dir> <name>
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

from e2e_m31_save import _new, _write
from tst.balance import fixtures
from tst.balance.game import Game, start_game
from tst.config import Settings
from tst.db.repository import create_save, ledger_balances, open_session
from tst.loader import LoadedData, load_all
from tst.sim.ledger import CASH
from tst.sim.pharma import data as pd
from tst.sim.pharma import demand, pipeline
from tst.sim.pharma.models import Authorisation, Drug, Hta, Programme
from tst.sim.products.models import ProductSegment
from tst.sim.rng import RngFactory
from tst.sim.state import GameState, with_product, with_product_segment

SEED: Final = 42
COMPANY: Final = "Helix"
JAN_2026: Final = 192
FUNDING: Final = 5_000_000_000_00  # $5B (the brief's practice save)
AI_QUALITY: Final = 85.0
TEAM: Final = (("research_scientist", 12, "ML research"), ("data_scientist", 8, "ML research"))


def _played(data: LoadedData) -> Game:
    game = start_game(data, SEED, "funded_spinout")
    game.state = replace(game.state, companies=tuple(
        replace(c, name=COMPANY) if c.is_player else c for c in game.state.companies
    ))  # fmt: skip
    while game.state.turn < JAN_2026:
        game.turn()
    cash = (game.state.player.id, CASH)
    game.balances = {**game.balances, cash: game.balances.get(cash, 0) + FUNDING}
    return game


def _business(state: GameState, data: LoadedData) -> GameState:
    for category, name, price, quality in (
        ("ai_models", "Helix Mind", 10_000, AI_QUALITY),
        ("devices", "Helix Band", 30_000, 70.0),
    ):
        state, pid = _new(state, data, category, name, live=True, feature=70)
        product = state.product(pid)
        assert product is not None
        state = with_product(state, replace(product, quality=quality))
        segment = data.game_data.category(category).markets[0].segment
        state = with_product_segment(state, ProductSegment(pid, segment, price, 0.0))
    return state


def _phase2(state: GameState, data: LoadedData) -> GameState:
    """A weak molecule whose Phase II reads out now; checked to fail on this seed."""
    b, d = data.balance, data.game_data
    t = state.turn
    p = Programme(
        id=1, company_id=state.player.id, name="HX-201", indication="obesity",
        area="metabolic", modality="small_molecule", stage="phase1", start_turn=t - 60,
        due_turn=t - 30, efficacy=0.05, safety=0.3, status="ready", obs_n=1, obs_eff=0.52,
        obs_safety=0.68, patent_turn=t - 90, ind_turn=t - 60,
    )  # fmt: skip
    p = pipeline.begin_stage(replace(state, turn=t - 40), p, "phase2", "standard", b, d)
    p = replace(p, due_turn=t, spent_cents=p.cost_cents)
    probe = replace(state, pharma_programmes=(p,))
    after, _ = pipeline.read_out(probe, p, RngFactory(state.save_meta.master_seed), b, d)
    if after.pharma_readouts[-1].success:
        raise SystemExit("the fixture's Phase II succeeded on this seed: choose another molecule")
    return replace(state, pharma_programmes=(p,))


def _cliff(state: GameState, data: LoadedData) -> GameState:
    """A marketed blockbuster past its exclusivity everywhere, its months played."""
    b, d = data.balance, data.game_data
    t = state.turn
    approved = t - 17 * pd.MONTHS
    p = Programme(
        id=1, company_id=state.player.id, name="Helixor", indication="thrombosis",
        area="cardiovascular", modality="small_molecule", stage="approved",
        start_turn=approved, due_turn=approved, efficacy=0.8, safety=0.7, status="marketed",
        obs_n=3, obs_eff=0.8, obs_safety=0.7, patent_turn=approved - 6 * pd.MONTHS,
        ind_turn=approved - 5 * pd.MONTHS, filed_turn=approved - pd.MONTHS,
        approved_turn=approved,
    )  # fmt: skip
    rows = [Authorisation(1, r.key, r.region, approved) for r in pd.regulators(d)]
    rows += [
        Authorisation(1, pd.RELY + region, region, approved)
        for region in d.region_keys
        if pd.reliance_share(d, region) > 0
    ]
    hta = tuple(
        Hta(1, r.region, approved, approved, "covered", approved)
        for r in pd.file(d).pricing.regions
        if r.hta
    )
    ind = pd.indication(d, "thrombosis")
    state = replace(
        state,
        pharma_programmes=(p,),
        pharma_authorisations=tuple(rows),
        pharma_drugs=(Drug(1, round(ind.price_year * pd.CENTS), 1.0, approved),),
        pharma_hta=hta,
    )
    ends = [pd.loe_turn(state, p, region, d) for region in d.region_keys]
    last = max(e for e in ends if e is not None)
    assert last <= t - 18, "exclusivity must have ended 18 months ago"
    months = []
    for turn in range(t - 60, t):
        s, _, _ = demand.month(replace(state, turn=turn, pharma_months=()), b, d)
        months += list(s.pharma_months)
    return replace(state, pharma_months=tuple(months[-b.pharma.history_months :]))


def make(save_dir: Path, name: str, data: LoadedData, mode: str) -> Path:
    path = create_save(
        name, SEED, "funded_spinout", company_name=COMPANY, data=data, save_dir=save_dir
    )
    with open_session(path) as session:
        start = dict(ledger_balances(session))
    game = _played(data)
    state = _business(game.state, data)
    if mode == "phase2":
        state = _phase2(state, data)
    elif mode == "cliff":
        state = _cliff(state, data)
    _write(path, state, game.balances, start)
    fixtures.finish(path, data, team=True, specialists=TEAM, stage=3)
    return path


def main(argv: list[str]) -> int:
    modes = ("pharma", "phase2", "cliff")
    if len(argv) != 4 or argv[1] not in modes:
        print(__doc__)
        return 2
    data = load_all(Settings().data_dir)
    print(make(Path(argv[2]), argv[3], data, argv[1]))
    return 0


if __name__ == "__main__":
    import e2e_cache  # M59: CI keeps the saves it builds (tools/e2e_cache.py)

    sys.exit(e2e_cache.run(__file__, sys.argv[1:], lambda: main(sys.argv)))
