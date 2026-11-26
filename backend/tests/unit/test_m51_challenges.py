"""M51 sub-tasks 2-3 (formulas.md 63.2-63.3): each challenge rule refuses its actions with the
rule named, multiplies the score, and changes nothing in a game without it; the results file
keeps one record a scenario save, and the best is a win, then the higher adjusted score."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from tests.helpers import DEFAULT_FOUNDER
from tst.loader import LoadedData
from tst.profile import results as kept
from tst.sim.actions import (
    AcceptBridge,
    CreateProduct,
    LaunchInRegion,
    RaiseSafe,
    SetAuthority,
    StartRound,
    apply_action,
)
from tst.sim.automation.actions import SetAreaOwner
from tst.sim.errors import ChallengeRefusedError, InvalidModeError, SimError
from tst.sim.ledger import apply_entries
from tst.sim.mna.deals import BidForCompany
from tst.sim.modes import challenges
from tst.sim.modes.models import CompanyScore, GameMode
from tst.sim.rng import RngFactory
from tst.sim.setup import new_game
from tst.sim.state import GameState

SEED = 63


@pytest.fixture(scope="module")
def game(loaded: LoadedData) -> tuple[GameState, dict[tuple[int, str], int]]:
    state, entries = new_game(
        save_name="t",
        master_seed=SEED,
        scenario=loaded.game_data.scenario("funded_spinout"),  # type: ignore[arg-type]
        difficulty="standard",
        company_name="Kestrel",
        founder=DEFAULT_FOUNDER,
        balance=loaded.balance,
        data=loaded.game_data,
    )
    return state, dict(apply_entries({}, entries))


def _with(state: GameState, *rules: str) -> GameState:
    return replace(state, mode=GameMode(kind="campaign", challenges=rules))


def _act(state: GameState, balances, loaded: LoadedData, action: object) -> None:  # type: ignore[no-untyped-def]
    apply_action(
        state,
        action,  # type: ignore[arg-type]
        RngFactory(SEED),
        loaded.balance,
        loaded.game_data,
        balances,
        seq=1,
    )


def _cases(state: GameState) -> list[tuple[str, object]]:
    founder = state.founder_of(state.player.id)
    assert founder is not None
    f = founder.id
    rival = next(c.id for c in state.companies if not c.is_player)
    return [
        ("bootstrapped", StartRound(f, "seed", 150_000_000)),
        ("bootstrapped", RaiseSafe(f, 30_000_000, 100_000_000)),
        ("bootstrapped", AcceptBridge(f, 1)),
        ("hardware_only", CreateProduct(f, "Pipeline", "b2b_saas", ("smb",))),
        ("no_acquisitions", BidForCompany(f, rival, 10**9)),
        ("one_region", LaunchInRegion(f, 1, "europe")),
        ("no_automation", SetAuthority(f, "cto", True)),
        ("no_automation", SetAreaOwner(f, "hiring", f)),
    ]


def test_each_rule_refuses_its_actions_by_name(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, balances = game
    for rule, action in _cases(state):
        with pytest.raises(ChallengeRefusedError) as refused:
            _act(_with(state, rule), balances, loaded, action)
        assert challenges.LABELS[rule][0] in refused.value.message  # type: ignore[index]
        assert refused.value.code == "challenge_refused"


def test_a_game_without_the_rule_is_not_refused_by_it(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, balances = game
    for rule, action in _cases(state):
        others = tuple(r for r in challenges.RULES if r != rule and r != "hardware_only")
        for s in (state, _with(state, *others)):
            try:
                _act(s, balances, loaded, action)
            except ChallengeRefusedError:  # pragma: no cover - the failure this test guards
                raise
            except SimError:
                pass  # the game's own rules may refuse it; no challenge does


def test_hardware_only_allows_a_device(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, balances = game
    founder = state.founder_of(state.player.id)
    assert founder is not None
    action = CreateProduct(founder.id, "Handset", "devices", ("consumer",))
    _act(_with(state, "hardware_only"), balances, loaded, action)  # no refusal


def test_scores_multiply_and_unknown_rules_are_refused(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, _ = game
    b = loaded.balance
    assert challenges.score_mult(None, b) == 1.0
    two = _with(state, "bootstrapped", "one_region").mode
    want = (
        b.challenges.rules["bootstrapped"].score_mult * b.challenges.rules["one_region"].score_mult
    )
    assert challenges.score_mult(two, b) == pytest.approx(want)
    assert challenges.validate(("one_region", "bootstrapped")) == ("bootstrapped", "one_region")
    with pytest.raises(InvalidModeError):
        challenges.validate(("no_sleep",))


def test_hard_rivals_weighs_only_rivals(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, _ = game
    b = loaded.balance
    assert challenges.rival_quality_mult(state, b) == 1.0
    hard = _with(state, "hard_rivals")
    assert challenges.rival_quality_mult(hard, b) == b.challenges.hard_rivals_quality_mult == 1.2
    rival = next(c.id for c in state.companies if not c.is_player)
    assert challenges.is_rival_product(hard, rival)
    assert not challenges.is_rival_product(hard, state.player.id)


def test_difficulty_bands(loaded: LoadedData) -> None:
    b = loaded.balance
    assert [challenges.difficulty(w, b) for w in (None, 0, 3, 4, 6, 7, 10)] == [
        None, "hard", "hard", "medium", "medium", "easy", "easy",
    ]  # fmt: skip


# --- The results file -------------------------------------------------------------------------


def _done(state: GameState, result: str, score: int, *rules: str) -> GameState:
    mode = GameMode(
        kind="scenario", scenario="the_crash", result=result, result_turn=-1, challenges=rules
    )  # type: ignore[arg-type]
    snap = CompanyScore(state.player.id, -1, score, 10**8, 0.5, 0.5, 0.2, 0.6, 10**7)
    return replace(state, mode=mode, scores=(snap,))


def test_a_record_holds_the_score_parts_and_the_challenges(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, _ = game
    b = loaded.balance
    assert kept.record_of(state, "s", b) is None  # a campaign keeps nothing
    rec = kept.record_of(_done(state, "success", 400, "bootstrapped"), "s", b)
    assert rec is not None
    assert (rec["result"], rec["score"], rec["challenges"]) == ("success", 400, ["bootstrapped"])
    assert rec["adjusted"] == round(400 * b.challenges.rules["bootstrapped"].score_mult)
    assert set(rec["parts"]) == {"value", "growth", "profit", "leadership", "reputation"}


def test_the_best_is_a_win_then_the_higher_score(loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, _ = game
    b = loaded.balance
    records = {
        "a": kept.record_of(_done(state, "failure", 900), "a", b),
        "b": kept.record_of(_done(state, "success", 300), "b", b),
        "c": kept.record_of(_done(state, "success", 250, "one_region", "hard_rivals"), "c", b),
    }
    best = kept.best(records)  # type: ignore[arg-type]
    assert best is not None and best["save"] == "c"  # 250 x 1.25 x 1.25 = 391 beats 300
    assert kept.best(records, without="c")["save"] == "b"  # type: ignore[arg-type,index]
    assert kept.best({}) is None


def test_the_results_file_survives_its_saves(tmp_path: Path, loaded: LoadedData, game) -> None:  # type: ignore[no-untyped-def]
    state, _ = game
    path = kept.results_path(tmp_path)
    assert path.parent.name == "results" and kept.load(tmp_path) == {}
    rec = kept.record_of(_done(state, "success", 300), "s", loaded.balance)
    kept._write(path, "default", {"the_crash": {"s:1": rec}})  # type: ignore[dict-item]
    assert kept.load(tmp_path)["the_crash"]["s:1"]["score"] == 300
    path.write_text("not json", encoding="utf-8")
    assert kept.load(tmp_path) == {}  # an unreadable file starts again
