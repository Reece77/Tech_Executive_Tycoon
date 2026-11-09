"""Selling controlled goods (docs/formulas.md 39.3).

A region's demand is split across its countries by countries.yaml's `demand_share`. For one of
the player group's products in a region, each country is open, open as a compliant variant, or
(partly) closed:

- a biting rule **restricts** the product in a country when one of its goods is a `product`
  good covering the product's chip type (at or above the rule's quality threshold), the seller
  is in the rule's jurisdiction (39.1: by country, or by ownership for `by_ownership` rules)
  and the country is a destination;
- under a restricting rule the country is open with an approved licence for the product, the
  country and the rule (or while the company sells unlicensed, `grey`: listing risk); a quota
  opens its share; a compliant variant launched on or after the rule's month (any month unless
  the rule `voids_variants`) opens it to the variant;
- a **local-partner market** (geopolitics.local_partner: cloud in China) is closed to a seller
  that is not a company sitting in the country with a local partner.

`access` gives the product's **blocked share** of the region (the demand it cannot win) and its
**variant share** (where it sells as the variant at quality - variant.quality_penalty, M22
decision: the variant's appeal there is that of the lower quality). Rivals' sales are not
controlled (M22 decision; brief: rivals' lobbying out of scope).

**Leaving.** Customers in a destination that closes stay on the books and leave at
`exit_rate` a month (`exits`, before the month's markets): an `Exit` per (product, region,
segment) keeps how many are left and last month's blocked share. A share that rises adds that
part of today's customers; one that falls (a licence approved) keeps the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.models import Exit
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.products.models import Product
from tst.sim.state import (
    GameState,
    with_product_segment,
    with_regional_segment,
)

EPS = 1e-9  # tunable-exempt: float tolerance on shares


@dataclass(frozen=True, slots=True)
class Access:
    blocked: float = 0.0  # share of the region's demand the product cannot win
    variant: float = 0.0  # share it sells to only as its compliant variant

    @property
    def free(self) -> bool:
        return self.blocked <= EPS and self.variant <= EPS


OPEN = Access()


def controls_product(
    active: ActiveRule, product: Product, balance: Balance, data: GameData
) -> bool:
    """Whether a rule's goods cover the product (module docstring)."""
    chip_type = data.category(product.category).chip_type
    if chip_type is None:
        return False
    for good in active.rule.goods:
        spec = balance.geopolitics.goods[good]
        if spec.kind == "product" and chip_type in spec.chip_types:
            threshold = active.rule.threshold
            return threshold is None or product.quality >= threshold
    return False


def restricting(
    state: GameState, product: Product, balance: Balance, data: GameData
) -> list[ActiveRule]:
    """Biting rules that restrict the product somewhere (seller and goods only)."""
    company = state.company(product.company_id)
    return [
        a
        for a in gr.biting(state, data)
        if controls_product(a, product, balance, data)
        and world.in_jurisdiction(state, company, a.rule, balance, data)
    ]


def licence_open(state: GameState, product_id: int, rule_key: str, country: str) -> bool:
    for x in state.licences:
        if x.product_id != product_id or x.rule_key != rule_key or x.country != country:
            continue
        if x.status == "grey":
            return True
        if x.status == "approved" and (x.until_turn is None or state.turn <= x.until_turn):
            return True
    return False


def variant_open(state: GameState, product_id: int, active: ActiveRule) -> bool:
    variant = next((v for v in state.variants if v.product_id == product_id), None)
    if variant is None:
        return False
    return not (active.rule.voids_variants and variant.turn < active.start_turn)


def partner_closed(
    state: GameState, product: Product, country: str, balance: Balance, data: GameData
) -> bool:
    lp = balance.geopolitics.local_partner
    if product.category not in lp.categories or country not in lp.countries:
        return False
    company = state.company(product.company_id)
    if world.company_country(state, company, balance, data) != country:
        return True
    site = next((s for s in state.sites if s.kind == "company" and s.id == company.id), None)
    return site is None or not site.local_partner


def country_access(
    state: GameState,
    product: Product,
    country: str,
    restrict: list[ActiveRule],
    balance: Balance,
    data: GameData,
) -> tuple[float, bool]:
    """(the share of the country's demand open to the product, whether only as a variant)."""
    if partner_closed(state, product, country, balance, data):
        return 0.0, False
    allowed, as_variant = 1.0, False
    for a in restrict:
        if country not in world.destination_countries(data, a.rule, state.turn):
            continue
        if licence_open(state, product.id, a.key, country):
            continue
        if variant_open(state, product.id, a):
            as_variant = True
            allowed *= balance.geopolitics.variant.keep
            continue
        allowed *= a.rule.quota if a.rule.regime == "quota" else 0.0
    return allowed, as_variant


def access(
    state: GameState, product: Product, region: str, balance: Balance, data: GameData
) -> Access:
    """The product's blocked and variant shares in `region` (module docstring)."""
    if not world.enabled(data) or not world.in_group(state, product.company_id):
        return OPEN
    restrict = restricting(state, product, balance, data)
    lp = balance.geopolitics.local_partner
    if not restrict and product.category not in lp.categories:
        return OPEN
    blocked = variant = 0.0
    for c in world.countries_of(data).of_region(region):
        allowed, as_variant = country_access(state, product, c.key, restrict, balance, data)
        blocked += c.demand_share * (1 - allowed)
        if as_variant:
            variant += c.demand_share * allowed
    return Access(blocked, variant)


def access_map(state: GameState, balance: Balance, data: GameData) -> dict[tuple[int, str], Access]:
    """(product id, region) -> access for the player group's selling products, where not
    open: built once at phase 5's start."""
    out: dict[tuple[int, str], Access] = {}
    if not world.enabled(data):
        return out
    regions = data.region_keys
    for company in world.group(state):
        for product in state.company_products(company.id):
            if product.status not in ("live", "sunset"):
                continue
            for region in regions:
                a = access(state, product, region, balance, data)
                if not a.free:
                    out[(product.id, region)] = a
    return out


def winding(
    state: GameState, product_id: int, region: str, segment: str, customers: float
) -> float:
    """The share of a segment's customers in closed destinations still buying while they
    wind down (they leave at exit_rate a month): their replacements still sell."""
    if customers <= EPS:
        return 0.0
    for x in state.exits:
        if (x.product_id, x.region, x.segment) == (product_id, region, segment):
            return min(1.0, x.remaining / customers)
    return 0.0


def exits(state: GameState, balance: Balance, data: GameData) -> GameState:
    """Customers in closed destinations leave (module docstring), before the markets."""
    if not world.enabled(data):
        return state
    rate = balance.geopolitics.exit_rate
    home = home_region(state, balance, data) if data.cities else None
    amap = access_map(state, balance, data)
    old = {(x.product_id, x.region, x.segment): x for x in state.exits}
    out: list[Exit] = []
    rows: list[tuple[int, str, str, float]] = []  # product, region, segment, customers
    for company in world.group(state):
        for product in state.company_products(company.id):
            if home is not None:
                rows += [
                    (product.id, home, s.segment, s.customers)
                    for s in state.segments_of(product.id)
                ]
            rows += [
                (product.id, r.region, r.segment, r.customers)
                for r in state.regional_segments_of(product.id)
            ]
    for pid, region, segment, customers in rows:
        share = amap.get((pid, region), OPEN).blocked
        prev = old.get((pid, region, segment))
        remaining = prev.remaining if prev else 0.0
        last = prev.share if prev else 0.0
        if share > last + EPS:  # the open part's customers in the newly closed countries
            remaining += max(0.0, customers - remaining) * (share - last) / max(EPS, 1 - last)
        elif share < last - EPS:
            remaining *= share / last if last > 0 else 0.0
        remaining = min(remaining, customers)
        leave = remaining * rate
        if leave > 0:
            state = _remove(state, pid, region, segment, home, leave)
            remaining -= leave
        if share > EPS or remaining > EPS:
            out.append(Exit(pid, region, segment, remaining, share))
    out.sort(key=lambda x: (x.product_id, x.region, x.segment))
    return replace(state, exits=tuple(out))


def _remove(
    state: GameState, pid: int, region: str, segment: str, home: str | None, n: float
) -> GameState:
    if region == home:
        seg = state.product_segment(pid, segment)
        if seg is not None:
            return with_product_segment(state, replace(seg, customers=max(0.0, seg.customers - n)))
        return state
    for r in state.regional_segments_of(pid, region):
        if r.segment == segment:
            return with_regional_segment(state, replace(r, customers=max(0.0, r.customers - n)))
    return state
