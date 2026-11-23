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
        # v3 (M23c): a project, a mine, a fab or a refinery; the entity is its id
        _m(
            "mine_npv",
            "Project NPV",
            "cents",
            "project",
            "The latest study's NPV, mid of its range",
        ),
        # M36 (45.4, 45.6): the family; readiness's entity is the child's person id
        _m("heir_readiness", "Readiness", "points", "person", "An heir's readiness points"),
        _m("estate_tax", "Estate tax", "cents", "company", "What the estate would owe now"),
        _m("mine_cost", "Mine cost a tonne", "cents", "mine", "All-in sustaining cost a tonne"),
        _m(
            "fab_die_cost", "Cost per good die", "cents", "fab", "A start's cost over its good dies"
        ),
        _m(
            "refinery_cost",
            "Refinery cost a unit",
            "cents",
            "refinery",
            "Full cost a unit of output",
        ),
        # v4 (M31): an app's platform fees and a device line's catalogue effect
        _m(
            "platform_fees", "Platform fees", "cents", "product", "Store fees on the app this month"
        ),
        # v4 (M33): a tool order's wait in ASML's queue
        _m("tool_wait", "Tool wait", "months", "order", "Months to the order's last tool"),
        _m(
            "catalogue_effect",
            "Catalogue effect",
            "points",
            "product",
            "Feature points from the platform's catalogue",
        ),
        # v4 (M32): a region's energy cost and a plant's levelised cost
        _m("energy_cost", "Energy cost", "cents", "region", "Last month's energy in the region"),
        _m(
            "plant_levelised",
            "Levelised cost",
            "cents",
            "plant",
            "A new plant of this type here, a MWh, at the published capex",
        ),
        # v5 (M38): a car's unit cost and the battery price
        _m("car_unit_cost", "Unit cost", "cents", "product", "A car's materials and assembly"),
        _m("battery_price", "Battery price", "cents", "company", "A kWh of EV cells this month"),
        # v5 (M39): a plant's automation saving and a robotaxi zone's contribution a ride
        _m("automation_saving", "Automation saving", "cents", "plant", "Robots' saving a unit"),
        _m("ride_contribution", "Contribution a ride", "cents", "zone", "A ride's fare less costs"),
        # v5 (M40): a launch's cost and a constellation's payback
        _m("launch_price", "Launch cost", "cents", "product", "A vehicle's cost a flight"),
        _m(
            "constellation_payback",
            "Payback",
            "cents",
            "constellation",
            "A constellation's cumulative cash flow",
        ),
        # v5 (M44): a bid's score band
        _m("bid_score", "Score band", "points", "bid", "A government bid's weighted score"),
        # v6 (M47): where a counterpart's limit lies, as revealed (58.2)
        _m(
            "negotiation_range",
            "Revealed range",
            "cents",
            "negotiation",
            "Where the counterpart's walk-away point lies, as the talks have revealed it",
        ),
        # v4 (M34): regulators' fines and the designation thresholds
        _m("regulation_fines", "Fines", "cents", "company", "Regulators' fines on the group"),
        _m(
            "designation_thresholds",
            "Designation test",
            "percent",
            "company",
            "The group against each regime's gatekeeper thresholds",
        ),
        # v5 (M41): a medical filing's review range and a clinical study's cost
        _m("medical_review", "Review range", "months", "product", "A filing's review, as a range"),
        _m(
            "study_cost",
            "Study cost",
            "cents",
            "project",
            "A clinical study's cost from its design",
        ),
        # v5 (M42): a programme's chance to approval and rNPV, and its trial's cost
        _m("pharma_value", "Expected value", "cents", "project", "Chance to approval and rNPV"),
        _m("trial_cost", "Trial cost", "cents", "project", "A trial's cost from its design"),
    )
}
