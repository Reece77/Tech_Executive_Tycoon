"""M43 sub-task 2: the conglomerate view's books (tst.sim.group.conglomerate) and the January
letter's facts and template (tst.events.letter)."""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from tst.events import letter
from tst.loader import LoadedData
from tst.sim.group.conglomerate import (
    CORPORATE,
    Books,
    LineSum,
    books,
    growth,
    risk_word,
    split,
)

HOLD, OPS, SUB = 1, 2, 3
TYPES = {
    "1000_cash": "asset",
    "1500_ppe": "asset",
    "1510_accumulated_depreciation": "asset",
    "1810_investment_subsidiaries": "asset",
    "2000_payables": "liability",
    "2500_debt": "liability",
    "3000_common_equity": "equity",
    "4000_revenue_subscriptions": "revenue",
    "4300_intercompany_sales": "revenue",
    "4420_foundry_sales": "revenue",
    "5000_cogs": "expense",
    "5900_intercompany_purchases": "expense",
    "6000_salaries": "expense",
    "6700_depreciation": "expense",
    "6900_general_admin": "expense",
    "7000_interest": "expense",
}
NAMES = {
    OPS: {"Pipeline": "software", "Handset": "devices"},
    SUB: {"Fab #4, East Asia": "chips"},
}


def _line(cid: int, year: int, account: str, memo: str, cents: int) -> LineSum:
    return LineSum(cid, year, account, memo, cents)


def _books(loaded: LoadedData, lines: list[LineSum]) -> Books:
    return books(lines, NAMES, TYPES, loaded.balance.conglomerate, "7", "8", root=HOLD)


def _year(year: int) -> list[LineSum]:
    return [
        # the operating company: software and devices revenue, the phone's cost of goods,
        # salaries it does not name (shared), interest (below the line)
        _line(OPS, year, "4000_revenue_subscriptions", "Revenue: Pipeline", -300_00),
        _line(OPS, year, "4000_revenue_subscriptions", "Revenue: Handset", -700_00),
        _line(OPS, year, "1000_cash", "Revenue: Pipeline", 300_00),
        _line(OPS, year, "1000_cash", "Revenue: Handset", 700_00),
        _line(OPS, year, "5000_cogs", "Cost of goods: Handset", 400_00),
        _line(OPS, year, "6000_salaries", "Monthly costs: Salaries", 100_01),
        _line(OPS, year, "1000_cash", "Monthly costs: Salaries", -500_01),
        _line(OPS, year, "7000_interest", "Interest: a bank", 50_00),
        _line(OPS, year, "5900_intercompany_purchases", "Fab starts from Sub: chips", 80_00),
        # the fab subsidiary: intercompany sales, foundry sales, the fab's depreciation and
        # its book value
        _line(SUB, year, "4300_intercompany_sales", "Fab starts for Ops: chips", -80_00),
        _line(SUB, year, "4420_foundry_sales", "Foundry slots: Fab #4, East Asia", -100_00),
        _line(SUB, year, "6700_depreciation", "Depreciation: Fab #4, East Asia", 60_00),
        _line(
            SUB, year, "1510_accumulated_depreciation", "Depreciation: Fab #4, East Asia", -60_00
        ),
        _line(SUB, year, "1500_ppe", "Capex: Fab #4, East Asia", 1_000_00),
        _line(SUB, year, "2500_debt", "Loan", -900_00),
        # the holding company: its office (no industry revenue: corporate)
        _line(HOLD, year, "6900_general_admin", "Group office", 25_00),
        _line(HOLD, year, "1810_investment_subsidiaries", "Acquisition of Sub", 500_00),
        _line(HOLD, year, "1000_cash", "Acquisition of Sub", -500_00),
        _line(HOLD, year, "1810_investment_subsidiaries", "Funding for Sub", 70_00),
        _line(HOLD, year, "1000_cash", "Funding for Sub", -70_00),
        _line(HOLD, year, "1000_cash", "Dividend to shareholders", -10_00),
        _line(HOLD, year, "3000_common_equity", "Dividend: $0.10 a share", 10_00),
    ]


def test_lines_go_to_the_industry_they_name_and_shared_costs_split_by_revenue(
    loaded: LoadedData,
) -> None:
    b = _books(loaded, _year(2030))
    by = b.by_industry(2030)
    assert set(by) == {"software", "devices", "chips", CORPORATE}
    assert by["software"].revenue == 300_00 and by["devices"].revenue == 700_00
    assert by["chips"].revenue == 100_00  # foundry only: intercompany sales are left out
    assert by["devices"].cost_of_revenue == 400_00  # its own cost of goods, named
    # salaries (10,001 cents) split 3:7 by revenue, cents conserved (largest remainder)
    assert by["software"].operating_costs + by["devices"].operating_costs == 100_01
    assert by["software"].operating_costs == 30_00
    assert by["chips"].operating_costs == 60_00  # the fab's depreciation
    assert by[CORPORATE].operating_costs == 25_00  # the holding company's office
    group = b.group(2030)
    assert group.revenue == 1_100_00
    # operating profit: interest is below the line, intercompany nets out of the industries
    assert group.operating_profit == 1_100_00 - 400_00 - 100_01 - 60_00 - 25_00


def test_capital_employed_and_where_capital_went(loaded: LoadedData) -> None:
    b = _books(loaded, _year(2030))
    by = b.by_industry(2030)
    # the fab's book value (1,000 - 60) is chips'; the subsidiary's debt is not deducted
    assert by["chips"].capital_employed == 940_00
    # the operating company's capital (cash) is split by revenue; the holding company's
    # investment in a member is not counted twice
    assert by["software"].capital_employed + by["devices"].capital_employed == 500_00 - 1
    assert by[CORPORATE].capital_employed == -10_00 - 500_00 - 70_00  # its cash paid out
    uses = b.uses[2030]
    assert uses.capex == {"chips": 1_000_00}
    assert uses.stakes == 500_00 and uses.returned == 10_00  # funding a member is not a deal
    assert b.company[(SUB, 2030)].revenue == 180_00  # its own row keeps intercompany sales
    assert b.intercompany[(SUB, 2030)] == 80_00
    # capital employed is cumulative across years
    two = _books(loaded, _year(2030) + _year(2031))
    assert two.by_industry(2031)["chips"].capital_employed == 2 * 940_00


@given(
    st.integers(min_value=-(10**12), max_value=10**12),
    st.dictionaries(st.sampled_from("abcdef"), st.integers(min_value=0, max_value=10**9)),
)
def test_split_conserves_cents(total: int, weights: dict[str, int]) -> None:
    parts = split(total, weights)
    if any(w > 0 for w in weights.values()):
        assert sum(parts.values()) == total
        assert set(parts) == {k for k, w in weights.items() if w > 0}
    else:
        assert parts == {}


def test_growth_and_risk_words(loaded: LoadedData) -> None:
    cfg = loaded.balance.conglomerate
    assert growth([100, 150, 0, 10]) == [0.5, -1.0]
    assert risk_word([100], cfg) == "new"
    assert risk_word([100, 110, 121, 133], cfg) == "low"
    assert risk_word([100, 200, 100, 300], cfg) == "high"


def test_letter_facts_and_template_use_the_books_only(loaded: LoadedData) -> None:
    from tst.balance.game import start_game

    state = start_game(loaded, 42, "funded_spinout").state
    b = _books(loaded, _year(2029) + _year(2030))
    labels = {i.key: i.label for i in loaded.balance.conglomerate.industries}
    name, lines = letter.facts(state, b, 2030, labels)
    text = "\n".join(lines)
    assert (
        "$1k" in text
        and "$700" in text
        and "Devices and hardware" in text
        and "Chips and fabs" in text
    )
    body = letter.template(name, state.player.name, 2030, b, labels)
    assert body.startswith("Dear shareholders") and body.endswith(name)
    assert "Devices and hardware $700 at a 32.9% margin" in body
    assert letter.has_figures(b, 2030) and not letter.has_figures(b, 2031)
    _system, user = letter.prompt(name, state.player.name, 2030, lines)
    assert "Dear shareholders" in user and all(line in user for line in lines)
