"""Series C and D (docs/formulas.md 20.2, M10 sub-task 3): gates, growth investors from
their year, and the board's seat limits."""

from __future__ import annotations

from dataclasses import replace

from tst.balance.game import PLAYER, start_game
from tst.loader import LoadedData
from tst.sim.calendar import ym_to_turn
from tst.sim.finance.board import seat_board
from tst.sim.finance.fundraising import deliver_term_sheets, next_series, series_problem
from tst.sim.finance.models import FundingRound
from tst.sim.rng import RngFactory
from tst.sim.state import with_company, with_round


def _closed(round_id: int, series: str, turn: int) -> FundingRound:
    return FundingRound(
        id=round_id,
        company_id=PLAYER,
        series=series,  # type: ignore[arg-type]
        status="closed",
        target_cents=10**9,
        opened_turn=turn - 1,
        expires_turn=turn + 1,
        closed_turn=turn,
        lead_firm="accel",
        pre_money_cents=10**10,
        amount_cents=10**9,
        fd_pre=10**7,
    )


def test_gates_and_order(loaded: LoadedData) -> None:
    game = start_game(loaded, 1, scenario="funded_spinout")
    state = game.state
    b = loaded.balance
    for i, series in enumerate(("a", "b"), start=50):
        state = with_round(state, _closed(i, series, i))
    assert next_series(state, PLAYER) == "c"
    state = with_company(state, replace(state.company(PLAYER), mrr_history=(2_000_000_00,)))
    assert "Series C needs ARR of at least $25,000,000" in (
        series_problem(state, PLAYER, "c", b) or ""
    )
    state = with_company(state, replace(state.company(PLAYER), mrr_history=(2_100_000_00,)))
    assert series_problem(state, PLAYER, "c", b) is None
    state = with_round(state, _closed(60, "c", 60))
    assert next_series(state, PLAYER) == "d"
    assert series_problem(state, PLAYER, "d", b) is not None  # $25.2M < $60M
    state = with_round(state, _closed(61, "d", 61))
    assert next_series(state, PLAYER) is None
    assert "Series D" in (series_problem(state, PLAYER, "d", b) or "")


def test_board_never_exceeds_seven_seats(loaded: LoadedData) -> None:
    game = start_game(loaded, 2, scenario="funded_spinout")
    state = game.state
    rng = RngFactory(2)
    b, data = loaded.balance, loaded.game_data
    sizes = []
    for i, (series, lead) in enumerate(
        (("a", "accel"), ("b", "sequoia"), ("c", "insight"), ("d", "tiger_global")), start=70
    ):
        state, _ = seat_board(state, PLAYER, series, lead, i, rng, b, data)  # type: ignore[arg-type]
        sizes.append(len(state.board(PLAYER)))
    assert sizes == [4, 6, 7, 7]
    investors = [s.firm for s in state.board(PLAYER) if s.kind == "investor"]
    assert "insight" in investors and "tiger_global" not in investors
    assert b.board.max_seats == 7


def test_growth_investors_and_softbank_from_2017(loaded: LoadedData) -> None:
    data = loaded.game_data
    keys = [f.key for f in data.investors]
    assert keys[:10] == [
        "sv_angel", "first_round", "union_square", "founders_fund", "accel", "benchmark",
        "sequoia", "a16z", "kleiner", "greylock",
    ]  # fmt: skip
    c_firms = {f.key for f in data.investors if "c" in f.series}
    assert c_firms == {
        "insight",
        "general_atlantic",
        "tiger_global",
        "dst_global",
        "softbank_vision",
    }
    softbank = next(f for f in data.investors if f.key == "softbank_vision")
    assert softbank.from_year == 2017 and softbank.check_max_cents == 500_000_000_00

    def firms_answering(turn: int) -> set[str]:
        game = start_game(loaded, 3, scenario="funded_spinout")
        state = replace(game.state, turn=turn)
        state = with_company(state, replace(state.company(PLAYER), mrr_history=(10**9,) * 13))
        rnd = replace(
            _closed(90, "c", turn), status="open", opened_turn=turn, expires_turn=turn + 2
        )
        state = with_round(state, rnd)
        seen: set[str] = set()
        for seed in range(40):
            out, _ = deliver_term_sheets(state, RngFactory(seed), loaded.balance, data)
            seen |= {t.firm for t in out.sheets_of(90)}
        return seen

    assert "softbank_vision" not in firms_answering(ym_to_turn(2016, 6))
    assert "softbank_vision" in firms_answering(ym_to_turn(2018, 6))
