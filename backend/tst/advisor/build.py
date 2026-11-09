"""Build an explanation for one number (M25 sub-task 1): its breakdown, its last
`history_months` and the drivers of its last change, from stored rows and the state.

Everything here reads what a screen already shows (ADR-0007): ledger lines, month-end
snapshots, product months (public scores), the shown morale and rating logs, and the
breakdowns in tst.api.breakdowns. Nothing is written."""

from __future__ import annotations

import math
from collections import defaultdict
from collections.abc import Callable, Iterable, Sequence
from dataclasses import replace

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tst.advisor.metrics import METRICS
from tst.advisor.model import Driver, Explanation, Item, MetricDef, Point
from tst.api import breakdowns as bd
from tst.api.schemas.common import BreakdownOut
from tst.db import repository
from tst.db.models import (
    AccountRow,
    LedgerEntryRow,
    LedgerLineRow,
    PersonMoraleLogRow,
    PersonRatingLogRow,
    ProductMonthRow,
)
from tst.loader import LoadedData
from tst.sim.errors import NotFoundError, SimError
from tst.sim.people.reveal import revealed_range
from tst.sim.state import GameState, company_cash

PERCENT = 100  # tunable-exempt: a fraction in percent
MONTHS_A_YEAR = 12  # tunable-exempt: ARR is 12 x MRR
DRIVERS_KEPT = 8  # tunable-exempt: drivers listed in the panel (the template names fewer)


class UnknownMetricError(NotFoundError):
    code = "unknown_metric"


class InvalidEntityError(SimError):
    code = "invalid_entity"


def _items(out: BreakdownOut | None) -> tuple[tuple[Item, ...], str | None]:
    if out is None:
        return (), None
    return tuple(Item(i.label, i.amount, i.unit) for i in out.items), out.note


def _additive(before: dict[str, float], after: dict[str, float]) -> list[Driver]:
    """Line-by-line change of an additive breakdown: the effects sum to the change."""
    keys = sorted(set(before) | set(after))
    return [
        Driver(k, effect=after.get(k, 0.0) - before.get(k, 0.0))
        for k in keys
        if after.get(k, 0.0) != before.get(k, 0.0)
    ]


def _levels(items: Iterable[Item], skip: Iterable[str] = ()) -> list[Driver]:
    skipped = set(skip)
    return [
        Driver(i.label, effect=i.amount, unit=i.unit, kind="level")
        for i in items
        if i.label not in skipped and i.amount
    ]


class Builder:
    """One explanation request: the session, the state and the data."""

    def __init__(self, session: Session, state: GameState, data: LoadedData) -> None:
        self.session = session
        self.state = state
        self.data = data
        self.company = state.player.id
        self.played = state.turn - 1  # the last closed month
        self.months = data.advisor.explain.history_months
        self.since = max(0, state.turn - self.months)
        self._prev: dict[int, list[ProductMonthRow]] = {}

    # --- shared reads -----------------------------------------------------------------------

    def snapshots(self, key: str, scale: float = 1.0) -> tuple[Point, ...]:
        snaps = repository.recent_snapshots(self.session, self.company, self.months)
        out = []
        for turn, snap in snaps:
            value = snap.kpis().get(key)
            if value is not None:
                out.append(Point(turn, float(value) * scale))
        return tuple(out)

    def cash_lines(self, turn: int, *, burn: bool) -> dict[str, float]:
        """A month's cash effects by category (cash) or by cost line (burn, before
        financing and counting money out as positive): tst.api.breakdowns' own split."""
        lines: dict[str, float] = defaultdict(float)
        if turn < 0:
            return lines
        for code, name, memo, cents in bd.cash_effects(self.session, self.company, turn):
            category = bd._category(code, memo)
            if not burn:
                lines[category] += cents
            elif category != "Financing":
                label = name if category in ("Payroll", "Marketing", "Other costs") else category
                lines[label] -= cents
        return dict(lines)

    def product_months(
        self, product_ids: Sequence[int], since: int | None = None
    ) -> list[ProductMonthRow]:
        if not product_ids:
            return []
        return list(
            self.session.scalars(
                select(ProductMonthRow)
                .where(
                    ProductMonthRow.product_id.in_(list(product_ids)),
                    ProductMonthRow.turn >= (self.since - 1 if since is None else since),
                )
                .order_by(ProductMonthRow.turn, ProductMonthRow.product_id)
            )
        )

    def product(self, entity: str | None) -> int:
        try:
            pid = int(entity or "")
        except ValueError as exc:
            raise InvalidEntityError("a product metric needs a product id") from exc
        if self.state.product(pid) is None:
            raise InvalidEntityError(f"no product {pid}")
        return pid

    def person(self, entity: str | None) -> int:
        try:
            pid = int(entity or "")
        except ValueError as exc:
            raise InvalidEntityError("a person metric needs a person id") from exc
        employment = self.state.employment_of(pid)
        if employment is None or employment.company_id != self.company:
            raise InvalidEntityError(f"person {pid} is not on your staff")
        return pid

    # --- the company --------------------------------------------------------------------------

    def cash(self, m: MetricDef, _: str | None) -> Explanation:
        items, note = _items(bd.cash_change(self.session, self.state))
        trend = self.snapshots("cash_cents")
        drivers = [Driver(k, effect=v) for k, v in self.cash_lines(self.played, burn=False).items()]
        cash = company_cash(
            repository.current_balances(self.session, self.state.turn), self.company
        )
        return self._out(m, None, float(cash), items, note, trend, drivers)

    def burn(self, m: MetricDef, _: str | None) -> Explanation:
        items, note = _items(bd.burn(self.session, self.state))
        trend = self.snapshots("monthly_burn_cents")
        drivers = _additive(
            self.cash_lines(self.played - 1, burn=True), self.cash_lines(self.played, burn=True)
        )
        return self._out(m, None, trend[-1].value if trend else 0.0, items, note, trend, drivers)

    def runway(self, m: MetricDef, _: str | None) -> Explanation:
        balances = repository.current_balances(self.session, self.state.turn)
        cash = company_cash(balances, self.company)
        items, note = _items(bd.runway(self.state, cash, self.data))
        cash_t = {p.turn: p.value for p in self.snapshots("cash_cents")}
        burn_t = {p.turn: p.value for p in self.snapshots("monthly_burn_cents")}
        trend = tuple(
            Point(t, cash_t[t] / burn_t[t]) for t in sorted(cash_t) if burn_t.get(t, 0) > 0
        )
        drivers: list[Driver] = []
        turns = [t for t in sorted(cash_t) if burn_t.get(t, 0) > 0][-2:]
        if len(turns) == 2:
            (c0, b0), (c1, b1) = ((cash_t[t], burn_t[t]) for t in turns)
            drivers = [
                Driver("Cash", effect=c1 / b0 - c0 / b0, change=c1 - c0, unit="cents"),
                Driver("Burn", effect=c1 / b1 - c1 / b0, change=b1 - b0, unit="cents"),
            ]
        projected = next((i.amount for i in items if i.label == "Projected net burn"), 0.0)
        value = cash / projected if projected > 0 else None
        return self._out(
            m,
            None,
            value,
            items,
            note,
            trend,
            drivers,
            trend_note="Each month end's cash over that month's burn.",
        )

    def _revenue_by_product(self, turn: int) -> dict[str, float]:
        own = {p.id: p.name for p in self.state.company_products(self.company)}
        if not own or turn < 0:
            return {}
        out: dict[str, float] = defaultdict(float)
        for pid, cents in self.session.execute(
            select(ProductMonthRow.product_id, func.sum(ProductMonthRow.revenue_cents))
            .where(ProductMonthRow.turn == turn, ProductMonthRow.product_id.in_(list(own)))
            .group_by(ProductMonthRow.product_id)
        ):
            out[own[int(pid)]] += float(cents)
        return dict(out)

    def _revenue(self, m: MetricDef, annual: bool, key: str) -> Explanation:
        items, note = _items(bd.revenue_by_product(self.session, self.state, annual=annual))
        trend = self.snapshots(key)
        factor = MONTHS_A_YEAR if annual else 1
        before = {k: v * factor for k, v in self._revenue_by_product(self.played - 1).items()}
        after = {k: v * factor for k, v in self._revenue_by_product(self.played).items()}
        value = trend[-1].value if trend else 0.0
        return self._out(m, None, value, items, note, trend, _additive(before, after))

    def mrr(self, m: MetricDef, _: str | None) -> Explanation:
        return self._revenue(m, False, "mrr_cents")

    def arr(self, m: MetricDef, _: str | None) -> Explanation:
        return self._revenue(m, True, "arr_cents")

    def revenue(self, m: MetricDef, _: str | None) -> Explanation:
        return self._revenue(m, False, "mrr_cents")

    def headcount(self, m: MetricDef, _: str | None) -> Explanation:
        items, note = _items(bd.headcount_by_unit(self.state))
        trend = self.snapshots("headcount")
        played = self.played
        mine = [e for e in self.state.employments if e.company_id == self.company]
        joined = sum(1 for e in mine if e.start_turn == played)
        left = sum(1 for e in mine if e.end_turn == played)
        drivers = [Driver("Joined", effect=float(joined)), Driver("Left", effect=-float(left))]
        value = float(len(self.state.staff(self.company)))
        return self._out(m, None, value, items, note, trend, drivers)

    def _accounts(self, turn: int, codes: Iterable[str] | None = None) -> dict[str, float]:
        if turn < 0:
            return {}
        wanted = set(codes) if codes is not None else None
        return {
            name: float(c)
            for code, name, c in repository.costs_for_turn(self.session, self.company, turn)
            if wanted is None or code in wanted
        }

    def payroll(self, m: MetricDef, _: str | None) -> Explanation:
        accounts = bd.PAYROLL[:2]  # salaries and benefits, as turn_snapshot.payroll_cents
        after = self._accounts(self.played, accounts)
        items = tuple(Item(k, v, "cents") for k, v in sorted(after.items()))
        trend = self.snapshots("payroll_cents")
        drivers = _additive(self._accounts(self.played - 1, accounts), after)
        note = "Salaries and benefits posted last month."
        value = trend[-1].value if trend else 0.0
        return self._out(m, None, value, items, note, trend, drivers)

    def avg_morale(self, m: MetricDef, _: str | None) -> Explanation:
        balances = repository.current_balances(self.session, self.state.turn)
        cash = company_cash(balances, self.company)
        items, note = _items(bd.average_morale(self.state, self.data, cash))
        trend = self.snapshots("avg_morale")
        value = trend[-1].value if trend else None
        return self._out(m, None, value, items, note, trend, _levels(items, ["Baseline"]))

    def board_confidence(self, m: MetricDef, _: str | None) -> Explanation:
        seats = [
            s for s in self.state.seats if s.company_id == self.company and s.confidence is not None
        ]
        firms = {f.key: f.name for f in self.data.game_data.investors}
        names = {}
        for s in seats:
            if s.firm:
                names[s.id] = firms.get(s.firm, s.firm)
            elif s.person_id is not None:
                p = self.state.person(s.person_id)
                names[s.id] = f"{p.first_name} {p.last_name}"
            else:
                names[s.id] = f"Seat {s.id}"
        items = tuple(Item(names[s.id], round(s.confidence or 0.0, 1), "points") for s in seats)
        drivers = [
            Driver(names[s.id], change=s.history[-1] - s.history[-2], unit="points")
            for s in seats
            if len(s.history) >= 2 and s.history[-1] != s.history[-2]
        ]
        trend = self.snapshots("board_confidence")
        value = trend[-1].value if trend else None
        note = "Each director's confidence; the board's is their average." if seats else None
        return self._out(m, None, value, items, note or "No board yet.", trend, drivers)

    def founder_ownership(self, m: MetricDef, _: str | None) -> Explanation:
        from tst.api.finance_views import captable_out

        table = captable_out(self.state, {}, self.data, self.company)
        holders = sorted(table.holders, key=lambda h: -h.fraction)[:DRIVERS_KEPT]
        items = tuple(Item(h.holder, round(h.fraction * PERCENT, 2), "percent") for h in holders)
        trend = self.snapshots("founder_bp", 1 / PERCENT)
        rounds = [
            r
            for r in self.state.rounds
            if r.company_id == self.company and r.closed_turn == self.played
        ]
        drivers = [
            Driver(f"Series {r.series} closed", change=float(r.new_shares or 0), unit="count")
            for r in rounds
        ]
        value = table.founder_fraction * PERCENT
        note = "Fully diluted: issued shares and the whole option pool."
        return self._out(m, None, value, items, note, trend, drivers)

    # --- a product ------------------------------------------------------------------------------

    def _by_turn(self, rows: Iterable[ProductMonthRow]) -> dict[int, list[ProductMonthRow]]:
        out: dict[int, list[ProductMonthRow]] = defaultdict(list)
        for r in rows:
            out[r.turn].append(r)
        return out

    def _product_series(
        self, pid: int, value: Callable[[list[ProductMonthRow]], float | None]
    ) -> tuple[dict[int, list[ProductMonthRow]], tuple[Point, ...]]:
        months = self._by_turn(self.product_months([pid]))
        points = []
        for turn in sorted(months):
            if turn < self.since:
                continue
            v = value(months[turn])
            if v is not None:
                points.append(Point(turn, v))
        return months, tuple(points)

    def _name(self, pid: int) -> str:
        product = self.state.product(pid)
        assert product is not None
        return product.name

    def _seg_label(self, key: str) -> str:
        return self.data.game_data.segment(key).label

    def customers(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)
        months, trend = self._product_series(pid, lambda rs: sum(r.customers for r in rs))
        last = months.get(self.played, [])
        items = tuple(Item(self._seg_label(r.segment), round(r.customers), "count") for r in last)
        items += (
            Item("New last month", round(sum(r.new for r in last)), "count"),
            Item("Churned last month", round(sum(r.churned for r in last)), "count"),
        )
        drivers = [
            Driver(f"New in {self._seg_label(r.segment)}", effect=r.new) for r in last if r.new
        ] + [
            Driver(f"Lost in {self._seg_label(r.segment)}", effect=-r.churned)
            for r in last
            if r.churned
        ]
        value = trend[-1].value if trend else 0.0
        note = "Customers by segment at the last month end, with last month's flows."
        return self._out(m, entity, value, items, note, trend, drivers, subject=self._name(pid))

    def product_mrr(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)
        months, trend = self._product_series(pid, lambda rs: sum(r.revenue_cents for r in rs))
        seg = {
            t: {self._seg_label(r.segment): float(r.revenue_cents) for r in rs}
            for t, rs in months.items()
        }
        items = tuple(Item(k, v, "cents") for k, v in sorted(seg.get(self.played, {}).items()))
        drivers = _additive(seg.get(self.played - 1, {}), seg.get(self.played, {}))
        value = trend[-1].value if trend else 0.0
        return self._out(
            m,
            entity,
            value,
            items,
            "Revenue by segment in the last closed month.",
            trend,
            drivers,
            subject=self._name(pid),
        )

    def _churn_factors(
        self, turn: int, own: list[ProductMonthRow], rivals: dict[tuple[int, str], float]
    ) -> tuple[float, float, float] | None:
        """(churn rate, weighted appeal-gap factor, low-quality factor) for one month, from
        public scores: the 11.7 terms the player can work out from the Market screen."""
        keys = self.data.balance.market
        prev = {r.segment: r.customers for r in self._prev.get(turn - 1, [])}
        held = sum(prev.get(r.segment, 0.0) for r in own)
        if held <= 0:
            return None
        rate = sum(r.churned for r in own) / held
        gap = 0.0
        for r in own:
            best = max(
                [v for (t, s), v in rivals.items() if t == turn and s == r.segment]
                + [r.appeal or 0.0]
            )
            g = 1 + max(0.0, best - (r.appeal or 0.0)) / keys.gap_divisor
            gap += g * prev.get(r.segment, 0.0) / held
        quality = own[0].quality
        low = keys.low_quality_churn_mult if quality < keys.low_quality_at else 1.0
        return rate, gap, low

    def churn(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)
        product = self.state.product(pid)
        assert product is not None
        months = self._by_turn(self.product_months([pid], since=self.since - 2))
        self._prev = months
        peers = [p.id for p in self.state.products if p.category == product.category]
        rivals: dict[tuple[int, str], float] = {}
        for r in self.product_months([p for p in peers if p != pid], since=max(0, self.played - 1)):
            if r.appeal is not None and r.customers > 0:
                key = (r.turn, r.segment)
                rivals[key] = max(rivals.get(key, 0.0), r.appeal)
        points = []
        for turn in sorted(months):
            prev = {r.segment: r.customers for r in months.get(turn - 1, [])}
            held = sum(prev.get(r.segment, 0.0) for r in months[turn])
            if turn >= self.since and held > 0:
                points.append(Point(turn, sum(r.churned for r in months[turn]) / held * PERCENT))
        last = months.get(self.played, [])
        prev = {r.segment: r.customers for r in months.get(self.played - 1, [])}
        items = tuple(
            Item(
                self._seg_label(r.segment),
                round(r.churned / prev[r.segment] * PERCENT, 2),
                "percent",
            )
            for r in last
            if prev.get(r.segment)
        )
        drivers: list[Driver] = []
        f1 = self._churn_factors(self.played, last, rivals) if last else None
        f0 = (
            self._churn_factors(self.played - 1, months.get(self.played - 1, []), rivals)
            if months.get(self.played - 1)
            else None
        )
        if f0 and f1 and min(f0 + f1) > 0 and f1[0] > 0 and f0[0] != f1[0]:
            (r0, g0, l0), (r1, g1, l1) = f0, f1
            delta = (r1 - r0) * PERCENT
            whole = math.log(r1 / r0)
            rest0, rest1 = r0 / (g0 * l0), r1 / (g1 * l1)
            share = {
                "gap": math.log(g1 / g0) / whole,
                "low": math.log(l1 / l0) / whole,
                "rest": math.log(rest1 / rest0) / whole,
            }
            divisor = self.data.balance.market.gap_divisor
            drivers = [
                Driver(
                    "The appeal gap to the best product",
                    effect=delta * share["gap"],
                    change=(g1 - g0) * divisor,
                    unit="points",
                ),
                Driver(
                    "Quality",
                    effect=delta * share["low"],
                    change=last[0].quality - months[self.played - 1][0].quality,
                    unit="points",
                ),
                Driver(
                    "Base churn and everything else (support, executives, events)",
                    effect=delta * share["rest"],
                ),
            ]
        value = points[-1].value if points else None
        note = (
            "Churn by segment last month. A wider appeal gap to the best product, quality "
            "under the market's floor and a sunset raise it."
        )
        return self._out(m, entity, value, items, note, tuple(points), drivers, self._name(pid))

    def _score(self, m: MetricDef, entity: str | None, attr: str) -> Explanation:
        pid = self.product(entity)
        product = self.state.product(pid)
        assert product is not None
        _months, trend = self._product_series(
            pid, lambda rs: float(getattr(rs[0], attr)) if rs else None
        )
        items: tuple[Item, ...] = ()
        note: str | None = None
        if attr == "quality" and product.company_id == self.company:
            from tst.api.product_views import product_out

            history = repository.product_history(self.session, pid, self.since)
            items, note = _items(
                product_out(self.state, product, history, self.data).quality_breakdown
            )
        drivers = []
        if len(trend) >= 2:
            drivers.append(Driver("Change last month", effect=trend[-1].value - trend[-2].value))
        current = {
            "quality": product.quality,
            "brand": product.brand,
            "feature_score": trend[-1].value if trend else None,
        }[attr]
        if not items and current is not None:
            items = (Item(m.label, round(current, 1), "points"),)
        if attr == "brand":
            items += (Item("Marketing budget a month", product.marketing_budget_cents, "cents"),)
            note = "Brand moves toward a target set by marketing spend and the product's appeal."
        return self._out(m, entity, current, items, note, trend, drivers, self._name(pid))

    def quality(self, m: MetricDef, entity: str | None) -> Explanation:
        return self._score(m, entity, "quality")

    def brand(self, m: MetricDef, entity: str | None) -> Explanation:
        return self._score(m, entity, "brand")

    def feature_score(self, m: MetricDef, entity: str | None) -> Explanation:
        return self._score(m, entity, "feature_score")

    def appeal(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)

        def weighted(rs: list[ProductMonthRow]) -> float | None:
            held = sum(r.customers for r in rs if r.appeal is not None)
            if held <= 0:
                return None
            return sum((r.appeal or 0.0) * r.customers for r in rs if r.appeal) / held

        months, trend = self._product_series(pid, weighted)
        last = months.get(self.played, [])
        items = tuple(
            Item(self._seg_label(r.segment), round(r.appeal, 1), "points")
            for r in last
            if r.appeal is not None
        )
        drivers = []
        before = months.get(self.played - 1, [])
        if last and before:
            for label, attr in (
                ("Quality", "quality"),
                ("Brand", "brand"),
                ("Feature score", "feature_score"),
            ):
                change = float(getattr(last[0], attr)) - float(getattr(before[0], attr))
                if change:
                    drivers.append(Driver(label, change=change, unit="points"))
        note = "Appeal by segment: quality, price, brand and features by the segment's weights."
        value = trend[-1].value if trend else None
        return self._out(m, entity, value, items, note, trend, drivers, self._name(pid))

    def _served(self, category: str, turns: Sequence[int]) -> dict[tuple[int, str], float]:
        peers = [p.id for p in self.state.products if p.category == category]
        out: dict[tuple[int, str], float] = defaultdict(float)
        for r in self.product_months(peers, since=min(turns, default=self.since)):
            if r.turn in turns:
                out[(r.turn, r.segment)] += r.customers
        return out

    def share(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)
        product = self.state.product(pid)
        assert product is not None
        months = self._by_turn(self.product_months([pid]))
        turns = [t for t in sorted(months) if t >= self.since]
        served = self._served(product.category, turns)
        points = []
        for t in turns:
            total = sum(served.get((t, r.segment), 0.0) for r in months[t])
            if total > 0:
                mine = sum(r.customers for r in months[t])
                points.append(Point(t, mine / total * PERCENT))
        last = months.get(self.played, [])
        items = tuple(
            Item(
                self._seg_label(r.segment),
                round(r.customers / served[(self.played, r.segment)] * PERCENT, 2),
                "percent",
            )
            for r in last
            if served.get((self.played, r.segment))
        )
        drivers = []
        before = months.get(self.played - 1, [])
        if last and before:
            own = sum(r.customers for r in last) - sum(r.customers for r in before)
            all_now = sum(served.get((self.played, r.segment), 0.0) for r in last)
            all_then = sum(served.get((self.played - 1, r.segment), 0.0) for r in last)
            drivers = [
                Driver("Your customers", change=own, unit="count"),
                Driver("Rivals' customers", change=(all_now - all_then) - own, unit="count"),
            ]
        value = points[-1].value if points else None
        note = "Your customers over every product's customers in the same segments."
        return self._out(m, entity, value, items, note, tuple(points), drivers, self._name(pid))

    def price(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.product(entity)
        segs = [s for s in self.state.product_segments if s.product_id == pid]
        items = tuple(
            Item(self._seg_label(s.segment), float(s.price_cents), "cents")
            for s in segs
            if s.price_cents is not None
        )
        held = sum(s.customers for s in segs if s.price_cents is not None)
        value = (
            sum((s.price_cents or 0) * s.customers for s in segs) / held
            if held > 0
            else (items[0].amount if items else None)
        )
        note = "The monthly price in each segment; the value weighs them by customers."
        return self._out(m, entity, value, items, note, (), _levels(items), self._name(pid))

    # --- a person -----------------------------------------------------------------------------

    def _person_name(self, pid: int) -> str:
        p = self.state.person(pid)
        return f"{p.first_name} {p.last_name}"

    def morale(self, m: MetricDef, entity: str | None) -> Explanation:
        from tst.api.org_views import morale_breakdown
        from tst.sim.hiring.phases import monthly_costs

        pid = self.person(entity)
        if self.state.person(pid).is_founder:
            raise InvalidEntityError("the founder has no morale")
        balances = repository.current_balances(self.session, self.state.turn)
        cash = company_cash(balances, self.company)
        projected = sum(
            a
            for _, _, a in monthly_costs(
                self.state, self.company, self.data.balance, self.data.game_data
            )
        )
        terms = morale_breakdown(self.state, self.company, pid, self.data, cash, projected)
        items = tuple(Item(t.label, round(t.value, 1), "points") for t in terms.terms)
        rows = self.session.scalars(
            select(PersonMoraleLogRow)
            .where(PersonMoraleLogRow.person_id == pid, PersonMoraleLogRow.turn >= self.since)
            .order_by(PersonMoraleLogRow.turn)
        ).all()
        trend = tuple(Point(r.turn, float(r.morale)) for r in rows)
        note = f"Morale moves part of the way toward its target ({terms.target:.0f}) each month."
        return self._out(
            m,
            entity,
            float(terms.morale),
            items,
            note,
            trend,
            _levels(items, ["Baseline"]),
            self._person_name(pid),
        )

    def salary(self, m: MetricDef, entity: str | None) -> Explanation:
        from tst.sim.org.morale import market_mid_for

        pid = self.person(entity)
        employment = self.state.employment_of(pid)
        assert employment is not None
        market = market_mid_for(self.state, employment, self.data.balance, self.data.game_data)
        items, note = _items(bd.salary(employment.salary_cents, market))
        if not items:
            items = (Item("Salary", float(employment.salary_cents), "cents"),)
        return self._out(
            m,
            entity,
            float(employment.salary_cents),
            items,
            note,
            (),
            _levels(i for i in items if i.label == "Difference"),
            self._person_name(pid),
        )

    def rating(self, m: MetricDef, entity: str | None) -> Explanation:
        pid = self.person(entity)
        employment = self.state.employment_of(pid)
        reveal = self.state.reveal(self.company, pid)
        assert employment is not None
        role = self.data.game_data.role(employment.role)
        person = self.state.person(pid)
        labels = {s.key: s.label for s in self.data.game_data.skills}
        items: tuple[Item, ...] = ()
        if reveal is not None:
            items = tuple(
                Item(
                    f"{labels.get(k, k)} (shown midpoint)",
                    round(sum(revealed_range(person, reveal, k)) / 2, 1),
                    "points",
                )
                for k in role.primary
            )
        rows = self.session.scalars(
            select(PersonRatingLogRow)
            .where(PersonRatingLogRow.person_id == pid, PersonRatingLogRow.turn >= self.since)
            .order_by(PersonRatingLogRow.turn)
        ).all()
        trend = tuple(Point(r.turn, float(r.rating)) for r in rows)
        value = sum(i.amount for i in items) / len(items) if items else None
        note = (
            "The mean midpoint of the shown ranges of the role's primary skills; interviews, "
            "references and time together narrow the ranges."
        )
        drivers = []
        if len(trend) >= 2:
            drivers.append(Driver("Change last month", effect=trend[-1].value - trend[-2].value))
        return self._out(m, entity, value, items, note, trend, drivers, self._person_name(pid))

    # --- a cost line --------------------------------------------------------------------------

    def cost_line(self, m: MetricDef, entity: str | None) -> Explanation:
        code = (entity or "").strip()
        account = self.session.get(AccountRow, code)
        if account is None:
            raise InvalidEntityError(f"no account {code!r}")
        sign = 1 if account.type in ("expense", "asset") else -1
        rows = self.session.execute(
            select(LedgerEntryRow.turn, func.sum(LedgerLineRow.amount_cents))
            .join(LedgerLineRow.entry)
            .where(
                LedgerEntryRow.company_id == self.company,
                LedgerLineRow.account_code == code,
                LedgerEntryRow.turn >= self.since,
                LedgerEntryRow.turn <= self.played,
            )
            .group_by(LedgerEntryRow.turn)
        ).all()
        by_turn = {int(t): float(c) * sign for t, c in rows}
        trend = tuple(Point(t, by_turn.get(t, 0.0)) for t in range(self.since, self.played + 1))

        def memos(turn: int) -> dict[str, float]:
            out: dict[str, float] = defaultdict(float)
            for memo, _code, cents in self._memo_lines(turn, code):
                out[memo or account.name] += cents * sign
            return dict(out)

        now = memos(self.played)
        items = tuple(Item(k, v, "cents") for k, v in sorted(now.items(), key=lambda kv: -kv[1]))
        drivers = _additive(memos(self.played - 1), now)
        value = trend[-1].value if trend else 0.0
        note = f"{account.name} last month by what was posted to it."
        return self._out(m, entity, value, items, note, trend, drivers, account.name)

    def _memo_lines(self, turn: int, code: str) -> list[tuple[str, str, int]]:
        if turn < 0:
            return []
        stmt = (
            select(LedgerEntryRow.memo, LedgerLineRow.account_code, LedgerLineRow.amount_cents)
            .join(LedgerLineRow.entry)
            .where(
                LedgerEntryRow.company_id == self.company,
                LedgerEntryRow.turn == turn,
                LedgerLineRow.account_code == code,
            )
            .order_by(LedgerEntryRow.id, LedgerLineRow.id)
        )
        return [
            (str(memo or "").split(":")[0], str(c), int(a))
            for memo, c, a in self.session.execute(stmt)
        ]

    # --- a market -----------------------------------------------------------------------------

    def _category(self, entity: str | None) -> str:
        key = (entity or "").strip()
        if key not in {c.key for c in self.data.game_data.categories}:
            raise InvalidEntityError(f"no market {key!r}")
        return key

    def market_customers(self, m: MetricDef, entity: str | None) -> Explanation:
        category = self._category(entity)
        peers = {p.id: p.name for p in self.state.products if p.category == category}
        months = self._by_turn(self.product_months(list(peers)))
        trend = tuple(
            Point(t, sum(r.customers for r in rs))
            for t, rs in sorted(months.items())
            if t >= self.since
        )

        def by_product(turn: int) -> dict[str, float]:
            out: dict[str, float] = defaultdict(float)
            for r in months.get(turn, []):
                out[peers[r.product_id]] += r.customers
            return dict(out)

        now = by_product(self.played)
        top = sorted(now.items(), key=lambda kv: (-kv[1], kv[0]))[:DRIVERS_KEPT]
        items = tuple(Item(k, round(v), "count") for k, v in top)
        drivers = _additive(by_product(self.played - 1), now)
        value = trend[-1].value if trend else 0.0
        label = self.data.game_data.category(category).label
        return self._out(
            m,
            entity,
            value,
            items,
            "Customers by product, largest first.",
            trend,
            drivers,
            label,
        )

    def market_size(self, m: MetricDef, entity: str | None) -> Explanation:
        from tst.api.product_views import market_out

        category = self._category(entity)
        out = market_out(self.state, category, self.data)
        items = tuple(Item(s.label, float(s.size_cents_year), "cents") for s in out.segments)
        note = (
            f"Addressable customers times the reference price, a year; the market grows "
            f"{out.annual_growth * PERCENT:.1f}% a year."
        )
        return self._out(
            m,
            entity,
            float(out.size_cents_year),
            items,
            note,
            (),
            _levels(items),
            out.label,
            trend_note="Market size is not kept month by month.",
        )

    # --- assembly -----------------------------------------------------------------------------

    def _out(
        self,
        m: MetricDef,
        entity: str | None,
        value: float | None,
        items: Sequence[Item],
        note: str | None,
        trend: Sequence[Point],
        drivers: Sequence[Driver],
        subject: str | None = None,
        trend_note: str | None = None,
    ) -> Explanation:
        kept = sorted(drivers, key=lambda d: (-d.size, d.label))[:DRIVERS_KEPT]
        return Explanation(
            metric=m,
            entity=entity,
            subject=subject or self.state.player.name,
            value=value,
            items=tuple(items),
            note=note,
            trend=tuple(trend),
            drivers=tuple(d for d in kept if d.size > 0),
            trend_note=trend_note,
        )


def explain(
    session: Session, state: GameState, data: LoadedData, metric: str, entity: str | None
) -> Explanation:
    """The explanation of one number; UnknownMetricError or InvalidEntityError if it has none."""
    m = METRICS.get(metric)
    if m is None:
        raise UnknownMetricError(f"no metric {metric!r}")
    builder = Builder(session, state, data)
    out: Explanation = getattr(builder, metric)(m, entity)
    related = related_events(state, m, entity, data.advisor.explain.events_months)
    return replace(out, related=related)


def related_events(
    state: GameState, m: MetricDef, entity: str | None, months: int
) -> tuple[str, ...]:
    """The player's events of the last `months` that touch this number's subject, as the
    inbox shows them: the month, the title and the choice taken. Company numbers take every
    event; a product's or person's take those about it; a market's those in its segments'
    products' category."""
    from tst.sim.calendar import format_turn

    since = state.turn - months
    out = []
    for e in state.events:
        if e.company_id != state.player.id or e.turn < since or not e.title:
            continue
        if m.scope == "product" and str(e.product_id) != entity:
            continue
        if m.scope == "person" and entity not in {str(p) for p in e.person_ids}:
            continue
        if m.scope == "market":
            product = state.product(e.product_id) if e.product_id is not None else None
            if product is None or product.category != entity:
                continue
        choice = e.choice(e.chosen) if e.chosen else None
        taken = f" (you chose: {choice.label})" if choice is not None else ""
        out.append(f"{format_turn(e.turn)}: {e.title}{taken}")
    return tuple(out)
