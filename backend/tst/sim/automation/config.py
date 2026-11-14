"""Fixed lists of the automation layer (docs/formulas.md 40): which rules and KPIs exist, the
seats' existing areas, and the one-offs. balance.yaml's `automation.areas` names these keys
and the loader checks them."""

from __future__ import annotations

from typing import Final

# The seats' existing monthly rules (24.1, 27.1) and the area each one is (40.1's table).
SEAT_AREA: Final[dict[str, str]] = {
    "cto": "engineering",
    "cpo": "products",
    "cro": "pricing",
    "cmo": "marketing",
    "coo": "support",
    "cfo": "treasury",
}
AREA_SEAT_RULE: Final[dict[str, str]] = {area: seat for seat, area in SEAT_AREA.items()}

RULES: Final = frozenset(
    {
        "hiring",
        "seat_cto",
        "seat_cpo",
        "seat_cmo",
        "seat_coo",
        "seat_cfo",
        "pricing",
        "research",
        "regions",
        "cloud",
        "press",
        "events",
    }
)
KPIS: Final = frozenset(
    {
        "headcount",
        "open_plans",
        "builders",
        "products_below_line",
        "live_products",
        "in_development",
        "mrr",
        "churn_bp",
        "marketing_cents",
        "brand",
        "coverage_pct",
        "cash_cents",
        "runway_months",
        "research_projects",
        "research_cents",
        "regions",
        "dc_use_pct",
        "dc_capacity",
        "credibility",
        "press_waiting",
        "events_answered",
        "events_waiting",
    }
)

# 40.2's one-offs as action kinds: always a proposal, whatever their size, whoever owns the
# area, on Holiday or not. Sizes and terms that make a move a one-off (layoffs of a share of a
# unit, long contracts) are checked in tst.sim.automation.limits.
ONE_OFF_ACTIONS: Final = frozenset(
    {
        # buying, bidding and selling
        "bid_for_company",
        "make_offer_for_company",
        "acquire",
        "sell_product",
        "sell_facility",
        "sell_stake",
        "sell_unit",
        "sell_brand",
        "sell_subsidiary",
        "sell_project",
        # capital
        "start_round",
        "accept_term_sheet",
        "take_loan",
        "issue_bond",
        "start_ipo",
        "secondary_offering",
        "buyback",
        "pay_dividend",
        "raise_safe",
        # subsidiaries
        "found_subsidiary",
        "close_subsidiary",
        "carve_out",
        "spin_off",
        "set_mandate",
        # facilities and nodes
        "build_facility",
        "expand_facility",
        "convert_facility",
        "close_facility",
        "build_plant",
        "build_fab",
        "build_mine",
        "build_refinery",
        "start_node",
        "lease_office",
        "close_office",
        # exploration
        "develop_project",
        # products
        "sunset_product",
        "cancel_product",
        # people at the top
        "appoint_executive",
        "remove_executive",
        "fill_seat",
        "vacate_seat",
        "appoint_ceo",
        "dismiss_ceo",
        # contracts
        "terminate_contract",
        # licensing deals (40.6's research rule)
        "license_in",
        "license_out",
    }
)
LAYOFF_ACTIONS: Final = frozenset({"fire", "layoff"})  # one-offs at automation.layoff_share
CONTRACT_ACTIONS: Final = frozenset({"sign_contract"})  # one-offs above long_contract_months

# Pitches (27.1) that are one-offs: they no longer go ahead on Holiday (40.2).
ONE_OFF_PITCHES: Final = frozenset(
    {"sunset", "data_centre", "plant", "buyback", "dividend", "acquisition"}
)

# Pitch kinds an area's rule makes itself once the area has an owner row, so the seat's
# quarterly pitch leaves them out (40.6: Regions, Research, Cloud capacity).
AREA_PITCH_KINDS: Final[dict[str, tuple[str, ...]]] = {
    "regions": ("region",),
    "research": ("research",),
    "cloud": ("data_centre",),
}
