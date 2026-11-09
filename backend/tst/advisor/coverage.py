"""Which Explain metric explains each number on the main screens (M25 sub-task 1). Every
numeric field of these response models maps to a metric (tst.advisor.metrics) or is exempt
with a reason; tests/unit/test_m25_coverage.py scans the schemas so a new number has to
choose. The front end puts the Explain affordance on the mapped numbers."""

from __future__ import annotations

from typing import Final

type Covered = str  # a metric key, or "exempt: <reason>"

EXEMPT: Final = "exempt: "


def exempt(reason: str) -> Covered:
    return EXEMPT + reason


_STAGE = exempt("a stage number; the stage track explains what each stage needs")
_COUNT = exempt("a count of items listed beside it; nothing drives it but the list")
_INPUT = exempt("the player's own setting, explained by the control that sets it")
_THRESHOLD = exempt("a rule's threshold from balance.yaml, shown in its glossary entry")
_TOTAL = exempt("a statement total: each of its lines explains as a cost line")

SCREEN_FIELDS: Final[dict[str, dict[str, Covered]]] = {
    # Overview and the top bar
    "saves.OverviewOut": {
        "deals_due": _COUNT,
        "cash_cents": "cash",
        "monthly_burn_cents": "burn",
        "runway_months": "runway",
        "stage": _STAGE,
        "headcount": "headcount",
        "payroll_cents": "payroll",
        "avg_morale": "avg_morale",
        "unread_inbox": _COUNT,
        "month_total_cents": exempt("this month's costs so far, itemised as cost lines below it"),
        "month_net_burn_cents": "burn",
        "option_pool_left_bp": "founder_ownership",
        "network_bonus_candidates": _COUNT,
        "mrr_cents": "mrr",
        "arr_cents": "arr",
        "month_revenue_cents": "revenue",
    },
    "saves.CostLineOut": {"amount_cents": "cost_line"},
    "saves.FundingTileOut": {
        "post_money_cents": exempt("the last round's terms, shown on the Funding screen"),
        "founder_fraction": "founder_ownership",
        "board_confidence": "board_confidence",
        "safes_outstanding": _COUNT,
    },
    # Products and the Product screen
    "products.ProductOut": {
        "quality": "quality",
        "feature_score": "feature_score",
        "brand": "brand",
        "marketing_budget_cents": _INPUT,
        "mrr_cents": "product_mrr",
        "mrr_change": "product_mrr",
        "customers": "customers",
        "customer_trend": "customers",
        "new_last_month": "customers",
        "churned_last_month": "churn",
        "hosting_cents": "cost_line",
    },
    "products.ProductSegmentOut": {
        "price_cents": "price",
        "price_score": "appeal",
        "customers": "customers",
        "appeal": "appeal",
        "share_of_served": "share",
        "churn_rate": "churn",
        "mrr_cents": "product_mrr",
        "new_last_month": "customers",
        "churned_last_month": "churn",
    },
    "products.PortfolioOut": {
        "mrr_cents": "mrr",
        "mrr_change": "mrr",
        "arr_cents": "arr",
        "stage": _STAGE,
        "paying_customers": "customers",
        "consumer_users": "customers",
        "hosting_cents": "cost_line",
        "marketing_cents": "cost_line",
        "product_costs_cents": "cost_line",
    },
    # The Market screen
    "products.MarketOut": {
        "annual_growth": "market_size",
        "size_cents_year": "market_size",
    },
    "products.MarketSegmentOut": {
        "addressable": "market_size",
        "served": "market_customers",
        "unserved": "market_customers",
        "reference_price_cents": exempt("the segment's reference price from categories.yaml"),
        "size_cents_year": "market_size",
    },
    "products.MarketProductOut": {
        "quality": "quality",
        "feature_score": "feature_score",
        "brand": "brand",
        "price_cents": "price",
        "price_score": "appeal",
        "appeal": "appeal",
        "customers": "customers",
        "share_of_served": "share",
        "churn_rate": "churn",
        "mrr_cents": "product_mrr",
    },
    # People and the Person screen
    "people.PersonSummaryOut": {
        "age": exempt("a person's age"),
        "morale": "morale",
        "energy": exempt("the founder's energy, explained by its own adjustments list"),
        "leadership_fit_low": "rating",
        "leadership_fit_high": "rating",
    },
    "people.EmploymentOut": {
        "salary_cents": "salary",
        "equity_bp": _INPUT,
        "severance_cents": exempt("set by the contract: months of salary"),
        "tenure_months": exempt("months since they started"),
        "market_rate_cents": "salary",
        "monthly_cost_cents": "payroll",
    },
    # Finance
    "finance.StatementLineOut": {"amount_cents": "cost_line"},
    "finance.ProfitAndLossOut": {
        "total_revenue_cents": "revenue",
        "total_cost_of_revenue_cents": _TOTAL,
        "gross_margin_cents": _TOTAL,
        "total_operating_expenses_cents": _TOTAL,
        "operating_result_cents": _TOTAL,
        "total_other_gains_cents": _TOTAL,
        "interest_cents": "cost_line",
        "tax_cents": "cost_line",
        "net_result_cents": _TOTAL,
        "nci_cents": _TOTAL,
        "net_to_owners_cents": _TOTAL,
    },
    "finance.CashFlowOut": {
        "operating_cents": "burn",
        "investing_cents": "cash",
        "financing_cents": "cash",
        "change_in_cash_cents": "cash",
        "burn_cents": "burn",
    },
    "finance.BalanceSheetOut": {
        "total_assets_cents": _TOTAL,
        "total_liabilities_cents": _TOTAL,
        "accumulated_result_cents": _TOTAL,
        "total_liabilities_and_equity_cents": _TOTAL,
    },
    "finance.FinanceSummaryOut": {
        "cash_cents": "cash",
        "projected_net_burn_cents": "runway",
        "runway_months": "runway",
        "insolvent_months": exempt("months of negative cash, counted toward bankruptcy"),
        "stage": _STAGE,
        "open_bridge_amount_cents": exempt("the open bridge offer's terms"),
        "bridge_energy": _THRESHOLD,
    },
    # Competitors
    "rivals.RivalSegmentOut": {
        "quality": "quality",
        "feature_score": "feature_score",
        "brand": "brand",
        "price_cents": "price",
        "customers": "customers",
    },
}
