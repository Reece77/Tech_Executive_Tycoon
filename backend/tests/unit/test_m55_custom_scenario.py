"""M52's brief (decision for the lane that merges last): a custom-scenario round trip that uses
a category from M54 or M55. Here M55's media: a platform-war start whose spec edits two media
rivals (Spotify removed, Netflix with twice its opening cash) is written to a file, read back with
the same hash, and plays identically from the file as from the spec; the media markets follow
media.yaml every month, so a media market override is refused (custom.computed_markets)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tst import scenario_files as sf
from tst.balance import m52
from tst.balance.game import Game
from tst.loader import LoadedData
from tst.sim.errors import InvalidCustomScenarioError
from tst.sim.ledger import CASH
from tst.sim.modes import custom
from tst.sim.modes.custom_config import CustomScenario

MONTHS = 12


def _spec(loaded: LoadedData, **markets: dict[str, float]) -> CustomScenario:
    h = loaded.game_data.historical_scenario("platform_war")
    assert h is not None
    raw = custom.from_historical(h).model_dump(mode="json")
    raw["key"] = "media-round-trip"
    raw["overrides"] = {
        "rivals": {"Spotify": {"present": False}, "Netflix": {"cash_mult": 2.0}},
        "markets": markets,
    }
    return sf.validate(sf.from_dict(raw), loaded.balance, loaded.game_data)


def _company(game: Game, name: str) -> int:
    return next(c.id for c in game.state.companies if c.name == name)


def test_a_media_edit_round_trips_through_a_file(tmp_path: Path, loaded: LoadedData) -> None:
    b, d = loaded.balance, loaded.game_data
    spec = _spec(loaded)
    sf.write(tmp_path, spec, b, d, overwrite=False)
    back = sf.import_text(
        tmp_path / "copy", sf.export_text(tmp_path, spec.key, b, d), b, d, slug=spec.key
    )
    assert sf.sha256(back) == sf.sha256(spec)
    assert sf.read(tmp_path, spec.key, b, d) == spec

    edited = m52.start_custom(loaded, spec, 5)
    original = m52.start_historical(loaded, "platform_war", 5)
    spotify = _company(edited, "Spotify")
    assert edited.state.company(spotify).failed_turn == edited.state.turn
    netflix_e, netflix_o = _company(edited, "Netflix"), _company(original, "Netflix")
    assert edited.balances[(netflix_e, CASH)] == 2 * original.balances[(netflix_o, CASH)]

    a = m52.month_digests(edited, MONTHS)
    c = m52.month_digests(m52.start_custom(loaded, back, 5), MONTHS)
    assert len(a) == MONTHS + 1 and a == c


@pytest.mark.parametrize("category", ["streaming", "music_streaming", "games", "social"])
def test_a_media_market_cannot_be_edited(loaded: LoadedData, category: str) -> None:
    assert category in custom.computed_markets(loaded.balance)
    with pytest.raises(InvalidCustomScenarioError, match="follows its own data"):
        _spec(loaded, **{category: {"market_mult": 1.5}})
