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
decision: the variant's appeal there is that of the lower quality).

**Rivals** (M23a; playtest 5): with `geopolitics.rivals_controlled`, a rival in a rule's
jurisdiction is restricted as the player is, but it requests no licences: it sells to a
destination only as a compliant variant from history (export_controls.yaml `rival_variants`:
NVIDIA's A800 and H20) or under a quota. The local-partner rule stays the player's. Demand a
blocked product cannot win goes to the products free in that region (products.phases), so a
Chinese rival gains where a US one is shut out.

**Leaving.** Customers in a destination that closes stay on the books and leave at
`exit_rate` a month (`exits`, before the month's markets): an `Exit` per (product, region,
segment) keeps how many are left and last month's blocked share. A share that rises adds that
part of today's customers; one that falls (a licence approved) keeps the rest.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Final

from tst.sim.data_models import Balance, GameData
from tst.sim.geo.cities import home_region
from tst.sim.geopolitics import rules as gr
from tst.sim.geopolitics import world
from tst.sim.geopolitics.models import Exit
from tst.sim.geopolitics.rules import ActiveRule
from tst.sim.products.models import Product
from tst.sim.state import (
    CompanyState,
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


def rival_variant_open(
    state: GameState, product: Product, active: ActiveRule, data: GameData
) -> bool:
    """A rival's compliant variant from history (M23a): the latest launched by now for its
    company and chip type, unless the rule voids variants launched before it."""
    chip_type = data.category(product.category).chip_type
    name = state.company(product.company_id).name
    launched = [
        v.turn
        for v in gr.controls_of(data).rival_variants
        if v.company == name and v.chip_type == chip_type and v.turn <= state.turn
    ]
    if not launched:
        return False
    return not (active.rule.voids_variants and max(launched) < active.start_turn)


def controlled(state: GameState, company_id: int, balance: Balance) -> bool:
    """Whether export controls bind the company's sales: the player's group always; a rival
    with geopolitics.rivals_controlled (M23a)."""
    if world.in_group(state, company_id):
        return True
    return balance.geopolitics.rivals_controlled and state.company(company_id).is_rival


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
    rival = not world.in_group(state, product.company_id)
    if not rival and partner_closed(state, product, country, balance, data):
        return 0.0, False
    allowed, as_variant = 1.0, False
    for a in restrict:
        if country not in world.destination_countries(data, a.rule, state.turn):
            continue
        if not rival and licence_open(state, product.id, a.key, country):
            continue
        if (
            rival_variant_open(state, product, a, data)
            if rival
            else variant_open(state, product.id, a)
        ):
            as_variant = True
            allowed *= balance.geopolitics.variant.keep
            continue
        allowed *= a.rule.quota if a.rule.regime == "quota" else 0.0
    return allowed, as_variant


def access(
    state: GameState, product: Product, region: str, balance: Balance, data: GameData
) -> Access:
    """The product's blocked and variant shares in `region` (module docstring)."""
    if not world.enabled(data) or not controlled(state, product.company_id, balance):
        return OPEN
    restrict = restricting(state, product, balance, data)
    lp = balance.geopolitics.local_partner
    rival = not world.in_group(state, product.company_id)
    if not restrict and (rival or product.category not in lp.categories):
        return OPEN
    blocked = variant = 0.0
    for c in world.countries_of(data).of_region(region):
        allowed, as_variant = country_access(state, product, c.key, restrict, balance, data)
        blocked += c.demand_share * (1 - allowed)
        if as_variant:
            variant += c.demand_share * allowed
    return Access(blocked, variant)


def access_map(state: GameState, balance: Balance, data: GameData) -> dict[tuple[int, str], Access]:
    """(product id, region) -> access for the controlled companies' selling products (the
    player's group; M23a, rivals), where not open: built once at phase 5's start."""
    out: dict[tuple[int, str], Access] = {}
    if not world.enabled(data):
        return out
    regions = data.region_keys
    for company in controlled_companies(state, balance, data):
        for product in state.company_products(company.id):
            if product.status not in ("live", "sunset"):
                continue
            for region in regions:
                a = access(state, product, region, balance, data)
                if not a.free:
                    out[(product.id, region)] = a
    return out


def controlled_companies(
    state: GameState, balance: Balance, data: GameData
) -> tuple[CompanyState, ...]:
    """The player's group, then (M23a) rivals with a selling chip product while a rule bites."""
    group = world.group(state)
    if not balance.geopolitics.rivals_controlled or not gr.biting(state, data):
        return group
    ids = {c.id for c in group}
    rivals = tuple(
        c
        for c in state.companies
        if c.id not in ids
        and c.is_rival
        and any(
            p.status in ("live", "sunset") and data.category(p.category).chip_type is not None
            for p in state.company_products(c.id)
        )
    )
    return (*group, *rivals)


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
    for company in controlled_companies(state, balance, data):
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
            state = _to_chinese_rival(state, pid, region, segment, home, leave, data)
            remaining -= leave
        if share > EPS or remaining > EPS:
            out.append(Exit(pid, region, segment, remaining, share))
    out.sort(key=lambda x: (x.product_id, x.region, x.segment))
    return replace(state, exits=tuple(out))


CHINA: Final = "china"  # tunable-exempt: countries.yaml key of China (41.5)


def _to_chinese_rival(
    state: GameState,
    pid: int,
    region: str,
    segment: str,
    home: str | None,
    n: float,
    data: GameData,
) -> GameState:
    """41.5 (M28): from 2026 the customers a controlled seller loses in a closed destination go
    to the Chinese rival (countries.yaml `rivals`) with the most customers on a product of the
    same category in that region and segment; before 2026 (and with none) they leave the market,
    as M22 had it."""
    if not state.chain_companies or data.countries is None:
        return state
    seller = state.product(pid)
    if seller is None:
        return state
    chinese = {
        c.id
        for c in state.rivals()
        if data.countries.rivals.get(c.name) == CHINA and c.id != seller.company_id
    }
    best: tuple[float, int] | None = None
    for p in state.products:
        if p.company_id not in chinese or p.category != seller.category:
            continue
        if p.status not in ("live", "sunset"):
            continue
        if region == home:
            seg = state.product_segment(p.id, segment)
            have = seg.customers if seg is not None else None
        else:
            have = next(
                (
                    r.customers
                    for r in state.regional_segments_of(p.id, region)
                    if r.segment == segment
                ),
                None,
            )
        if have is not None and (best is None or (have, -p.id) > (best[0], -best[1])):
            best = (have, p.id)
    if best is None:
        return state
    return _remove(state, best[1], region, segment, home, -n)


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
