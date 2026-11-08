"""Every number the Explain panel can explain (M25 sub-task 1), by key. A metric belongs to
the company, a product, a person, a ledger account (a cost line) or a market (category)."""

from __future__ import annotations

from tst.advisor.model import MetricDef, Scope, Unit


def _m(key: str, label: str, unit: Unit, scope: Scope, description: str) -> MetricDef:
    return MetricDef(key, label, unit, scope, description)


METRICS: dict[str, MetricDef] = {
    m.key: m
    for m in (
        # The company (Overview, top bar, Finance summary)
        _m("cash", "Cash", "cents", "company", "Cash at the last month end"),
        _m("burn", "Burn", "cents", "company", "Net cash used last month, before financing"),
        _m("runway", "Runway", "months", "company", "Cash over this month's projected net burn"),
        _m("mrr", "MRR", "cents", "company", "Recurring revenue in the last closed month"),
        _m("arr", "ARR", "cents", "company", "12 times MRR"),
        _m("revenue", "Revenue", "cents", "company", "Revenue in the last closed month"),
        _m("headcount", "Headcount", "count", "company", "Staff, the founder included"),
        _m("payroll", "Payroll", "cents", "company", "Salaries and benefits last month"),
        _m("avg_morale", "Average morale", "points", "company", "Employees' average morale"),
        _m(
            "board_confidence",
            "Board confidence",
            "points",
            "company",
            "Directors' average confidence",
        ),
        _m(
            "founder_ownership",
            "Founder ownership",
            "percent",
            "company",
            "The founder's share of fully diluted shares",
        ),
        # A product (Product screen, Products list, Market table)
        _m("customers", "Customers", "count", "product", "Customers in every segment"),
        _m("product_mrr", "Product MRR", "cents", "product", "The product's revenue last month"),
        _m("churn", "Churn", "percent", "product", "Customers lost last month, of those held"),
        _m("quality", "Quality", "points", "product", "The product's quality score"),
        _m("brand", "Brand", "points", "product", "The product's brand score"),
        _m("feature_score", "Feature score", "points", "product", "Features against the market"),
        _m("appeal", "Appeal", "points", "product", "Customer-weighted appeal in its segments"),
        _m("share", "Share of served", "percent", "product", "Its share of served customers"),
        _m("price", "Price", "cents", "product", "Customer-weighted monthly price"),
        # A person (People and Person screens)
        _m("morale", "Morale", "points", "person", "Shown morale"),
        _m("salary", "Salary", "cents", "person", "Annual salary"),
        _m("rating", "Rating", "points", "person", "Shown rating: the role's primary skills"),
        # A cost line (Finance statements): the entity is the account code
        _m("cost_line", "Cost line", "cents", "account", "One account's amount last month"),
        # A market (Market screen): the entity is the category key
        _m(
            "market_customers",
            "Market customers",
            "count",
            "market",
            "Customers of every product in the market",
        ),
        _m("market_size", "Market size", "cents", "market", "Addressable spend a year"),
    )
}
