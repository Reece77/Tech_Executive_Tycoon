"""Who works on a product, and what they contribute (docs/formulas.md 11.3, 11.10).

Everything is derived from the state: the units (and company root) assigned to a product,
their members' roles and true skills, tags and morale. The API uses `product_team` only for
names and the pace label; per-person numbers never leave the sim (11.13).
"""

from __future__ import annotations

from dataclasses import dataclass

from tst.sim.data_models import Balance, CategoryDef, GameData
from tst.sim.org.rules import OrgView
from tst.sim.org.scaleup import modifiers
from tst.sim.products import formulas as f
from tst.sim.products.models import Product
from tst.sim.state import GameState

PERFECTIONIST = "perfectionist"
MAVERICK = "maverick"


@dataclass(frozen=True, slots=True)
class Builder:
    person_id: int
    d: float  # development skill d_i
    output: float  # o_i before coordination and noise
    perfectionist: bool
    maverick: bool


@dataclass(frozen=True, slots=True)
class Contributor:
    """A seller or marketer: sell_i / 10 x m_i, or mkt_i / 10 x m_i."""

    person_id: int
    contribution: float


@dataclass(frozen=True, slots=True)
class Team:
    unit_ids: tuple[int | None, ...]  # assigned units; None = the company root
    builders: tuple[Builder, ...]
    sellers: tuple[Contributor, ...]
    marketers: tuple[Contributor, ...]
    # M8 (18.2, 18.3, 18.5): cross-division factor on output, CPO on features gained, support
    # and CMO on marketing points; all 1 for v1 companies and rivals.
    output_mult: float = 1.0
    feature_mult: float = 1.0
    marketing_mult: float = 1.0
    qcap_mult: float = 1.0  # CTO (18.3)
    churn_mult: float = 1.0  # CPO and the support shortfall (18.3, 18.4)
    brand_mult: float = 1.0  # CMO on B* (18.3)
    awareness_mult: float = 1.0  # CMO (18.3)
    pricing_power: float = 1.0  # CRO on p_ref in sales segments (18.3)

    @property
    def mavericks(self) -> int:
        return sum(1 for b in self.builders if b.maverick)

    def base_output(self, balance: Balance) -> float:
        """coord(n) x sum o_i: the team's output before monthly noise."""
        n = len(self.builders)
        total = sum(b.output for b in self.builders)
        return f.coord_factor(n, balance.products) * total * self.output_mult

    def qcap(self, balance: Balance) -> float | None:
        """Q_cap (11.4) x the CTO's factor (18.3)."""
        pb = balance.products
        cap = f.quality_cap(
            [(b.output, f.qcap_skill(b.d, b.perfectionist, pb)) for b in self.builders], pb
        )
        return cap if cap is None or self.qcap_mult == 1 else cap * self.qcap_mult

    @property
    def mu(self) -> float:
        return sum(m.contribution for m in self.marketers)

    def capacity(self, segment: str, balance: Balance) -> float:
        """New customers a month the sellers can close in a sales segment (11.3)."""
        rate = balance.products.seller_rate.get(segment, 0.0)
        return f.seller_capacity(rate, (s.contribution for s in self.sellers))


def assigned_units(state: GameState, product: Product) -> tuple[int | None, ...]:
    """Units working on the product, the company root (None) first, then by unit id."""
    company = state.company(product.company_id)
    units: list[int | None] = [None] if company.root_product_id == product.id else []
    units += [u.id for u in state.active_units(product.company_id) if u.product_id == product.id]
    return tuple(units)


def product_team(
    state: GameState,
    view: OrgView,
    product: Product,
    category: CategoryDef,
    balance: Balance,
    data: GameData,
) -> Team:
    """Members of the assigned units by function; members of child units do not count."""
    pb = balance.products
    builders: list[Builder] = []
    sellers: list[Contributor] = []
    marketers: list[Contributor] = []
    units = assigned_units(state, product)
    mods = modifiers(state, view, balance, data)  # M8 (18.5); None for v1 companies
    for unit_id in units:
        for person_id in view.members.get(unit_id, ()):
            person = state.person(person_id)
            m = f.morale_factor(state.person_state(person_id).morale, pb)
            if person.is_founder:
                function = "builder"
            else:
                employment = state.employment_of(person_id)
                if employment is None:
                    continue
                function = data.role(employment.role).product_function
            skills = person.skills
            if function == "builder":
                d = f.dev_skill(skills.as_dict(), category.dev_weights)
                t = f.tag_multiplier(person.tags, pb)
                builders.append(
                    Builder(
                        person_id=person_id,
                        d=d,
                        output=f.builder_output(d, m, t)
                        * (mods.builder.get(person_id, 1.0) if mods else 1.0),
                        perfectionist=PERFECTIONIST in person.tags,
                        maverick=MAVERICK in person.tags,
                    )
                )
            elif function == "seller":
                sell = f.sell_skill(skills["sales"], skills["negotiation"], skills["communication"])
                factor = mods.seller.get(person_id, 1.0) if mods else 1.0
                sellers.append(Contributor(person_id, f.contribution(sell, m) * factor))
            elif function == "marketer":
                mkt = f.marketing_skill(
                    skills["marketing"], skills["communication"], skills["design"]
                )
                marketers.append(Contributor(person_id, f.contribution(mkt, m)))
    return Team(
        unit_ids=units,
        builders=tuple(builders),
        sellers=tuple(sellers),
        marketers=tuple(marketers),
        output_mult=mods.output_factor(state, view, product) if mods else 1.0,
        feature_mult=mods.cpo if mods else 1.0,
        marketing_mult=mods.marketing_factor(state, product) if mods else 1.0,
        qcap_mult=mods.qcap if mods else 1.0,
        churn_mult=mods.churn_factor(state, product) if mods else 1.0,
        brand_mult=mods.brand if mods else 1.0,
        awareness_mult=mods.awareness if mods else 1.0,
        pricing_power=mods.pricing if mods else 1.0,
    )
